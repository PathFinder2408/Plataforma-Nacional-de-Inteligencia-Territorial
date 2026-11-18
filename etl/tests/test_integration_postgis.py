import os
from pathlib import Path

import psycopg
import pytest

from etl.loader import get_db_dsn
from etl.run import run_etl
from etl.seed import seed_comuna_piloto

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"


def _postgis_available(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT PostGIS_Version();")
        return True
    except Exception:
        return False


@pytest.fixture
def postgis_dsn() -> str:
    dsn = get_db_dsn()
    if not _postgis_available(dsn):
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail(f"PostGIS requerido pero inaccesible en {dsn}")
        pytest.skip("PostGIS no disponible en este entorno")
    return dsn


def test_etl_idempotency_and_explain_analyze(postgis_dsn: str, tmp_path: Path) -> None:
    seed_comuna_piloto(postgis_dsn)
    with psycopg.connect(postgis_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transaccion
                SET parcela_id = NULL
                WHERE comuna_id = (SELECT id FROM comuna WHERE codigo_ine = '04101');
                DELETE FROM parcela
                WHERE comuna_id = (SELECT id FROM comuna WHERE codigo_ine = '04101');
                """
            )
        conn.commit()

    report_1_path = tmp_path / "report_1.json"
    report_1 = run_etl(CONFIG_PATH, output_report=report_1_path, dsn=postgis_dsn)
    assert report_1_path.exists()
    assert report_1["counts"]["leidas"] == 7
    assert report_1["counts"]["aceptadas"] == 4
    assert report_1["counts"]["corregidas"] == 1
    assert report_1["counts"]["insertadas"] == 4
    assert report_1["counts"]["actualizadas"] == 0
    assert report_1["counts"]["sin_cambios"] == 0
    assert report_1["counts"]["rechazadas"] == 3

    # Verifica alerta por discrepancia > 10% en rol 00101-00002 (5000 m2 vs 8000 m2 declarados).
    alert_roles = {a["rol"] for a in report_1["alertas_superficie"]}
    assert "00101-00002" in alert_roles

    # Segunda ejecución del mismo archivo: 0 insertadas, 0 actualizadas, 4 sin cambios.
    report_2 = run_etl(CONFIG_PATH, output_report=tmp_path / "report_2.json", dsn=postgis_dsn)
    assert report_2["counts"]["insertadas"] == 0
    assert report_2["counts"]["actualizadas"] == 0
    assert report_2["counts"]["sin_cambios"] == 4

    # Verifica plan de ejecución punto -> parcela y filtro compuesto.
    with psycopg.connect(postgis_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                EXPLAIN (ANALYZE, FORMAT TEXT)
                SELECT id, rol
                FROM parcela
                WHERE ST_Intersects(geom, ST_SetSRID(ST_Point(-71.254, -29.903), 4326));
                """
            )
            plan_lines = "\n".join(r[0] for r in cur.fetchall())
            assert "Execution Time" in plan_lines
