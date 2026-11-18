#!/usr/bin/env bash
set -euo pipefail

# Genera PMTiles para capas estáticas (ej. límites comunales) usando tippecanoe.
# Si tippecanoe no está instalado localmente, usa la imagen oficial vía Docker.

INPUT="${1:-etl/fixtures/comuna_la_serena_limite.geojson}"
OUTPUT="${2:-infra/pmtiles/out/limites_comunales.pmtiles}"
LAYER_NAME="${3:-limites_comunales}"

mkdir -p "$(dirname "$OUTPUT")"

if command -v tippecanoe >/dev/null 2>&1; then
  tippecanoe -zg -o "$OUTPUT" -l "$LAYER_NAME" --drop-densest-as-needed --force "$INPUT"
else
  docker run --rm -v "$(pwd):/data" -w /data \
    ghcr.io/felt/tippecanoe:latest \
    tippecanoe -zg -o "$OUTPUT" -l "$LAYER_NAME" --drop-densest-as-needed --force "$INPUT"
fi

echo "PMTiles generado en $OUTPUT"
