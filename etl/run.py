import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etl.config import ETLConfig, load_etl_config
from etl.loader import LoadStats, get_db_dsn, load_parcelas_idempotent
from etl.transform import (
    RejectedRow,
    TransformResult,
    compute_source_hash,
    read_spatial_source,
    transform_parcelas,
)


def build_quality_report(
    config: ETLConfig,
    transform_res: TransformResult,
    load_stats: LoadStats,
) -> dict[str, Any]:
    """Construye el reporte de calidad estructurado de la ejecución ETL."""
    all_rejected: list[RejectedRow] = [
        *transform_res.rejected_rows,
        *load_stats.rejected_missing_comuna,
    ]
    accepted = len(transform_res.valid_rows) - len(load_stats.rejected_missing_comuna)
    return {
        "executed_at": datetime.now(UTC).isoformat(),
        "fuente_id": load_stats.fuente_id,
        "fuente_nombre": config.fuente.nombre,
        "input_path": config.input_path,
        "hash_archivo": transform_res.file_hash,
        "source_crs": config.source_crs,
        "target_crs": "EPSG:4326",
        "area_diff_threshold_pct": config.area_diff_threshold_pct,
        "counts": {
            "leidas": transform_res.total_read,
            "aceptadas": accepted,
            "corregidas": transform_res.repaired_count,
            "insertadas": load_stats.inserted,
            "actualizadas": load_stats.updated,
            "sin_cambios": load_stats.unchanged,
            "rechazadas": len(all_rejected),
        },
        "rechazadas_detalle": [asdict(r) for r in all_rejected],
        "alertas_superficie": [asdict(a) for a in load_stats.area_alerts],
    }


def run_etl(
    config_path: str | Path,
    output_report: str | Path | None = None,
    dsn: str | None = None,
) -> dict[str, Any]:
    """Ejecuta el pipeline ETL completo y opcionalmente guarda el reporte JSON."""
    config = load_etl_config(config_path)
    file_hash = compute_source_hash(config.input_path)
    gdf = read_spatial_source(config)
    transform_res = transform_parcelas(gdf, config, file_hash)
    load_stats = load_parcelas_idempotent(
        dsn=dsn or get_db_dsn(),
        config=config,
        file_hash=file_hash,
        total_read=transform_res.total_read,
        rows=transform_res.valid_rows,
    )
    report = build_quality_report(config, transform_res, load_stats)

    if output_report:
        out_path = Path(output_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL idempotente de parcelas catastrales")
    parser.add_argument("--config", required=True, help="Ruta al archivo YAML de configuración")
    parser.add_argument(
        "--output-report",
        default="etl/output/quality_report.json",
        help="Ruta de salida para el reporte JSON de calidad",
    )
    args = parser.parse_args()
    report = run_etl(args.config, args.output_report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
