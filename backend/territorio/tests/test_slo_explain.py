import os

import psycopg
import pytest

from etl.loader import get_db_dsn


def test_point_lookup_slo_under_100ms() -> None:
    dsn = get_db_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    EXPLAIN (ANALYZE, FORMAT JSON)
                    SELECT id, rol
                    FROM parcela
                    WHERE ST_Intersects(geom, ST_SetSRID(ST_Point(-71.255, -29.904), 4326))
                    LIMIT 1;
                    """
                )
                plan = cur.fetchone()[0][0]
    except Exception:
        if os.environ.get("REQUIRE_POSTGIS") == "1":
            pytest.fail("PostGIS inaccesible")
        pytest.skip("PostGIS no disponible en este entorno")

    exec_ms = float(plan["Execution Time"])
    assert exec_ms < 100.0, f"SLO punto->parcela excedido: {exec_ms:.2f} ms"
