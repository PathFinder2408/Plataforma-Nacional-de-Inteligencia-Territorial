import argparse
import csv
import json
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import h3
import psycopg
import yaml
from shapely.geometry import Polygon

from etl.config import FuenteConfig
from etl.loader import get_db_dsn, upsert_fuente
from etl.transform import compute_source_hash


@dataclass(frozen=True)
class PreparedTransaccion:
    row_index: int
    codigo_f2890: str
    codigo_ine: str
    rol: str
    fecha: date
    monto_clp: int
    superficie_m2: float | None
    precio_m2_clp: float | None
    destino: str


def _resolve_path(raw_input: str) -> Path:
    p = Path(raw_input)
    if p.exists():
        return p
    return Path(__file__).resolve().parent.parent / raw_input


def cell_to_polygon_wkt(h3_index: str) -> str:
    """Convierte una celda H3 a Polygon WKT en EPSG:4326 (lng, lat)."""
    boundary_lat_lng = h3.cell_to_boundary(h3_index)
    coords = [(lng, lat) for lat, lng in boundary_lat_lng]
    coords.append(coords[0])
    return Polygon(coords).wkt


def parse_f2890_csv(
    csv_path: Path,
    cols: dict[str, str],
) -> tuple[int, list[PreparedTransaccion], list[dict[str, Any]]]:
    """Lee CSV F2890 aplicando whitelist de columnas (sin PII) y valida montos/fechas."""
    valid: list[PreparedTransaccion] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    total = 0

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader):
            total += 1
            folio = str(row.get(cols["codigo_f2890"]) or "").strip()
            cod_ine = str(row.get(cols["codigo_ine"]) or "").strip()
            rol = str(row.get(cols["rol"]) or "").strip()
            raw_fecha = str(row.get(cols["fecha"]) or "").strip()
            raw_monto = row.get(cols["monto_clp"])

            if not folio or not cod_ine or not rol or not raw_fecha:
                rejected.append({"row_index": idx, "reason": "campos_clave_faltantes"})
                continue
            if (cod_ine, folio) in seen:
                rejected.append({"row_index": idx, "reason": "duplicado_en_lote"})
                continue
            try:
                fecha = date.fromisoformat(raw_fecha[:10])
                monto = int(float(str(raw_monto)))
            except Exception:
                rejected.append({"row_index": idx, "reason": "fecha_o_monto_invalido"})
                continue
            if monto <= 0:
                rejected.append({"row_index": idx, "reason": "monto_no_positivo"})
                continue

            sup_raw = row.get(cols.get("superficie_m2", ""))
            sup: float | None = None
            precio_m2: float | None = None
            if sup_raw not in (None, ""):
                sup_val = float(str(sup_raw))
                if sup_val > 0:
                    sup = round(sup_val, 2)
                    precio_m2 = round(monto / sup_val, 2)

            seen.add((cod_ine, folio))
            valid.append(
                PreparedTransaccion(
                    row_index=idx,
                    codigo_f2890=folio,
                    codigo_ine=cod_ine,
                    rol=rol,
                    fecha=fecha,
                    monto_clp=monto,
                    superficie_m2=sup,
                    precio_m2_clp=precio_m2,
                    destino=str(row.get(cols.get("destino", "")) or "").strip(),
                )
            )

    return total, valid, rejected


