import os
from dataclasses import dataclass

import psycopg

from etl.config import ETLConfig
from etl.transform import PreparedParcela, RejectedRow


@dataclass(frozen=True)
class AreaAlert:
    """Parcela cuya diferencia entre superficie calculada y declarada supera el umbral."""

    codigo_ine: str
    rol: str
    superficie_m2: float
    superficie_declarada: float
    diferencia_pct: float


@dataclass(frozen=True)
class LoadStats:
    """Contadores de persistencia idempotente devueltos por PostgreSQL."""

    fuente_id: int
    inserted: int
    updated: int
    unchanged: int
    rejected_missing_comuna: list[RejectedRow]
    area_alerts: list[AreaAlert]


def get_db_dsn() -> str:
    """Construye el DSN de PostgreSQL desde variables de entorno (12-factor)."""
    user = os.environ.get("POSTGRES_USER", "territorio")
    password = os.environ.get("POSTGRES_PASSWORD", "changeme_local_only")
    host = os.environ.get("POSTGRES_HOST", "postgis")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB", "territorio")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def _upsert_fuente(
    cur: psycopg.Cursor,
    config: ETLConfig,
    file_hash: str,
    total_read: int,
) -> int:
    sql = """
        INSERT INTO fuente_dato (
            nombre, origen, url, licencia, fecha_corte, fecha_descarga,
            hash_archivo, version_etl, filas_leidas, confianza_defecto
        )
        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
        ON CONFLICT (nombre, hash_archivo, version_etl)
        DO UPDATE SET
            filas_leidas = EXCLUDED.filas_leidas
        RETURNING id;
    """
    cur.execute(
        sql,
        (
            config.fuente.nombre,
            config.fuente.origen,
            config.fuente.url,
            config.fuente.licencia,
            config.fuente.fecha_corte,
            file_hash,
            config.fuente.version_etl,
            total_read,
            config.fuente.confianza_defecto,
        ),
    )
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def load_parcelas_idempotent(
    dsn: str,
    config: ETLConfig,
    file_hash: str,
    total_read: int,
    rows: list[PreparedParcela],
) -> LoadStats:
    """Carga parcelas por lotes usando tabla temporal, ST_Area(geography) y ON CONFLICT."""
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            fuente_id = _upsert_fuente(cur, config, file_hash, total_read)

            cur.execute(
                """
                CREATE TEMP TABLE tmp_parcela_stage (
                    row_index integer NOT NULL,
                    codigo_ine varchar(10) NOT NULL,
                    rol varchar(32) NOT NULL,
                    ewkt text NOT NULL,
                    superficie_declarada numeric(14, 2),
                    destino varchar(80) NOT NULL,
                    serie varchar(20) NOT NULL,
                    avaluo_fiscal bigint,
                    fecha_corte date NOT NULL,
                    confianza_geom varchar(20) NOT NULL,
                    vigente_desde date NOT NULL,
                    vigente_hasta date
                ) ON COMMIT DROP;
                """
            )

            insert_stage_sql = """
                INSERT INTO tmp_parcela_stage (
                    row_index, codigo_ine, rol, ewkt, superficie_declarada,
                    destino, serie, avaluo_fiscal, fecha_corte,
                    confianza_geom, vigente_desde, vigente_hasta
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            for start in range(0, len(rows), config.batch_size):
                batch = rows[start : start + config.batch_size]
                params = [
                    (
                        r.row_index,
                        r.codigo_ine,
                        r.rol,
                        r.ewkt,
                        r.superficie_declarada,
                        r.destino,
                        r.serie,
                        r.avaluo_fiscal,
                        r.fecha_corte,
                        r.confianza_geom,
                        r.vigente_desde,
                        r.vigente_hasta,
                    )
                    for r in batch
                ]
                cur.executemany(insert_stage_sql, params)

            cur.execute(
                """
                SELECT s.row_index, s.rol, s.codigo_ine
                FROM tmp_parcela_stage s
                LEFT JOIN comuna c ON c.codigo_ine = s.codigo_ine
                WHERE c.id IS NULL;
                """
            )
            missing_comuna = [
                RejectedRow(
                    row_index=int(r[0]),
                    rol=str(r[1]),
                    codigo_ine=str(r[2]),
                    reason="comuna_no_encontrada",
                )
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                WITH prepared AS (
                    SELECT
                        s.codigo_ine,
                        s.rol,
                        c.id AS comuna_id,
                        c.region_id,
                        ST_Multi(
                            ST_CollectionExtract(ST_MakeValid(ST_GeomFromEWKT(s.ewkt)), 3)
                        )::geometry(MultiPolygon, 4326) AS geom,
                        s.superficie_declarada,
                        s.destino,
                        s.serie,
                        s.avaluo_fiscal,
                        s.fecha_corte,
                        s.confianza_geom,
                        s.vigente_desde,
                        s.vigente_hasta
                    FROM tmp_parcela_stage s
                    JOIN comuna c ON c.codigo_ine = s.codigo_ine
                ),
                measured AS (
                    SELECT
                        *,
                        ROUND(ST_Area(geom::geography)::numeric, 2) AS superficie_m2
                    FROM prepared
                ),
                scored AS (
                    SELECT
                        *,
                        CASE
                            WHEN superficie_declarada IS NOT NULL AND superficie_declarada > 0
                            THEN ROUND(
                                (
                                    ABS(superficie_m2 - superficie_declarada)::double precision
                                    / superficie_declarada::double precision
                                    * 100.0
                                )::numeric,
                                2
                            )::double precision
                            ELSE NULL
                        END AS diferencia_superficie_pct
                    FROM measured
                ),
                upserted AS (
                    INSERT INTO parcela (
                        rol, comuna_id, region_id, geom, superficie_m2,
                        superficie_declarada, diferencia_superficie_pct,
                        destino, serie, avaluo_fiscal, fuente_id,
                        fecha_corte, confianza_geom, vigente_desde,
                        vigente_hasta, actualizado_en
                    )
                    SELECT
                        rol, comuna_id, region_id, geom, superficie_m2,
                        superficie_declarada, diferencia_superficie_pct,
                        destino, serie, avaluo_fiscal, %s,
                        fecha_corte, confianza_geom, vigente_desde,
                        vigente_hasta, NOW()
                    FROM scored
                    ON CONFLICT (comuna_id, rol, vigente_desde)
                    DO UPDATE SET
                        region_id = EXCLUDED.region_id,
                        geom = EXCLUDED.geom,
                        superficie_m2 = EXCLUDED.superficie_m2,
                        superficie_declarada = EXCLUDED.superficie_declarada,
                        diferencia_superficie_pct = EXCLUDED.diferencia_superficie_pct,
                        destino = EXCLUDED.destino,
                        serie = EXCLUDED.serie,
                        avaluo_fiscal = EXCLUDED.avaluo_fiscal,
                        fuente_id = EXCLUDED.fuente_id,
                        fecha_corte = EXCLUDED.fecha_corte,
                        confianza_geom = EXCLUDED.confianza_geom,
                        vigente_hasta = EXCLUDED.vigente_hasta,
                        actualizado_en = NOW()
                    WHERE NOT ST_OrderingEquals(parcela.geom, EXCLUDED.geom)
                       OR (
                           parcela.region_id,
                           parcela.superficie_m2,
                           parcela.superficie_declarada,
                           parcela.diferencia_superficie_pct,
                           parcela.destino,
                           parcela.serie,
                           parcela.avaluo_fiscal,
                           parcela.fuente_id,
                           parcela.fecha_corte,
                           parcela.confianza_geom,
                           parcela.vigente_hasta
                       ) IS DISTINCT FROM (
                           EXCLUDED.region_id,
                           EXCLUDED.superficie_m2,
                           EXCLUDED.superficie_declarada,
                           EXCLUDED.diferencia_superficie_pct,
                           EXCLUDED.destino,
                           EXCLUDED.serie,
                           EXCLUDED.avaluo_fiscal,
                           EXCLUDED.fuente_id,
                           EXCLUDED.fecha_corte,
                           EXCLUDED.confianza_geom,
                           EXCLUDED.vigente_hasta
                       )
                    RETURNING (xmax = 0) AS was_inserted
                )
                SELECT
                    COUNT(*) FILTER (WHERE was_inserted) AS inserted_cnt,
                    COUNT(*) FILTER (WHERE NOT was_inserted) AS updated_cnt
                FROM upserted;
                """,
                (fuente_id,),
            )
            counts_row = cur.fetchone()
            inserted = int(counts_row[0]) if counts_row else 0
            updated = int(counts_row[1]) if counts_row else 0
            eligible = len(rows) - len(missing_comuna)
            unchanged = max(0, eligible - inserted - updated)

            cur.execute(
                """
                SELECT
                    c.codigo_ine,
                    p.rol,
                    p.superficie_m2::double precision,
                    p.superficie_declarada::double precision,
                    p.diferencia_superficie_pct
                FROM parcela p
                JOIN comuna c ON c.id = p.comuna_id
                JOIN tmp_parcela_stage s
                    ON s.codigo_ine = c.codigo_ine
                   AND s.rol = p.rol
                   AND s.vigente_desde = p.vigente_desde
                WHERE p.diferencia_superficie_pct > %s
                ORDER BY p.diferencia_superficie_pct DESC;
                """,
                (config.area_diff_threshold_pct,),
            )
            alerts = [
                AreaAlert(
                    codigo_ine=str(r[0]),
                    rol=str(r[1]),
                    superficie_m2=float(r[2]),
                    superficie_declarada=float(r[3]),
                    diferencia_pct=float(r[4]),
                )
                for r in cur.fetchall()
            ]

        conn.commit()

    return LoadStats(
        fuente_id=fuente_id,
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        rejected_missing_comuna=missing_comuna,
        area_alerts=alerts,
    )
