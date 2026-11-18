param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "migrate", "etl", "etl-layers", "etl-f2890", "test")]
    [string]$Task = "up"
)

switch ($Task) {
    "up"      { docker compose up -d --build }
    "down"    { docker compose down }
    "migrate" { docker compose exec backend uv run python manage.py migrate }
    "etl"     {
        docker compose exec -w /app backend uv run python -m etl.seed
        docker compose exec -w /app backend uv run python -m etl.run --config etl/configs/la_serena_sintetico.yaml
    }
    "etl-layers" {
        docker compose exec -w /app backend uv run python -m etl.layers --config etl/configs/la_serena_capas_estado.yaml
    }
    "etl-f2890" {
        docker compose exec -w /app backend uv run python -m etl.f2890 --config etl/configs/la_serena_f2890.yaml
    }
    "test"    { docker compose exec -w /app backend uv run pytest }
}