def _aggregate_h3_cells(
    cur: psycopg.Cursor,
    fuente_id: int,
    fecha_corte: date,
    confianza: str,
    resolutions: list[int],
) -> tuple[int, int]:
    """Agrega transacciones geolocalizadas en celdas H3 (res. 7-9) y calcula ratios/tendencias."""
    cur.execute(
        """
        SELECT
            t.comuna_id,
            t.fecha,
            t.monto_clp,
            t.precio_m2_clp::double precision,
            p.avaluo_fiscal,
            ST_Y(ST_PointOnSurface(p.geom)) AS lat,
            ST_X(ST_PointOnSurface(p.geom)) AS lng
        FROM transaccion t
        JOIN parcela p ON p.id = t.parcela_id
        WHERE t.precio_m2_clp IS NOT NULL;
        """
    )
    rows = cur.fetchall()
    if not rows:
        return 0, 0

    buckets: dict[tuple[str, int, int], list[tuple[date, int, float, int | None]]] = {}
    for comuna_id, fecha, monto, precio_m2, avaluo, lat, lng in rows:
        for res in resolutions:
            h3_idx = h3.latlng_to_cell(float(lat), float(lng), res)
            buckets.setdefault((h3_idx, res, int(comuna_id)), []).append(
                (fecha, int(monto), float(precio_m2), int(avaluo) if avaluo else None)
            )

    inserted = 0
    updated = 0
    for (h3_idx, res, comuna_id), items in buckets.items():
        precios = [it[2] for it in items]
        mediana = round(statistics.median(precios), 2)
        promedio = round(statistics.mean(precios), 2)

        ratios = [it[1] / it[3] for it in items if it[3] and it[3] > 0]
        ratio_avg = round(statistics.mean(ratios), 3) if ratios else None

        ordered = sorted(items, key=lambda x: x[0])
        tendencia: float | None = None
        if len(ordered) >= 2 and ordered[0][0] != ordered[-1][0]:
            mid = len(ordered) // 2
            prev_avg = statistics.mean(it[2] for it in ordered[:mid])
            curr_avg = statistics.mean(it[2] for it in ordered[mid:])
            if prev_avg > 0:
                tendencia = round((curr_avg - prev_avg) / prev_avg * 100.0, 2)

        wkt = cell_to_polygon_wkt(h3_idx)
        cur.execute(
            """
            INSERT INTO celda_h3 (
                h3_index, resolucion, comuna_id, geom, cantidad_transacciones,
                precio_m2_mediana_clp, precio_m2_promedio_clp, ratio_precio_avaluo,
                tendencia_pct, fuente_id, fecha_corte, confianza, actualizado_en
            )
            VALUES (
                %s, %s, %s, ST_GeomFromText(%s, 4326), %s,
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (h3_index)
            DO UPDATE SET
                cantidad_transacciones = EXCLUDED.cantidad_transacciones,
                precio_m2_mediana_clp = EXCLUDED.precio_m2_mediana_clp,
                precio_m2_promedio_clp = EXCLUDED.precio_m2_promedio_clp,
                ratio_precio_avaluo = EXCLUDED.ratio_precio_avaluo,
                tendencia_pct = EXCLUDED.tendencia_pct,
                fuente_id = EXCLUDED.fuente_id,
                fecha_corte = EXCLUDED.fecha_corte,
                confianza = EXCLUDED.confianza,
                actualizado_en = NOW()
            WHERE (
                celda_h3.cantidad_transacciones,
                celda_h3.precio_m2_mediana_clp,
                celda_h3.precio_m2_promedio_clp,
                celda_h3.ratio_precio_avaluo,
                celda_h3.tendencia_pct
            ) IS DISTINCT FROM (
                EXCLUDED.cantidad_transacciones,
                EXCLUDED.precio_m2_mediana_clp,
                EXCLUDED.precio_m2_promedio_clp,
                EXCLUDED.ratio_precio_avaluo,
                EXCLUDED.tendencia_pct
            )
            RETURNING (xmax = 0) AS was_inserted;
            """,
            (
                h3_idx,
                res,
                comuna_id,
                wkt,
                len(items),
                mediana,
                promedio,
                ratio_avg,
                tendencia,
                fuente_id,
                fecha_corte,
                confianza,
            ),
        )
        res_row = cur.fetchone()
        if res_row:
            if res_row[0]:
                inserted += 1
            else:
                updated += 1

    return inserted, updated


