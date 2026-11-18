import os
from pathlib import Path

import psycopg
import pytest
from shapely import wkt

from etl.f2890 import cell_to_polygon_wkt, parse_f2890_csv, run_f2890_etl
from etl.loader import get_db_dsn
from etl.run import run_etl
from etl.seed import seed_comuna_piloto

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PARCELA_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"
F2890_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_f2890.yaml"
F2890_CSV = REPO_ROOT / "etl" / "fixtures" / "la_serena_f2890_sintetico.csv"


def test_parse_f2890_csv_and_h3_polygon_unit() -> None:
    cols = {
        "codigo_f2890": "folio_f2890",
        "codigo_ine": "cod_comuna",
        "rol": "rol_predial",
        "fecha": "fecha_inscripcion",
        "monto_clp": "monto_clp",
        "superficie_m2": "sup_m2",
        "destino": "destino",
    }
    total, valid, rejected = parse_f2890_csv(F2890_CSV, cols)
    assert total == 6
    assert len(valid) == 5
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "monto_no_positivo"

    poly = wkt.loads(cell_to_polygon_wkt("88b2e33457fffff"))
    assert poly.is_valid
    assert poly.geom_type == "Polygon"


def test_f2890_etl_and_h3_idempotent(tmp_path: Path) -> None:
    dsn = get_db_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.celda_h3');")
                if cur.fetchone()[0] is None:
                    pytest.skip("Tablas transaccion/celda_h3 no migradas aún")
    except Exception:
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail("PostGIS inaccesible")
        pytest.skip("PostGIS no disponible en este entorno")

    seed_comuna_piloto(dsn)
    run_etl(PARCELA_CONFIG, dsn=dsn)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM transaccion;")
            cur.execute("DELETE FROM celda_h3;")
        conn.commit()

    rep_1 = run_f2890_etl(F2890_CONFIG, dsn=dsn, output_report=tmp_path / "f2890_1.json")
    assert rep_1["counts"]["insertadas"] == 5
    assert rep_1["counts"]["rechazadas"] == 1
    assert rep_1["h3"]["insertadas"] >= 3

    rep_2 = run_f2890_etl(F2890_CONFIG, dsn=dsn, output_report=tmp_path / "f2890_2.json")
    assert rep_2["counts"]["insertadas"] == 0
    assert rep_2["counts"]["actualizadas"] == 0
    assert rep_2["counts"]["sin_cambios"] == 5
    assert rep_2["h3"]["insertadas"] == 0
    assert rep_2["h3"]["actualizadas"] == 0
