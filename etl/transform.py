import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from etl.config import ETLConfig


@dataclass(frozen=True)
class PreparedParcela:
    """Registro validado y normalizado en EPSG:4326 listo para carga masiva."""

    row_index: int
    codigo_ine: str
    rol: str
    ewkt: str
    superficie_declarada: float | None
    destino: str
    serie: str
    avaluo_fiscal: int | None
    fecha_corte: date
    confianza_geom: str
    vigente_desde: date
    vigente_hasta: date | None
    was_repaired: bool


@dataclass(frozen=True)
class RejectedRow:
    """Registro rechazado con motivo explícito para el reporte de calidad."""

    row_index: int
    rol: str | None
    codigo_ine: str | None
    reason: str


@dataclass(frozen=True)
class TransformResult:
    """Resultado de lectura, validación, reparación y deduplicación."""

    file_hash: str
    total_read: int
    valid_rows: list[PreparedParcela]
    rejected_rows: list[RejectedRow]
    repaired_count: int


def compute_source_hash(input_path: str) -> str:
    """Calcula SHA-256 si es archivo local, o hash determinista de la URI si es fuente remota."""
    path = Path(input_path)
    if path.exists() and path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    return hashlib.sha256(input_path.encode("utf-8")).hexdigest()


def read_spatial_path(
    input_path: str,
    source_crs: str,
    layer: str | None = None,
) -> gpd.GeoDataFrame:
    """Lee un archivo espacial (GPKG/SHP/GeoJSON) o WFS usando pyogrio/GeoJSON tolerante."""
    path = Path(input_path)
    if path.suffix.lower() in {".geojson", ".json"} and path.exists():
        # Lectura tolerante en GeoJSON para capturar anillos sin cerrar u otras anomalías por fila.
        return _read_geojson_tolerant(path, source_crs)

    read_kwargs: dict[str, Any] = {"engine": "pyogrio"}
    if layer:
        read_kwargs["layer"] = layer
    gdf = gpd.read_file(input_path, **read_kwargs)
    if gdf.crs is None:
        gdf = gdf.set_crs(source_crs, allow_override=True)
    return gdf


def read_spatial_source(config: ETLConfig) -> gpd.GeoDataFrame:
    """Lee un archivo espacial desde la configuración de parcelas."""
    return read_spatial_path(config.input_path, config.source_crs, config.layer)


def normalize_reproject_polygon(
    geom: BaseGeometry | None,
    transformer: Transformer,
    raw_err: Any = None,
) -> tuple[MultiPolygon | None, bool, str | None]:
    """Valida, repara con make_valid y reproyecta a MultiPolygon EPSG:4326."""
    if isinstance(raw_err, str) and raw_err:
        return None, False, raw_err
    if geom is None or geom.is_empty:
        return None, False, "geometria_vacia"

    was_repaired = False
    if not geom.is_valid:
        geom = make_valid(geom)
        was_repaired = True

    multipoly = _to_multipolygon(geom)
    if multipoly is None or not multipoly.is_valid:
        return None, was_repaired, "geometria_invalida_irreparable"

    reprojected = shapely_transform(transformer.transform, multipoly)
    reprojected_multi = _to_multipolygon(reprojected)
    if reprojected_multi is None or not reprojected_multi.is_valid:
        return None, was_repaired, "geometria_invalida_post_reproyeccion"

    return reprojected_multi, was_repaired, None


