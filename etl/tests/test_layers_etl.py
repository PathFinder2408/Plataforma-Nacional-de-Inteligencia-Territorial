import os
from pathlib import Path

import psycopg
import pytest
import yaml

from etl.layers import _prepare_rows, run_layers_etl
from etl.loader import get_db_dsn
from etl.run import run_etl
from etl.seed import seed_comuna_piloto

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PARCELA_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"
LAYERS_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_capas_estado.yaml"


def test_prepare_rows_layers_unit() -> None:
    cfg = yaml.safe_load(LAYERS_CONFIG.read_text(encoding="utf-8"))
    for layer_cfg in cfg["capas"]:
        file_hash, total_read, repaired, prepared, rejected = _prepare_rows(layer_cfg)
        assert len(file_hash) == 64
        assert total_read == 2
        assert repaired == 0
        assert len(prepared) == 2
        assert len(rejected) == 0


def _postgis_ready(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.capa_normativa');")
                return cur.fetchone()[0] is not None
    except Exception:
        return False


def test_layers_etl_idempotent(tmp_path: Path) -> None:
    dsn = get_db_dsn()
    if not _postgis_ready(dsn):
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail("PostGIS o tabla capa_normativa no disponible")
        pytest.skip("PostGIS no disponible en este entorno")

    seed_comuna_piloto(dsn)
    run_etl(PARCELA_CONFIG, dsn=dsn)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM terreno_fiscal;")
            cur.execute("DELETE FROM capa_normativa;")
            cur.execute("DELETE FROM capa_riesgo;")
            cur.execute(
                """
                UPDATE parcela
                SET elevacion_media_m = NULL,
                    pendiente_media_pct = NULL,
                    exposicion_aspecto = '',
                    fuente_relieve_id = NULL,
                    fecha_corte_relieve = NULL,
                    confianza_relieve = '';
                """
            )
        conn.commit()

    rep_1 = run_layers_etl(LAYERS_CONFIG, dsn=dsn, output_report=tmp_path / "layers_1.json")
    assert rep_1["fiscal"]["counts"]["insertadas"] == 2
    assert rep_1["normativa"]["counts"]["insertadas"] == 2
    assert rep_1["riesgo"]["counts"]["insertadas"] == 2
    assert rep_1["relieve"]["counts"]["actualizadas"] >= 3

    rep_2 = run_layers_etl(LAYERS_CONFIG, dsn=dsn, output_report=tmp_path / "layers_2.json")
    for tipo in ("fiscal", "normativa", "riesgo", "relieve"):
        assert rep_2[tipo]["counts"]["insertadas"] == 0
        assert rep_2[tipo]["counts"]["actualizadas"] == 0
        assert rep_2[tipo]["counts"]["sin_cambios"] >= 2
