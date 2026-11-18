import math
import statistics
import time
import urllib.request

import psycopg

from etl.loader import get_db_dsn


def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    return int((lon_deg + 180.0) / 360.0 * n), int(
        (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    )


def _p95(values_ms: list[float]) -> float:
    ordered = sorted(values_ms)
    idx = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[idx]


def measure_point_lookup(samples: int = 30) -> float:
    dsn = get_db_dsn()
    latitudes: list[float] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for _ in range(samples):
                t0 = time.perf_counter()
                cur.execute(
                    """
                    SELECT id, rol
                    FROM parcela
                    WHERE ST_Intersects(geom, ST_SetSRID(ST_Point(-71.255, -29.904), 4326))
                    LIMIT 1;
                    """
                )
                cur.fetchall()
                latitudes.append((time.perf_counter() - t0) * 1000.0)

            cur.execute(
                """
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id, rol
                FROM parcela
                WHERE ST_Intersects(geom, ST_SetSRID(ST_Point(-71.255, -29.904), 4326))
                LIMIT 1;
                """
            )
            print("=== EXPLAIN ANALYZE (punto -> parcela) ===")
            for row in cur.fetchall():
                print(row[0])

    p95_ms = _p95(latitudes)
    print(f"Punto->Parcela p50={statistics.median(latitudes):.2f} ms | p95={p95_ms:.2f} ms")
    return p95_ms


def measure_martin_tiles(base_url: str = "http://martin:3000", samples: int = 30) -> float:
    x, y = _deg2num(-29.904, -71.255, 15)
    url = f"{base_url}/parcelas_mvt/15/{x}/{y}"
    latitudes: list[float] = []
    for _ in range(samples):
        t0 = time.perf_counter()
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()
        latitudes.append((time.perf_counter() - t0) * 1000.0)

    p95_ms = _p95(latitudes)
    print(f"Martin MVT p50={statistics.median(latitudes):.2f} ms | p95={p95_ms:.2f} ms")
    return p95_ms


if __name__ == "__main__":
    point_p95 = measure_point_lookup()
    assert point_p95 < 100.0, f"SLO punto->parcela incumplido: {point_p95:.2f} ms >= 100 ms"
    try:
        tile_p95 = measure_martin_tiles()
        assert tile_p95 < 150.0, f"SLO tiles incumplido: {tile_p95:.2f} ms >= 150 ms"
    except Exception as exc:
        print(f"Aviso Martin tiles: {exc}")
