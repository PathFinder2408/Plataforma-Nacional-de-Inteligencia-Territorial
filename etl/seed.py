import psycopg

from etl.loader import get_db_dsn


def seed_comuna_piloto(dsn: str | None = None) -> None:
    """Inserta de forma idempotente la comuna piloto La Serena (04101, Región IV)."""
    with psycopg.connect(dsn or get_db_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO comuna (codigo_ine, nombre, region_id)
                VALUES ('04101', 'La Serena', 4)
                ON CONFLICT (codigo_ine) DO NOTHING;
                """
            )
        conn.commit()


if __name__ == "__main__":
    seed_comuna_piloto()