def run_f2890_etl(
    config_path: str | Path,
    dsn: str | None = None,
    output_report: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta ETL idempotente de transacciones F2890 anonimizadas y agrega celdas H3."""
    raw_cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    csv_path = _resolve_path(str(raw_cfg["input_path"]))
    resolutions = [int(r) for r in raw_cfg.get("resolutions", [7, 8, 9])]
    f_raw = raw_cfg["fuente"]
    fuente = FuenteConfig(
        nombre=str(f_raw["nombre"]),
        origen=str(f_raw["origen"]),
        licencia=str(f_raw["licencia"]),
        fecha_corte=str(f_raw["fecha_corte"]),
        confianza_defecto=str(f_raw.get("confianza_defecto", "media")),
        url=str(f_raw.get("url", "")),
        version_etl=str(f_raw.get("version_etl", "1.0.0")),
    )
    fecha_corte = date.fromisoformat(fuente.fecha_corte)
    file_hash = compute_source_hash(str(csv_path))
    total_read, prepared, rejected = parse_f2890_csv(csv_path, raw_cfg["columns"])

    with psycopg.connect(dsn or get_db_dsn()) as conn:
        with conn.cursor() as cur:
            fuente_id = upsert_fuente(cur, fuente, file_hash, total_read)
            cur.execute(
                """
                CREATE TEMP TABLE tmp_f2890_stage (
                    row_index integer NOT NULL,
                    codigo_f2890 varchar(64) NOT NULL,
                    codigo_ine varchar(10) NOT NULL,
                    rol varchar(32) NOT NULL,
                    fecha date NOT NULL,
                    monto_clp bigint NOT NULL,
                    superficie_m2 numeric(14, 2),
                    precio_m2_clp numeric(14, 2),
                    destino varchar(80) NOT NULL
                ) ON COMMIT DROP;
                """
            )
            cur.executemany(
                "INSERT INTO tmp_f2890_stage VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
                [
                    (
                        r.row_index,
                        r.codigo_f2890,
                        r.codigo_ine,
                        r.rol,
                        r.fecha,
                        r.monto_clp,
                        r.superficie_m2,
                        r.precio_m2_clp,
                        r.destino,
                    )
                    for r in prepared
                ],
            )
            cur.execute(
                """
                SELECT s.row_index FROM tmp_f2890_stage s
                LEFT JOIN comuna c ON c.codigo_ine = s.codigo_ine
                WHERE c.id IS NULL;
                """
            )
            missing_com = [
                {"row_index": int(r[0]), "reason": "comuna_no_encontrada"} for r in cur.fetchall()
            ]
            rejected.extend(missing_com)

            cur.execute(
                """
                SELECT DISTINCT
                    s.codigo_f2890,
                    c.id AS comuna_id,
                    p.id AS parcela_id,
                    s.rol,
                    s.fecha,
                    s.monto_clp,
                    s.superficie_m2,
                    s.precio_m2_clp,
                    s.destino,
                    ST_Y(ST_PointOnSurface(p.geom)) AS lat,
                    ST_X(ST_PointOnSurface(p.geom)) AS lng
                FROM tmp_f2890_stage s
                JOIN comuna c ON c.codigo_ine = s.codigo_ine
                LEFT JOIN LATERAL (
                    SELECT p2.id, p2.geom
                    FROM parcela p2
                    WHERE p2.comuna_id = c.id AND p2.rol = s.rol
                    ORDER BY (p2.vigente_hasta IS NULL) DESC, p2.vigente_desde DESC
                    LIMIT 1
                ) p ON true;
                """
            )
            resolved_rows = cur.fetchall()

            ins = 0
            upd = 0
            for (
                folio,
                comuna_id,
                parcela_id,
                rol,
                fecha,
                monto,
                sup,
                precio_m2,
                destino,
                lat,
                lng,
            ) in resolved_rows:
                h3_res8 = (
                    h3.latlng_to_cell(float(lat), float(lng), 8)
                    if lat is not None and lng is not None
                    else ""
                )
                cur.execute(
                    """
                    INSERT INTO transaccion (
                        codigo_f2890, comuna_id, parcela_id, rol, fecha, monto_clp,
                        superficie_m2, precio_m2_clp, destino, h3_res8,
                        fuente_id, fecha_corte, confianza
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (comuna_id, codigo_f2890)
                    DO UPDATE SET
                        parcela_id = EXCLUDED.parcela_id,
                        rol = EXCLUDED.rol,
                        fecha = EXCLUDED.fecha,
                        monto_clp = EXCLUDED.monto_clp,
                        superficie_m2 = EXCLUDED.superficie_m2,
                        precio_m2_clp = EXCLUDED.precio_m2_clp,
                        destino = EXCLUDED.destino,
                        h3_res8 = EXCLUDED.h3_res8,
                        fuente_id = EXCLUDED.fuente_id,
                        fecha_corte = EXCLUDED.fecha_corte,
                        confianza = EXCLUDED.confianza
                    WHERE (
                        transaccion.parcela_id,
                        transaccion.monto_clp,
                        transaccion.superficie_m2,
                        transaccion.precio_m2_clp,
                        transaccion.h3_res8,
                        transaccion.fuente_id
                    ) IS DISTINCT FROM (
                        EXCLUDED.parcela_id,
                        EXCLUDED.monto_clp,
                        EXCLUDED.superficie_m2,
                        EXCLUDED.precio_m2_clp,
                        EXCLUDED.h3_res8,
                        EXCLUDED.fuente_id
                    )
                    RETURNING (xmax = 0) AS was_inserted;
                    """,
                    (
                        folio,
                        comuna_id,
                        parcela_id,
                        rol,
                        fecha,
                        monto,
                        sup,
                        precio_m2,
                        destino,
                        h3_res8,
                        fuente_id,
                        fecha_corte,
                        fuente.confianza_defecto,
                    ),
                )
                res_tx = cur.fetchone()
                if res_tx:
                    if res_tx[0]:
                        ins += 1
                    else:
                        upd += 1

            h3_ins, h3_upd = _aggregate_h3_cells(
                cur, fuente_id, fecha_corte, fuente.confianza_defecto, resolutions
            )
        conn.commit()

    unch = max(0, len(resolved_rows) - ins - upd)
    report = {
        "fuente_id": fuente_id,
        "fuente_nombre": fuente.nombre,
        "hash_archivo": file_hash,
        "counts": {
            "leidas": total_read,
            "aceptadas": len(resolved_rows),
            "insertadas": ins,
            "actualizadas": upd,
            "sin_cambios": unch,
            "rechazadas": len(rejected),
        },
        "h3": {"insertadas": h3_ins, "actualizadas": h3_upd, "resoluciones": resolutions},
        "rechazadas_detalle": rejected,
    }
    if output_report:
        out = Path(output_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL idempotente F2890 + agregación H3")
    parser.add_argument("--config", required=True, help="Ruta YAML F2890")
    parser.add_argument(
        "--output-report",
        default="etl/output/f2890_quality_report.json",
        help="Ruta del reporte JSON",
    )
    args = parser.parse_args()
    print(json.dumps(run_f2890_etl(args.config, output_report=args.output_report), indent=2))


if __name__ == "__main__":
    main()
