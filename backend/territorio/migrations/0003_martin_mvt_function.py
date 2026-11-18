from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("territorio", "0002_pg_trgm_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION public.parcelas_mvt(z integer, x integer, y integer)
            RETURNS bytea
            LANGUAGE plpgsql
            STABLE
            PARALLEL SAFE
            AS $$
            DECLARE
                bounds_3857 geometry := ST_TileEnvelope(z, x, y);
                bounds_4326 geometry := ST_Transform(bounds_3857, 4326);
                tol double precision := CASE
                    WHEN z < 12 THEN 12.0
                    WHEN z < 14 THEN 3.0
                    ELSE 0.0
                END;
                mvt bytea;
            BEGIN
                SELECT INTO mvt ST_AsMVT(tile, 'parcelas', 4096, 'geom')
                FROM (
                    SELECT
                        p.id,
                        p.rol,
                        p.destino,
                        p.serie,
                        p.confianza_geom,
                        p.superficie_m2::double precision AS superficie_m2,
                        ST_AsMVTGeom(
                            CASE
                                WHEN tol > 0 THEN ST_SimplifyPreserveTopology(
                                    ST_Transform(p.geom, 3857), tol
                                )
                                ELSE ST_Transform(p.geom, 3857)
                            END,
                            bounds_3857,
                            4096,
                            64,
                            true
                        ) AS geom
                    FROM public.parcela p
                    WHERE p.vigente_hasta IS NULL
                      AND p.geom && bounds_4326
                ) AS tile
                WHERE tile.geom IS NOT NULL;

                RETURN COALESCE(mvt, ''::bytea);
            END;
            $$;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS public.parcelas_mvt(integer, integer, integer);",
        ),
    ]
