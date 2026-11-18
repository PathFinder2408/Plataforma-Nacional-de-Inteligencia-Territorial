from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ColumnMapping:
    """Mapeo configurable desde columnas del archivo fuente hacia el esquema canónico."""

    rol: str
    codigo_ine: str
    destino: str | None = None
    serie: str | None = None
    avaluo_fiscal: str | None = None
    superficie_declarada: str | None = None
    vigente_desde: str | None = None
    vigente_hasta: str | None = None


@dataclass(frozen=True)
class FuenteConfig:
    """Metadatos de procedencia y licencia para registrar en FuenteDato."""

    nombre: str
    origen: str
    licencia: str
    fecha_corte: str
    confianza_defecto: str = "referencial"
    url: str = ""
    version_etl: str = "1.0.0"


@dataclass(frozen=True)
class ETLConfig:
    """Configuración completa de una ejecución ETL."""

    input_path: str
    source_crs: str
    fuente: FuenteConfig
    columns: ColumnMapping
    layer: str | None = None
    default_vigente_desde: str | None = None
    area_diff_threshold_pct: float = 10.0
    batch_size: int = 1000
    extra: dict[str, Any] = field(default_factory=dict)


def load_etl_config(config_path: str | Path) -> ETLConfig:
    """Carga y valida la configuración YAML del ETL."""
    path = Path(config_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Configuración YAML inválida en {path}")

    fuente_raw = raw["fuente"]
    cols_raw = raw["columns"]
    raw_input = str(raw["input_path"])
    if not raw_input.startswith(("http://", "https://", "WFS:")):
        candidate = Path(raw_input)
        if not candidate.exists():
            repo_candidate = Path(__file__).resolve().parent.parent / raw_input
            if repo_candidate.exists():
                raw_input = str(repo_candidate)

    return ETLConfig(
        input_path=raw_input,
        source_crs=str(raw["source_crs"]),
        layer=raw.get("layer"),
        default_vigente_desde=raw.get("default_vigente_desde"),
        area_diff_threshold_pct=float(raw.get("area_diff_threshold_pct", 10.0)),
        batch_size=int(raw.get("batch_size", 1000)),
        fuente=FuenteConfig(
            nombre=str(fuente_raw["nombre"]),
            origen=str(fuente_raw["origen"]),
            licencia=str(fuente_raw["licencia"]),
            fecha_corte=str(fuente_raw["fecha_corte"]),
            confianza_defecto=str(fuente_raw.get("confianza_defecto", "referencial")),
            url=str(fuente_raw.get("url", "")),
            version_etl=str(fuente_raw.get("version_etl", "1.0.0")),
        ),
        columns=ColumnMapping(
            rol=str(cols_raw["rol"]),
            codigo_ine=str(cols_raw["codigo_ine"]),
            destino=cols_raw.get("destino"),
            serie=cols_raw.get("serie"),
            avaluo_fiscal=cols_raw.get("avaluo_fiscal"),
            superficie_declarada=cols_raw.get("superficie_declarada"),
            vigente_desde=cols_raw.get("vigente_desde"),
            vigente_hasta=cols_raw.get("vigente_hasta"),
        ),
    )
