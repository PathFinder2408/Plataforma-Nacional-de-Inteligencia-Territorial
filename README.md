# Plataforma Nacional de Inteligencia Territorial

Motor de decisión territorial para Chile (PostGIS 3.4+ · GeoDjango · Martin · MapLibre GL JS · Celery/Redis).

## Estructura del monorepo
- `backend/`: API y modelos GeoDjango.
- `etl/`: pipelines idempotentes (GeoPandas/pyogrio) y datasets sintéticos.
- `frontend/`: interfaz web (React + MapLibre GL JS).
- `infra/`: configuración de infraestructura (Martin, Docker, CI).
- `docs/`: ADRs (`docs/DECISIONS.md`) y documentación técnica.

## Levantar el entorno local
> **Windows:** la ruta recomendada es **WSL2** con Docker Desktop y `make`. Como alternativa nativa, usa `.\tasks.ps1 <comando>`.

1. Copia `.env.example` a `.env` y ajusta credenciales locales si es necesario.
2. Levanta los servicios: `make up` (o `.\tasks.ps1 up`).
3. Aplica migraciones: `make migrate` (o `.\tasks.ps1 migrate`).
4. Ejecuta el ETL sintético: `make etl` (o `.\tasks.ps1 etl`).
5. Corre los tests: `make test` (o `.\tasks.ps1 test`).

## Decisiones abiertas
- Comuna piloto y convenio/fuente legítima de geometrías de parcelas.
- Público objetivo inicial para calibrar el primer puntaje de oportunidad.
- Revisión legal de licencias de datos y flujo de informe de dominio (Ley 21.719).
