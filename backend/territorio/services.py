import re
from typing import Any

from django.db import connection

COORD_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$"
)


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
        "procedencia": {
            "fuente": row[15],
            "origen": row[16],
            "licencia": row[17],
            "fecha_corte": row[18].isoformat() if row[18] else None,
            "confianza": row[19],
        },
    }


def lookup_parcela_by_point(lat: float, lng: float) -> dict[str, Any] | None:
    """Consulta punto -> parcela usando índice GiST (sin devolver geometría pesada)."""
    validate_coordinates(lat, lng)
    sql = """
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
        WHERE ST_Intersects(p.geom, ST_SetSRID(ST_Point(%s, %s), 4326))
        ORDER BY (p.vigente_hasta IS NULL) DESC, p.vigente_desde DESC
        LIMIT 1;
    """
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
    sql = """
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
    pattern = f"%{cleaned}%"
    with connection.cursor() as cursor:
        cursor.execute(sql, [pattern, pattern, cleaned, safe_limit])
        rows = cursor.fetchall()

    return {
        "tipo": "rol",
        "query": cleaned,
        "resultados": [_serialize_parcela_row(r) for r in rows],
    }
