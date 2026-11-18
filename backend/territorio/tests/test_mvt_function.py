import math
import os
from pathlib import Path

import psycopg
import pytest

from etl.loader import get_db_dsn
from etl.run import run_etl
from etl.seed import seed_comuna_piloto

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"


def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def test_parcelas_mvt_function_returns_bytes() -> None:
    dsn = get_db_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regprocedure('public.parcelas_mvt(integer,integer,integer)');"
                )
                exists = cur.fetchone()
                if not exists or exists[0] is None:
                    pytest.skip("Función parcelas_mvt aún no migrada")
    except Exception:
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail("PostGIS inaccesible")
        pytest.skip("PostGIS no disponible en este entorno")

    seed_comuna_piloto(dsn)
    run_etl(CONFIG_PATH, dsn=dsn)
    x, y = _deg2num(-29.904, -71.255, 15)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT octet_length(public.parcelas_mvt(15, %s, %s));", (x, y))
            size = cur.fetchone()[0]
    assert size > 0
