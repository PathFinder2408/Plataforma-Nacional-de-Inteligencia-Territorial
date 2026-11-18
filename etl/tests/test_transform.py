from pathlib import Path

from shapely import wkt

from etl.config import load_etl_config
from etl.transform import compute_source_hash, read_spatial_source, transform_parcelas

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "etl" / "configs" / "la_serena_sintetico.yaml"


def test_transform_la_serena_sintetico() -> None:
    config = load_etl_config(CONFIG_PATH)
    file_hash = compute_source_hash(config.input_path)
    gdf = read_spatial_source(config)

    res = transform_parcelas(gdf, config, file_hash)

    assert res.total_read == 7
    assert len(res.valid_rows) == 4
    assert res.repaired_count == 1
    assert len(res.rejected_rows) == 3

    reasons = {r.reason for r in res.rejected_rows}
    assert reasons == {"anillo_sin_cerrar", "duplicado_en_lote", "comuna_faltante"}

    # Verifica que el mismo rol con distinta vigencia temporal fue aceptado dos veces.
    vigencias_001 = {r.vigente_desde.isoformat() for r in res.valid_rows if r.rol == "00101-00001"}
    assert vigencias_001 == {"2025-01-01", "2026-01-01"}

    # Verifica reproyección EPSG:32719 -> EPSG:4326 en zona de La Serena (~ -71.25, -29.90).
    sample_geom = wkt.loads(res.valid_rows[0].ewkt.split(";", 1)[1])
    minx, miny, maxx, maxy = sample_geom.bounds
    assert -71.5 < minx < maxx < -71.0
    assert -30.1 < miny < maxy < -29.7
    assert sample_geom.geom_type == "MultiPolygon"
    assert sample_geom.is_valid
