import json
import re
from typing import Any

from django.db import connection

COORD_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$"
)

BASE_PARCELA_SELECT = """
    SELECT
        p.id,
        p.rol,
        c.codigo_ine,
        c.nombre,
        p.region_id,
        p.superficie_m2,
        p.superficie_declarada,
        p.diferencia_superficie_pct,
        p.destino,
        p.serie,
        p.avaluo_fiscal,
        p.vigente_desde,
        p.vigente_hasta,
        ST_X(ST_PointOnSurface(p.geom)) AS lng,
        ST_Y(ST_PointOnSurface(p.geom)) AS lat,
        f.nombre,
        f.origen,
        f.licencia,
        p.fecha_corte,
        p.confianza_geom
    FROM parcela p
    JOIN comuna c ON c.id = p.comuna_id
    JOIN fuente_dato f ON f.id = p.fuente_id
"""


def _build_procedencia(
    fuente: str,
    origen: str,
    licencia: str,
    fecha_corte: Any,
    confianza: str,
) -> dict[str, Any]:
    return {
        "fuente": fuente,
        "origen": origen,
        "licencia": licencia,
        "fecha_corte": fecha_corte.isoformat() if fecha_corte else None,
        "confianza": confianza,
    }


def _ensure_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def calcular_cabida_referencial(
    superficie_m2: float | None,
    parametros: dict[str, Any] | str | None,
) -> dict[str, Any] | None:
    """Estima cabida constructiva referencial según coeficientes urbanísticos de la zona."""
    parsed = _ensure_json(parametros, None)
    if superficie_m2 is None or superficie_m2 <= 0 or not parsed:
        return None

    coef_ocup = parsed.get("coef_ocupacion_suelo")
    coef_const = parsed.get("coef_constructibilidad")
    sup_min = parsed.get("superficie_predial_min_m2")
    altura_max = parsed.get("altura_max_m")

    return {
        "ocupacion_max_m2": (
            round(superficie_m2 * float(coef_ocup), 2) if coef_ocup is not None else None
        ),
        "edificabilidad_max_m2": (
            round(superficie_m2 * float(coef_const), 2) if coef_const is not None else None
        ),
        "altura_max_m": float(altura_max) if altura_max is not None else None,
        "superficie_predial_min_m2": float(sup_min) if sup_min is not None else None,
        "cumple_superficie_min": (
            superficie_m2 >= float(sup_min) if sup_min is not None else None
        ),
        "descargo": (
            "Cabida estimada referencial; no reemplaza Certificado de Informaciones Previas (CIP)."
        ),
    }


def validate_coordinates(lat: float, lng: float) -> tuple[float, float]:
    """Valida latitud y longitud en EPSG:4326."""
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        raise ValueError("Coordenadas fuera de rango válido (lat [-90,90], lng [-180,180]).")
    return lat, lng


def _serialize_parcela_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "rol": row[1],
        "comuna": {
            "codigo_ine": row[2],
            "nombre": row[3],
            "region_id": row[4],
        },
        "superficie_m2": float(row[5]) if row[5] is not None else None,
        "superficie_declarada": float(row[6]) if row[6] is not None else None,
        "diferencia_superficie_pct": float(row[7]) if row[7] is not None else None,
        "destino": row[8],
        "serie": row[9],
        "avaluo_fiscal": row[10],
        "vigente_desde": row[11].isoformat() if row[11] else None,
        "vigente_hasta": row[12].isoformat() if row[12] else None,
        "centroide": {"lng": float(row[13]), "lat": float(row[14])},
        "procedencia": _build_procedencia(row[15], row[16], row[17], row[18], row[19]),
    }


def lookup_parcela_by_point(lat: float, lng: float) -> dict[str, Any] | None:
    """Consulta punto -> parcela usando índice GiST (sin devolver geometría pesada)."""
    validate_coordinates(lat, lng)
    sql = (
        BASE_PARCELA_SELECT
        + """
        WHERE ST_Intersects(p.geom, ST_SetSRID(ST_Point(%s, %s), 4326))
        ORDER BY (p.vigente_hasta IS NULL) DESC, p.vigente_desde DESC
        LIMIT 1;
        """
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [lng, lat])
        row = cursor.fetchone()
    return _serialize_parcela_row(row) if row else None


