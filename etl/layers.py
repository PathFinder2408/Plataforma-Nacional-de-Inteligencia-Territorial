import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import yaml
from pyproj import Transformer

from etl.config import FuenteConfig
from etl.loader import get_db_dsn, upsert_fuente
from etl.transform import (
    _normalize_str,
    _parse_date,
    compute_source_hash,
    normalize_reproject_polygon,
    read_spatial_path,
)


def _resolve_input_path(raw_input: str) -> str:
    if not raw_input.startswith(("http://", "https://", "WFS:")):
        candidate = Path(raw_input)
        if not candidate.exists():
            repo_candidate = Path(__file__).resolve().parent.parent / raw_input
            if repo_candidate.exists():
                return str(repo_candidate)
    return raw_input


def _parse_fuente(raw: dict[str, Any]) -> FuenteConfig:
    return FuenteConfig(
        nombre=str(raw["nombre"]),
        origen=str(raw["origen"]),
        licencia=str(raw["licencia"]),
        fecha_corte=str(raw["fecha_corte"]),
        confianza_defecto=str(raw.get("confianza_defecto", "referencial")),
        url=str(raw.get("url", "")),
        version_etl=str(raw.get("version_etl", "1.0.0")),
    )


def _parse_json_value(raw: Any, default: Any) -> str:
    if raw is None or raw == "":
        return json.dumps(default)
    if isinstance(raw, (list, dict)):
        return json.dumps(raw, ensure_ascii=False)
    if isinstance(raw, str):
        parsed = json.loads(raw)
        return json.dumps(parsed, ensure_ascii=False)
    return json.dumps(default)


def _prepare_rows(
    layer_cfg: dict[str, Any],
) -> tuple[str, int, int, list[dict[str, Any]], list[dict[str, Any]]]:
    input_path = _resolve_input_path(str(layer_cfg["input_path"]))
    source_crs = str(layer_cfg["source_crs"])
    file_hash = compute_source_hash(input_path)
    gdf = read_spatial_path(input_path, source_crs, layer_cfg.get("layer"))
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)

    has_raw_err = "_raw_geom_error" in gdf.columns
    repaired = 0
    prepared: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for idx, row in gdf.iterrows():
        row_num = int(idx) if isinstance(idx, int) else len(prepared) + len(rejected)
        raw_err = row.get("_raw_geom_error") if has_raw_err else None
        geom_4326, was_rep, err = normalize_reproject_polygon(row.geometry, transformer, raw_err)
        if err or geom_4326 is None:
            rejected.append({"row_index": row_num, "reason": err or "geom_error"})
            continue
        if was_rep:
            repaired += 1
        props = row.to_dict()
        props["_row_index"] = row_num
        props["_ewkt"] = f"SRID=4326;{geom_4326.wkt}"
        prepared.append(props)

    return file_hash, len(gdf), repaired, prepared, rejected