def _read_geojson_tolerant(path: Path, source_crs: str) -> gpd.GeoDataFrame:
    """Lee GeoJSON feature por feature tolerando geometrías inválidas o anillos abiertos."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    rows: list[dict[str, Any]] = []
    geometries: list[BaseGeometry | None] = []
    invalid_reasons: list[str | None] = []

    for feat in features:
        props = dict(feat.get("properties") or {})
        raw_geom = feat.get("geometry")
        geom: BaseGeometry | None = None
        reason: str | None = None
        if raw_geom is None:
            reason = "geometria_nula"
        else:
            reason = _check_raw_geojson_rings(raw_geom)
            if reason is None:
                try:
                    geom = shape(raw_geom)
                except Exception:
                    reason = "geometria_no_parseable"
        rows.append(props)
        geometries.append(geom)
        invalid_reasons.append(reason)

    df = pd.DataFrame(rows)
    df["_raw_geom_error"] = invalid_reasons
    return gpd.GeoDataFrame(df, geometry=geometries, crs=source_crs)


def _check_raw_geojson_rings(raw_geom: dict[str, Any]) -> str | None:
    """Detecta anillos sin cerrar antes de que Shapely los cierre implícitamente."""
    gtype = raw_geom.get("type")
    coords = raw_geom.get("coordinates")
    if not coords:
        return "geometria_vacia"

    rings: list[list[Any]] = []
    if gtype == "Polygon":
        rings = coords
    elif gtype == "MultiPolygon":
        for poly in coords:
            rings.extend(poly)
    else:
        return None

    for ring in rings:
        if len(ring) < 4:
            return "anillo_pocos_vertices"
        if ring[0][:2] != ring[-1][:2]:
            return "anillo_sin_cerrar"
    return None


def _normalize_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parse_optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return float(value)


def _parse_optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return int(float(value))


def _parse_date(value: Any, fallback: date | None = None) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return fallback
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


def _normalize_serie(value: Any) -> str:
    raw = _normalize_str(value).lower()
    if raw in {"agricola", "agrícola", "a"}:
        return "agricola"
    if raw in {"no_agricola", "no agrícola", "no agricola", "n"}:
        return "no_agricola"
    return "desconocida"


def _to_multipolygon(geom: BaseGeometry) -> MultiPolygon | None:
    """Extrae polígonos de área positiva y retorna un MultiPolygon."""
    if geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return MultiPolygon([geom]) if geom.area > 0 else None
    if isinstance(geom, MultiPolygon):
        polys = [p for p in geom.geoms if not p.is_empty and p.area > 0]
        return MultiPolygon(polys) if polys else None
    if hasattr(geom, "geoms"):
        polys: list[Polygon] = []
        for part in geom.geoms:
            if isinstance(part, Polygon) and part.area > 0:
                polys.append(part)
            elif isinstance(part, MultiPolygon):
                polys.extend(p for p in part.geoms if p.area > 0)
        return MultiPolygon(polys) if polys else None
    return None


def transform_parcelas(gdf: gpd.GeoDataFrame, config: ETLConfig, file_hash: str) -> TransformResult:
    """Valida atributos, repara geometrías, reproyecta a EPSG:4326 y deduplica por clave natural."""
    cols = config.columns
    fecha_corte = date.fromisoformat(config.fuente.fecha_corte)
    default_vig = _parse_date(config.default_vigente_desde, fallback=fecha_corte)

    transformer = Transformer.from_crs(config.source_crs, "EPSG:4326", always_xy=True)

    valid_rows: list[PreparedParcela] = []
    rejected_rows: list[RejectedRow] = []
    repaired_count = 0
    seen_keys: set[tuple[str, str, date]] = set()

    has_raw_error_col = "_raw_geom_error" in gdf.columns

    for idx, row in gdf.iterrows():
        row_num = int(idx) if isinstance(idx, int) else len(valid_rows) + len(rejected_rows)
        codigo_ine = _normalize_str(row.get(cols.codigo_ine))
        rol = _normalize_str(row.get(cols.rol))

        if not codigo_ine:
            rejected_rows.append(RejectedRow(row_num, rol or None, None, "comuna_faltante"))
            continue
        if not rol:
            rejected_rows.append(RejectedRow(row_num, None, codigo_ine, "rol_faltante"))
            continue

        vigente_desde = _parse_date(
            row.get(cols.vigente_desde) if cols.vigente_desde else None,
            fallback=default_vig,
        )
        if vigente_desde is None:
            rejected_rows.append(RejectedRow(row_num, rol, codigo_ine, "vigente_desde_faltante"))
            continue

        key = (codigo_ine, rol, vigente_desde)
        if key in seen_keys:
            rejected_rows.append(RejectedRow(row_num, rol, codigo_ine, "duplicado_en_lote"))
            continue

        raw_err = row.get("_raw_geom_error") if has_raw_error_col else None
        reprojected_multi, was_repaired, geom_err = normalize_reproject_polygon(
            row.geometry, transformer, raw_err
        )
        if geom_err or reprojected_multi is None:
            rejected_rows.append(RejectedRow(row_num, rol, codigo_ine, geom_err or "geom_error"))
            continue

        seen_keys.add(key)
        if was_repaired:
            repaired_count += 1

        vigente_hasta = _parse_date(
            row.get(cols.vigente_hasta) if cols.vigente_hasta else None,
            fallback=None,
        )
        superficie_decl = _parse_optional_float(
            row.get(cols.superficie_declarada) if cols.superficie_declarada else None
        )
        avaluo = _parse_optional_int(
            row.get(cols.avaluo_fiscal) if cols.avaluo_fiscal else None
        )

        valid_rows.append(
            PreparedParcela(
                row_index=row_num,
                codigo_ine=codigo_ine,
                rol=rol,
                ewkt=f"SRID=4326;{reprojected_multi.wkt}",
                superficie_declarada=superficie_decl,
                destino=_normalize_str(row.get(cols.destino) if cols.destino else ""),
                serie=_normalize_serie(row.get(cols.serie) if cols.serie else ""),
                avaluo_fiscal=avaluo,
                fecha_corte=fecha_corte,
                confianza_geom=config.fuente.confianza_defecto,
                vigente_desde=vigente_desde,
                vigente_hasta=vigente_hasta,
                was_repaired=was_repaired,
            )
        )

    return TransformResult(
        file_hash=file_hash,
        total_read=len(gdf),
        valid_rows=valid_rows,
        rejected_rows=rejected_rows,
        repaired_count=repaired_count,
    )