def search_parcelas(query: str, limit: int = 10) -> dict[str, Any]:
    """Busca parcelas por coordenadas o por rol / alias de rol (pg_trgm)."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("El parámetro de búsqueda 'q' es obligatorio.")

    match = COORD_PATTERN.match(cleaned)
    if match:
        lat = float(match.group(1))
        lng = float(match.group(2))
        item = lookup_parcela_by_point(lat, lng)
        return {
            "tipo": "coordenadas",
            "query": cleaned,
            "resultados": [item] if item else [],
        }

    safe_limit = max(1, min(limit, 50))
    sql = (
        BASE_PARCELA_SELECT
        + """
        WHERE p.rol ILIKE %s
           OR EXISTS (
               SELECT 1
               FROM parcela_alias_rol a
               WHERE a.comuna_id = p.comuna_id
                 AND a.rol_actual = p.rol
                 AND a.rol_anterior ILIKE %s
           )
        ORDER BY (p.rol = %s) DESC, (p.vigente_hasta IS NULL) DESC, p.vigente_desde DESC
        LIMIT %s;
        """
    )
    pattern = f"%{cleaned}%"
    with connection.cursor() as cursor:
        cursor.execute(sql, [pattern, pattern, cleaned, safe_limit])
        rows = cursor.fetchall()

    return {
        "tipo": "rol",
        "query": cleaned,
        "resultados": [_serialize_parcela_row(r) for r in rows],
    }


def get_parcela_ficha_completa(parcela_id: int) -> dict[str, Any] | None:
    """Cruza espacialmente parcela con estatus fiscal, normativa, riesgos y relieve."""
    with connection.cursor() as cursor:
        cursor.execute(BASE_PARCELA_SELECT + " WHERE p.id = %s;", [parcela_id])
        base_row = cursor.fetchone()
        if not base_row:
            return None
        parcela = _serialize_parcela_row(base_row)
        superficie_m2 = parcela["superficie_m2"]

        # Relieve y procedencia DEM de la parcela.
        cursor.execute(
            """
            SELECT
                p.elevacion_media_m,
                p.pendiente_media_pct,
                p.exposicion_aspecto,
                fr.nombre,
                fr.origen,
                fr.licencia,
                p.fecha_corte_relieve,
                p.confianza_relieve
            FROM parcela p
            LEFT JOIN fuente_dato fr ON fr.id = p.fuente_relieve_id
            WHERE p.id = %s;
            """,
            [parcela_id],
        )
        rel_row = cursor.fetchone()

        # Estatus fiscal (Bienes Nacionales / Fisco).
        cursor.execute(
            """
            SELECT
                tf.codigo_bn,
                tf.institucion,
                tf.tipo,
                ROUND(
                    (
                        ST_Area(ST_Intersection(p.geom, tf.geom)::geography)
                        / NULLIF(ST_Area(p.geom::geography), 0)
                        * 100.0
                    )::numeric,
                    2
                )::double precision AS traslape_pct,
                f.nombre,
                f.origen,
                f.licencia,
                tf.fecha_corte,
                tf.confianza
            FROM parcela p
            JOIN terreno_fiscal tf ON ST_Intersects(p.geom, tf.geom)
            JOIN fuente_dato f ON f.id = tf.fuente_id
            WHERE p.id = %s
              AND tf.vigente_hasta IS NULL
            ORDER BY traslape_pct DESC;
            """,
            [parcela_id],
        )
        fiscal_rows = cursor.fetchall()

        # Normativa urbana (PRC / PRI / PRMS).
        cursor.execute(
            """
            SELECT
                cn.instrumento,
                cn.codigo_zona,
                cn.nombre_zona,
                cn.usos_permitidos,
                cn.parametros_urbanisticos,
                ROUND(
                    (
                        ST_Area(ST_Intersection(p.geom, cn.geom)::geography)
                        / NULLIF(ST_Area(p.geom::geography), 0)
                        * 100.0
                    )::numeric,
                    2
                )::double precision AS traslape_pct,
                f.nombre,
                f.origen,
                f.licencia,
                cn.fecha_corte,
                cn.confianza
            FROM parcela p
            JOIN capa_normativa cn ON ST_Intersects(p.geom, cn.geom)
            JOIN fuente_dato f ON f.id = cn.fuente_id
            WHERE p.id = %s
              AND cn.vigente_hasta IS NULL
            ORDER BY traslape_pct DESC;
            """,
            [parcela_id],
        )
        norm_rows = cursor.fetchall()

        # Amenazas y riesgos naturales.
        cursor.execute(
            """
            SELECT
                cr.codigo_evento,
                cr.tipo,
                cr.nivel,
                cr.descripcion,
                ROUND(
                    (
                        ST_Area(ST_Intersection(p.geom, cr.geom)::geography)
                        / NULLIF(ST_Area(p.geom::geography), 0)
                        * 100.0
                    )::numeric,
                    2
                )::double precision AS afectacion_pct,
                f.nombre,
                f.origen,
                f.licencia,
                cr.fecha_corte,
                cr.confianza
            FROM parcela p
            JOIN capa_riesgo cr ON ST_Intersects(p.geom, cr.geom)
            JOIN fuente_dato f ON f.id = cr.fuente_id
            WHERE p.id = %s
            ORDER BY CASE cr.nivel
                WHEN 'alto' THEN 1
                WHEN 'restriccion' THEN 2
                WHEN 'medio' THEN 3
                ELSE 4
            END, afectacion_pct DESC;
            """,
            [parcela_id],
        )
        riesgo_rows = cursor.fetchall()

    relieve = None
    if rel_row and rel_row[0] is not None:
        relieve = {
            "elevacion_media_m": float(rel_row[0]),
            "pendiente_media_pct": float(rel_row[1]) if rel_row[1] is not None else None,
            "exposicion_aspecto": rel_row[2],
            "procedencia": (
                _build_procedencia(rel_row[3], rel_row[4], rel_row[5], rel_row[6], rel_row[7])
                if rel_row[3]
                else None
            ),
        }

    fiscal_items = [
        {
            "codigo_bn": r[0],
            "institucion": r[1],
            "tipo": r[2],
            "porcentaje_traslape": float(r[3]) if r[3] is not None else None,
            "procedencia": _build_procedencia(r[4], r[5], r[6], r[7], r[8]),
        }
        for r in fiscal_rows
    ]

    normativa_items = [
        {
            "instrumento": r[0],
            "codigo_zona": r[1],
            "nombre_zona": r[2],
            "usos_permitidos": _ensure_json(r[3], []),
            "parametros_urbanisticos": _ensure_json(r[4], {}),
            "porcentaje_traslape": float(r[5]) if r[5] is not None else None,
            "cabida_referencial": calcular_cabida_referencial(superficie_m2, r[4]),
            "procedencia": _build_procedencia(r[6], r[7], r[8], r[9], r[10]),
        }
        for r in norm_rows
    ]

    riesgo_items = [
        {
            "codigo_evento": r[0],
            "tipo": r[1],
            "nivel": r[2],
            "descripcion": r[3],
            "porcentaje_afectacion": float(r[4]) if r[4] is not None else None,
            "procedencia": _build_procedencia(r[5], r[6], r[7], r[8], r[9]),
        }
        for r in riesgo_rows
    ]

    return {
        "identificacion": parcela,
        "estatus_fiscal": {
            "es_fiscal": len(fiscal_items) > 0,
            "coincidencias": fiscal_items,
        },
        "normativa": normativa_items,
        "riesgos": riesgo_items,
        "relieve": relieve,
        "descargo_general": (
            "Información territorial de carácter referencial. No acredita deslindes ni "
            "reemplaza escrituras, certificados de dominio o Certificados de Informaciones Previas."
        ),
    }