def _load_fiscal(
    cur: psycopg.Cursor,
    fuente_id: int,
    fuente: FuenteConfig,
    cols: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[int, int, int, list[dict[str, Any]]]:
    cur.execute(
        """
        CREATE TEMP TABLE tmp_fiscal_stage (
            codigo_bn varchar(64) NOT NULL,
            codigo_ine varchar(10),
            institucion varchar(150) NOT NULL,
            tipo varchar(80) NOT NULL,
            ewkt text NOT NULL,
            fecha_corte date NOT NULL,
            confianza varchar(20) NOT NULL,
            vigente_desde date NOT NULL,
            vigente_hasta date
        ) ON COMMIT DROP;
        """
    )
    fecha_corte = date.fromisoformat(fuente.fecha_corte)
    rejected: list[dict[str, Any]] = []
    params: list[tuple[Any, ...]] = []
    seen: set[tuple[str, date]] = set()

    for r in rows:
        codigo_bn = _normalize_str(r.get(cols["codigo_bn"]))
        if not codigo_bn:
            rejected.append({"row_index": r["_row_index"], "reason": "codigo_bn_faltante"})
            continue
        vig_desde = _parse_date(r.get(cols.get("vigente_desde", "")), fallback=fecha_corte)
        assert vig_desde is not None
        if (codigo_bn, vig_desde) in seen:
            rejected.append({"row_index": r["_row_index"], "reason": "duplicado_en_lote"})
            continue
        seen.add((codigo_bn, vig_desde))
        codigo_ine = _normalize_str(r.get(cols.get("codigo_ine", ""))) or None
        params.append(
            (
                codigo_bn,
                codigo_ine,
                _normalize_str(r.get(cols["institucion"])) or "Fisco de Chile",
                _normalize_str(r.get(cols["tipo"])) or "Fiscal",
                r["_ewkt"],
                fecha_corte,
                fuente.confianza_defecto,
                vig_desde,
                _parse_date(r.get(cols.get("vigente_hasta", "")), fallback=None),
            )
        )

    cur.executemany(
        """
        INSERT INTO tmp_fiscal_stage VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        params,
    )
    cur.execute(
        """
        WITH prepared AS (
            SELECT
                s.codigo_bn,
                c.id AS comuna_id,
                s.institucion,
                s.tipo,
                ST_Multi(
                    ST_CollectionExtract(ST_MakeValid(ST_GeomFromEWKT(s.ewkt)), 3)
                )::geometry(MultiPolygon, 4326) AS geom,
                s.fecha_corte,
                s.confianza,
                s.vigente_desde,
                s.vigente_hasta
            FROM tmp_fiscal_stage s
            LEFT JOIN comuna c ON c.codigo_ine = s.codigo_ine
        ),
        upserted AS (
            INSERT INTO terreno_fiscal (
                codigo_bn, comuna_id, institucion, tipo, geom, superficie_m2,
                fuente_id, fecha_corte, confianza, vigente_desde, vigente_hasta
            )
            SELECT
                codigo_bn, comuna_id, institucion, tipo, geom,
                ROUND(ST_Area(geom::geography)::numeric, 2),
                %s, fecha_corte, confianza, vigente_desde, vigente_hasta
            FROM prepared
            ON CONFLICT (codigo_bn, vigente_desde)
            DO UPDATE SET
                comuna_id = EXCLUDED.comuna_id,
                institucion = EXCLUDED.institucion,
                tipo = EXCLUDED.tipo,
                geom = EXCLUDED.geom,
                superficie_m2 = EXCLUDED.superficie_m2,
                fuente_id = EXCLUDED.fuente_id,
                fecha_corte = EXCLUDED.fecha_corte,
                confianza = EXCLUDED.confianza,
                vigente_hasta = EXCLUDED.vigente_hasta
            WHERE NOT ST_OrderingEquals(terreno_fiscal.geom, EXCLUDED.geom)
               OR (
                   terreno_fiscal.comuna_id,
                   terreno_fiscal.institucion,
                   terreno_fiscal.tipo,
                   terreno_fiscal.fuente_id,
                   terreno_fiscal.vigente_hasta
               ) IS DISTINCT FROM (
                   EXCLUDED.comuna_id,
                   EXCLUDED.institucion,
                   EXCLUDED.tipo,
                   EXCLUDED.fuente_id,
                   EXCLUDED.vigente_hasta
               )
            RETURNING (xmax = 0) AS was_inserted
        )
        SELECT
            COUNT(*) FILTER (WHERE was_inserted),
            COUNT(*) FILTER (WHERE NOT was_inserted)
        FROM upserted;
        """,
        (fuente_id,),
    )
    ins, upd = cur.fetchone() or (0, 0)
    unchanged = max(0, len(params) - int(ins) - int(upd))
    return int(ins), int(upd), unchanged, rejected


def _load_normativa(
    cur: psycopg.Cursor,
    fuente_id: int,
    fuente: FuenteConfig,
    cols: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[int, int, int, list[dict[str, Any]]]:
    cur.execute(
        """
        CREATE TEMP TABLE tmp_norm_stage (
            row_index integer NOT NULL,
            codigo_ine varchar(10) NOT NULL,
            instrumento varchar(80) NOT NULL,
            codigo_zona varchar(40) NOT NULL,
            codigo_poligono varchar(64) NOT NULL,
            nombre_zona varchar(150) NOT NULL,
            usos_permitidos jsonb NOT NULL,
            parametros_urbanisticos jsonb NOT NULL,
            ewkt text NOT NULL,
            fecha_corte date NOT NULL,
            confianza varchar(20) NOT NULL,
            vigente_desde date NOT NULL,
            vigente_hasta date
        ) ON COMMIT DROP;
        """
    )
    fecha_corte = date.fromisoformat(fuente.fecha_corte)
    rejected: list[dict[str, Any]] = []
    params: list[tuple[Any, ...]] = []
    seen: set[tuple[str, str, str, str, date]] = set()

    for r in rows:
        codigo_ine = _normalize_str(r.get(cols["codigo_ine"]))
        instrumento = _normalize_str(r.get(cols["instrumento"]))
        codigo_zona = _normalize_str(r.get(cols["codigo_zona"]))
        codigo_poligono = _normalize_str(r.get(cols.get("codigo_poligono", "")))
        if not codigo_ine or not instrumento or not codigo_zona:
            rejected.append({"row_index": r["_row_index"], "reason": "clave_normativa_incompleta"})
            continue
        vig_desde = _parse_date(r.get(cols.get("vigente_desde", "")), fallback=fecha_corte)
        assert vig_desde is not None
        key = (codigo_ine, instrumento, codigo_zona, codigo_poligono, vig_desde)
        if key in seen:
            rejected.append({"row_index": r["_row_index"], "reason": "duplicado_en_lote"})
            continue
        seen.add(key)
        params.append(
            (
                r["_row_index"],
                codigo_ine,
                instrumento,
                codigo_zona,
                codigo_poligono,
                _normalize_str(r.get(cols.get("nombre_zona", ""))),
                _parse_json_value(r.get(cols.get("usos_permitidos", "")), []),
                _parse_json_value(r.get(cols.get("parametros_urbanisticos", "")), {}),
                r["_ewkt"],
                fecha_corte,
                fuente.confianza_defecto,
                vig_desde,
                _parse_date(r.get(cols.get("vigente_hasta", "")), fallback=None),
            )
        )

    cur.executemany(
        """
        INSERT INTO tmp_norm_stage VALUES (
            %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s
        );
        """,
        params,
    )
    cur.execute(
        """
        SELECT s.row_index FROM tmp_norm_stage s
        LEFT JOIN comuna c ON c.codigo_ine = s.codigo_ine
        WHERE c.id IS NULL;
        """
    )
    missing_comunas = [
        {"row_index": int(r[0]), "reason": "comuna_no_encontrada"} for r in cur.fetchall()
    ]
    rejected.extend(missing_comunas)

    cur.execute(
        """
        WITH prepared AS (
            SELECT
                c.id AS comuna_id,
                s.instrumento,
                s.codigo_zona,
                s.codigo_poligono,
                s.nombre_zona,
                s.usos_permitidos,
                s.parametros_urbanisticos,
                ST_Multi(
                    ST_CollectionExtract(ST_MakeValid(ST_GeomFromEWKT(s.ewkt)), 3)
                )::geometry(MultiPolygon, 4326) AS geom,
                s.fecha_corte,
                s.confianza,
                s.vigente_desde,
                s.vigente_hasta
            FROM tmp_norm_stage s
            JOIN comuna c ON c.codigo_ine = s.codigo_ine
        ),
        upserted AS (
            INSERT INTO capa_normativa (
                comuna_id, instrumento, codigo_zona, codigo_poligono, nombre_zona,
                usos_permitidos, parametros_urbanisticos, geom, fuente_id,
                fecha_corte, confianza, vigente_desde, vigente_hasta
            )
            SELECT
                comuna_id, instrumento, codigo_zona, codigo_poligono, nombre_zona,
                usos_permitidos, parametros_urbanisticos, geom, %s,
                fecha_corte, confianza, vigente_desde, vigente_hasta
            FROM prepared
            ON CONFLICT (comuna_id, instrumento, codigo_zona, codigo_poligono, vigente_desde)
            DO UPDATE SET
                nombre_zona = EXCLUDED.nombre_zona,
                usos_permitidos = EXCLUDED.usos_permitidos,
                parametros_urbanisticos = EXCLUDED.parametros_urbanisticos,
                geom = EXCLUDED.geom,
                fuente_id = EXCLUDED.fuente_id,
                fecha_corte = EXCLUDED.fecha_corte,
                confianza = EXCLUDED.confianza,
                vigente_hasta = EXCLUDED.vigente_hasta
            WHERE NOT ST_OrderingEquals(capa_normativa.geom, EXCLUDED.geom)
               OR (
                   capa_normativa.nombre_zona,
                   capa_normativa.usos_permitidos,
                   capa_normativa.parametros_urbanisticos,
                   capa_normativa.fuente_id,
                   capa_normativa.vigente_hasta
               ) IS DISTINCT FROM (
                   EXCLUDED.nombre_zona,
                   EXCLUDED.usos_permitidos,
                   EXCLUDED.parametros_urbanisticos,
                   EXCLUDED.fuente_id,
                   EXCLUDED.vigente_hasta
               )
            RETURNING (xmax = 0) AS was_inserted
        )
        SELECT
            COUNT(*) FILTER (WHERE was_inserted),
            COUNT(*) FILTER (WHERE NOT was_inserted)
        FROM upserted;
        """,
        (fuente_id,),
    )
    ins, upd = cur.fetchone() or (0, 0)
    eligible = len(params) - len(missing_comunas)
    unchanged = max(0, eligible - int(ins) - int(upd))
    return int(ins), int(upd), unchanged, rejected


def _load_riesgo(
    cur: psycopg.Cursor,
    fuente_id: int,
    fuente: FuenteConfig,
    cols: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[int, int, int, list[dict[str, Any]]]:
    cur.execute(
        """
        CREATE TEMP TABLE tmp_riesgo_stage (
            codigo_evento varchar(64) NOT NULL,
            tipo varchar(30) NOT NULL,
            nivel varchar(20) NOT NULL,
            descripcion varchar(240) NOT NULL,
            ewkt text NOT NULL,
            fecha_corte date NOT NULL,
            confianza varchar(20) NOT NULL
        ) ON COMMIT DROP;
        """
    )
    fecha_corte = date.fromisoformat(fuente.fecha_corte)
    rejected: list[dict[str, Any]] = []
    params: list[tuple[Any, ...]] = []
    seen: set[tuple[str, str]] = set()

    for r in rows:
        codigo_evento = _normalize_str(r.get(cols["codigo_evento"]))
        tipo = _normalize_str(r.get(cols["tipo"])).lower()
        nivel = _normalize_str(r.get(cols["nivel"])).lower()
        if not codigo_evento or not tipo or not nivel:
            rejected.append({"row_index": r["_row_index"], "reason": "clave_riesgo_incompleta"})
            continue
        if (tipo, codigo_evento) in seen:
            rejected.append({"row_index": r["_row_index"], "reason": "duplicado_en_lote"})
            continue
        seen.add((tipo, codigo_evento))
        params.append(
            (
                codigo_evento,
                tipo,
                nivel,
                _normalize_str(r.get(cols.get("descripcion", ""))),
                r["_ewkt"],
                fecha_corte,
                fuente.confianza_defecto,
            )
        )

    cur.executemany("INSERT INTO tmp_riesgo_stage VALUES (%s, %s, %s, %s, %s, %s, %s);", params)
    cur.execute(
        """
        WITH prepared AS (
            SELECT
                codigo_evento,
                tipo,
                nivel,
                descripcion,
                ST_Multi(
                    ST_CollectionExtract(ST_MakeValid(ST_GeomFromEWKT(ewkt)), 3)
                )::geometry(MultiPolygon, 4326) AS geom,
                fecha_corte,
                confianza
            FROM tmp_riesgo_stage
        ),
        upserted AS (
            INSERT INTO capa_riesgo (
                codigo_evento, tipo, nivel, descripcion, geom, fuente_id, fecha_corte, confianza
            )
            SELECT
                codigo_evento, tipo, nivel, descripcion, geom, %s, fecha_corte, confianza
            FROM prepared
            ON CONFLICT (tipo, codigo_evento)
            DO UPDATE SET
                nivel = EXCLUDED.nivel,
                descripcion = EXCLUDED.descripcion,
                geom = EXCLUDED.geom,
                fuente_id = EXCLUDED.fuente_id,
                fecha_corte = EXCLUDED.fecha_corte,
                confianza = EXCLUDED.confianza
            WHERE NOT ST_OrderingEquals(capa_riesgo.geom, EXCLUDED.geom)
               OR (
                   capa_riesgo.nivel,
                   capa_riesgo.descripcion,
                   capa_riesgo.fuente_id
               ) IS DISTINCT FROM (
                   EXCLUDED.nivel,
                   EXCLUDED.descripcion,
                   EXCLUDED.fuente_id
               )
            RETURNING (xmax = 0) AS was_inserted
        )
        SELECT
            COUNT(*) FILTER (WHERE was_inserted),
            COUNT(*) FILTER (WHERE NOT was_inserted)
        FROM upserted;
        """,
        (fuente_id,),
    )
    ins, upd = cur.fetchone() or (0, 0)
    unchanged = max(0, len(params) - int(ins) - int(upd))
    return int(ins), int(upd), unchanged, rejected


def _load_relieve(
    cur: psycopg.Cursor,
    fuente_id: int,
    fuente: FuenteConfig,
    cols: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Cruza celdas DEM contra Parcela y actualiza métricas de elevación/pendiente/exposición."""
    cur.execute(
        """
        CREATE TEMP TABLE tmp_relieve_stage (
            elevacion_m double precision NOT NULL,
            pendiente_pct double precision NOT NULL,
            aspecto varchar(16) NOT NULL,
            geom geometry(MultiPolygon, 4326) NOT NULL
        ) ON COMMIT DROP;
        """
    )
    fecha_corte = date.fromisoformat(fuente.fecha_corte)
    rejected: list[dict[str, Any]] = []
    params: list[tuple[Any, ...]] = []

    for r in rows:
        elev = r.get(cols["elevacion_m"])
        pend = r.get(cols["pendiente_pct"])
        if elev is None or pend is None:
            rejected.append({"row_index": r["_row_index"], "reason": "metrica_relieve_faltante"})
            continue
        params.append(
            (
                float(elev),
                float(pend),
                _normalize_str(r.get(cols.get("aspecto", ""))) or "Plano",
                r["_ewkt"],
            )
        )

    cur.executemany(
        """
        INSERT INTO tmp_relieve_stage
        VALUES (%s, %s, %s, ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromEWKT(%s)), 3)));
        """,
        params,
    )
    cur.execute(
        """
        WITH agg AS (
            SELECT
                p.id AS parcela_id,
                ROUND(AVG(d.elevacion_m)::numeric, 2)::double precision AS elev_avg,
                ROUND(AVG(d.pendiente_pct)::numeric, 2)::double precision AS pend_avg,
                MAX(d.aspecto) AS aspecto_main
            FROM parcela p
            JOIN tmp_relieve_stage d ON ST_Intersects(p.geom, d.geom)
            GROUP BY p.id
        ),
        updated AS (
            UPDATE parcela p
            SET
                elevacion_media_m = agg.elev_avg,
                pendiente_media_pct = agg.pend_avg,
                exposicion_aspecto = agg.aspecto_main,
                fuente_relieve_id = %s,
                fecha_corte_relieve = %s,
                confianza_relieve = %s
            FROM agg
            WHERE p.id = agg.parcela_id
              AND (
                  p.elevacion_media_m,
                  p.pendiente_media_pct,
                  p.exposicion_aspecto,
                  p.fuente_relieve_id,
                  p.fecha_corte_relieve,
                  p.confianza_relieve
              ) IS DISTINCT FROM (
                  agg.elev_avg,
                  agg.pend_avg,
                  agg.aspecto_main,
                  %s,
                  %s,
                  %s
              )
            RETURNING p.id
        )
        SELECT
            (SELECT COUNT(*) FROM agg),
            (SELECT COUNT(*) FROM updated);
        """,
        (
            fuente_id,
            fecha_corte,
            fuente.confianza_defecto,
            fuente_id,
            fecha_corte,
            fuente.confianza_defecto,
        ),
    )
    matched, upd = cur.fetchone() or (0, 0)
    unchanged = max(0, int(matched) - int(upd))
    return 0, int(upd), unchanged, rejected


LOADERS = {
    "fiscal": _load_fiscal,
    "normativa": _load_normativa,
    "riesgo": _load_riesgo,
    "relieve": _load_relieve,
}


def run_layers_etl(
    config_path: str | Path,
    dsn: str | None = None,
    output_report: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta de forma idempotente la carga de capas del Estado, normativa, riesgo y relieve."""
    cfg_raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    results: dict[str, Any] = {}

    with psycopg.connect(dsn or get_db_dsn()) as conn:
        for layer_cfg in cfg_raw["capas"]:
            tipo = str(layer_cfg["tipo"])
            if tipo not in LOADERS:
                raise ValueError(f"Tipo de capa no soportado: {tipo}")
            fuente = _parse_fuente(layer_cfg["fuente"])
            file_hash, total_read, repaired, prepared, geom_rejected = _prepare_rows(layer_cfg)

            with conn.cursor() as cur:
                fuente_id = upsert_fuente(cur, fuente, file_hash, total_read)
                ins, upd, unch, load_rejected = LOADERS[tipo](
                    cur, fuente_id, fuente, layer_cfg["columns"], prepared
                )
            conn.commit()

            all_rejected = [*geom_rejected, *load_rejected]
            results[tipo] = {
                "fuente_id": fuente_id,
                "fuente_nombre": fuente.nombre,
                "hash_archivo": file_hash,
                "counts": {
                    "leidas": total_read,
                    "aceptadas": total_read - len(all_rejected),
                    "corregidas": repaired,
                    "insertadas": ins,
                    "actualizadas": upd,
                    "sin_cambios": unch,
                    "rechazadas": len(all_rejected),
                },
                "rechazadas_detalle": all_rejected,
            }

    if output_report:
        out_path = Path(output_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL idempotente de capas estatales y riesgo")
    parser.add_argument("--config", required=True, help="Ruta YAML de capas")
    parser.add_argument(
        "--output-report",
        default="etl/output/layers_quality_report.json",
        help="Ruta del reporte JSON",
    )
    args = parser.parse_args()
    report = run_layers_etl(args.config, output_report=args.output_report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
