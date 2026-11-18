import os
from pathlib import Path

import psycopg
import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="test-only")

from territorio.scoring import compute_opportunity_score, evaluate_valuation_error
from territorio.services import (
    filter_parcelas,
    get_parcela_ficha_completa,
    validate_market_valuation,
)

from etl.f2890 import run_f2890_etl
from etl.layers import run_layers_etl
from etl.run import run_etl
from etl.seed import seed_comuna_piloto

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PARCELA_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"
LAYERS_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_capas_estado.yaml"
F2890_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_f2890.yaml"


def test_compute_opportunity_score_explainable_math() -> None:
    parcela = {"procedencia": {"confianza": "alta"}}
    norm = [
        {
            "codigo_zona": "ZU-1",
            "parametros_urbanisticos": {"coef_constructibilidad": 2.4},
            "cabida_referencial": {"cumple_superficie_min": True},
            "procedencia": {"confianza": "referencial"},
        }
    ]
    relieve = {"pendiente_media_pct": 2.0, "procedencia": {"confianza": "media"}}
    mkt = {
        "h3_index": "88b2e33457fffff",
        "precio_m2_mediana_clp": 5000.0,
        "tendencia_pct": 12.0,
        "ratio_precio_avaluo": 1.3,
        "procedencia": {"confianza": "media"},
    }

    res_inv = compute_opportunity_score(
        perfil="inversionista",
        parcela=parcela,
        es_fiscal=True,
        normativa=norm,
        riesgos=[],
        relieve=relieve,
        mercado_h3=mkt,
    )
    expected = max(
        0.0, min(100.0, res_inv["puntaje_base"] + sum(f["delta"] for f in res_inv["factores"]))
    )
    assert res_inv["puntaje_total"] == round(expected, 2)

    res_fis = compute_opportunity_score(
        perfil="fiscal",
        parcela=parcela,
        es_fiscal=True,
        normativa=norm,
        riesgos=[],
        relieve=relieve,
        mercado_h3=mkt,
    )
    assert res_fis["puntaje_total"] > res_inv["puntaje_total"]


def test_evaluate_valuation_error_metrics() -> None:
    metrics = evaluate_valuation_error(
        [
            {"monto_real_clp": 100.0, "monto_estimado_clp": 110.0},
            {"monto_real_clp": 200.0, "monto_estimado_clp": 180.0},
        ]
    )
    assert metrics["muestras"] == 2
    assert metrics["mae_clp"] == 15.0
    assert metrics["mape_pct"] == 10.0


def test_scoring_and_valuation_error_postgis(transactional_db) -> None:
    from django.db import connection

    db_cfg = connection.settings_dict
    if not db_cfg.get("NAME"):
        pytest.skip("Base de datos Django no configurada")

    dsn = (
        f"postgresql://{db_cfg['USER']}:{db_cfg['PASSWORD']}"
        f"@{db_cfg['HOST']}:{db_cfg['PORT']}/{db_cfg['NAME']}"
    )
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.celda_h3');")
                if cur.fetchone()[0] is None:
                    pytest.skip("Tabla celda_h3 no migrada")
    except Exception:
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail("PostGIS inaccesible")
        pytest.skip("PostGIS no disponible")

    seed_comuna_piloto(dsn)
    run_etl(PARCELA_CONFIG, dsn=dsn)
    run_layers_etl(LAYERS_CONFIG, dsn=dsn)
    run_f2890_etl(F2890_CONFIG, dsn=dsn)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rol, id
                FROM parcela
                WHERE vigente_hasta IS NULL
                  AND rol IN ('00101-00001', '00101-00002', '00101-00003');
                """
            )
            ids = {r[0]: int(r[1]) for r in cur.fetchall()}

    f1 = get_parcela_ficha_completa(ids["00101-00001"])
    f2 = get_parcela_ficha_completa(ids["00101-00002"])
    f3 = get_parcela_ficha_completa(ids["00101-00003"])
    assert f1 and f2 and f3
    assert f1["puntaje_oportunidad"]["puntaje_total"] > f2["puntaje_oportunidad"]["puntaje_total"]
    assert f2["puntaje_oportunidad"]["puntaje_total"] > f3["puntaje_oportunidad"]["puntaje_total"]
    assert f1["mercado"]["celda_h3"] is not None

    validacion = validate_market_valuation()
    assert validacion["muestras"] >= 5
    assert validacion["mape_pct"] is not None
    assert validacion["mape_pct"] < 100.0

    sin_riesgos = filter_parcelas(excluir_riesgos=True)
    assert any(p["rol"] == "00101-00001" for p in sin_riesgos)
    assert all(p["rol"] != "00101-00002" for p in sin_riesgos)

    fiscales = filter_parcelas(solo_fiscales=True)
    assert any(p["rol"] == "00101-00003" for p in fiscales)
