param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "migrate", "etl", "test")]
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
    "test"    { docker compose exec -w /app backend uv run pytest }
}
