import os
import time
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest
from django.conf import settings
from django.test import RequestFactory

if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="test-only")

from territorio.services import calcular_cabida_referencial, get_parcela_ficha_completa
from territorio.views import parcela_ficha_completa_view

from etl.layers import run_layers_etl
from etl.run import run_etl
from etl.seed import seed_comuna_piloto

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PARCELA_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"
LAYERS_CONFIG = REPO_ROOT / "etl" / "configs" / "la_serena_capas_estado.yaml"


def test_calcular_cabida_referencial() -> None:
    cabida = calcular_cabida_referencial(
        1000.0,
        {
            "coef_ocupacion_suelo": 0.6,
            "coef_constructibilidad": 2.4,
            "altura_max_m": 21.0,
            "superficie_predial_min_m2": 200.0,
        },
    )
    assert cabida is not None
    assert cabida["ocupacion_max_m2"] == 600.0
    assert cabida["edificabilidad_max_m2"] == 2400.0
    assert cabida["cumple_superficie_min"] is True
    assert "CIP" in cabida["descargo"]


def test_ficha_completa_view_404_and_200() -> None:
    rf = RequestFactory()
    with patch("territorio.views.get_parcela_ficha_completa", return_value=None):
        resp = parcela_ficha_completa_view(rf.get("/api/v1/parcelas/999/ficha-completa/"), 999)
    assert resp.status_code == 404

    sample = {"identificacion": {"rol": "00101-00001"}}
    with patch("territorio.views.get_parcela_ficha_completa", return_value=sample):
        resp_ok = parcela_ficha_completa_view(rf.get("/api/v1/parcelas/1/ficha-completa/"), 1)
    assert resp_ok.status_code == 200


def test_ficha_completa_cruce_espacial_postgis(transactional_db) -> None:
    from django.db import connection

    db_cfg = connection.settings_dict
    if not db_cfg.get("NAME"):
        pytest.skip("Base de datos Django no configurada en este entorno")

    dsn = (
        f"postgresql://{db_cfg['USER']}:{db_cfg['PASSWORD']}"
        f"@{db_cfg['HOST']}:{db_cfg['PORT']}/{db_cfg['NAME']}"
    )
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.capa_normativa');")
                if cur.fetchone()[0] is None:
                    pytest.skip("Tablas de Fase 3 no migradas aún")
    except Exception:
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail("PostGIS inaccesible")
        pytest.skip("PostGIS no disponible en este entorno")

    seed_comuna_piloto(dsn)
    run_etl(PARCELA_CONFIG, dsn=dsn)
    run_layers_etl(LAYERS_CONFIG, dsn=dsn)

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
            ids_by_rol = {row[0]: int(row[1]) for row in cur.fetchall()}

    t0 = time.perf_counter()
    ficha_1 = get_parcela_ficha_completa(ids_by_rol["00101-00001"])
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 1000.0
    assert ficha_1 is not None
    assert ficha_1["estatus_fiscal"]["es_fiscal"] is False
    assert ficha_1["normativa"][0]["codigo_zona"] == "ZU-1"
    assert ficha_1["normativa"][0]["cabida_referencial"]["edificabilidad_max_m2"] > 20000
    assert ficha_1["riesgos"] == []
    assert ficha_1["relieve"]["elevacion_media_m"] == 24.5
    assert ficha_1["relieve"]["procedencia"]["confianza"] == "media"

    ficha_2 = get_parcela_ficha_completa(ids_by_rol["00101-00002"])
    assert ficha_2 is not None
    assert ficha_2["riesgos"][0]["tipo"] == "tsunami"
    assert ficha_2["riesgos"][0]["nivel"] == "alto"

    ficha_3 = get_parcela_ficha_completa(ids_by_rol["00101-00003"])
    assert ficha_3 is not None
    assert ficha_3["estatus_fiscal"]["es_fiscal"] is True
    assert ficha_3["estatus_fiscal"]["coincidencias"][0]["codigo_bn"] == "BN-04101-002"
    assert ficha_3["normativa"][0]["codigo_zona"] == "ZAV"
    assert ficha_3["riesgos"][0]["tipo"] == "remocion_masa"
    assert ficha_3["relieve"]["elevacion_media_m"] == 42.0
