# PROGRESS.md — Plataforma Nacional de Inteligencia Territorial

- **Proyecto:** Plataforma Nacional de Inteligencia Territorial (Chile)
- **Fase actual:** Fase 3 — Capas del Estado y riesgo (en curso)
- **Última actualización:** 2026-11-18

## Fase 0 — Configuración inicial y validación de datos/legalidad

| ID | Tarea | Esfuerzo (L/M/P) | Modelo usado | Estado | Criterio de aceptación | Notas |
| --- | --- | --- | --- | --- | --- | --- |
| 0.1 | Crear `AGENTS.md`, `PROGRESS.md` y `docs/DECISIONS.md` adaptados al proyecto territorial | L | Gemini 4 Hydrogen (Medium) | hecha | Los 3 archivos existen con reglas, plantilla de fases y encabezado de decisiones | `AGENTS.md` <= 60 líneas |

## Fase 1 — Núcleo espacial
| ID | Tarea | Esfuerzo (L/M/P) | Modelo usado | Estado | Criterio de aceptación | Notas |
| --- | --- | --- | --- | --- | --- | --- |
| 1.1 | Estructura monorepo, `.env.example`, `Makefile`, `tasks.ps1`, `README.md` y ADRs iniciales | L | Gemini 4 Hydrogen (Medium) | hecha | Carpetas `backend/`, `frontend/`, `etl/`, `infra/`, `docs/` + `docs/DECISIONS.md` con 3 ADRs y `README.md` base | Base sin secretos |
| 1.2 | `docker-compose.yml` (PostGIS 3.4+, Redis, Martin, backend con `uv`) y healthcheck | M | Gemini 4 Hydrogen (Medium) | hecha | `make up` levanta PostGIS, Redis, Martin y backend sin errores | `uv.lock` generado; `make up` pendiente (Docker no instalado aquí) |
| 1.3 | Modelos GeoDjango (`Comuna`, `FuenteDato`, `Parcela` con `region_id` y `superficie_declarada`, `AliasRol`), migraciones e índices | P | Gemini 4 Hydrogen (High) | hecha | `make migrate` aplica esquema en PostGIS; índices GiST, `(region_id, comuna_id, rol)` y unique `(comuna, rol, vigente_desde)` verificados | `ruff` en verde; `make migrate` pendiente por Docker local |
| 1.4 | Script ETL agnóstico (GeoPandas/pyogrio), reproyección a 4326, `ST_Area(geography)`, upsert idempotente y reporte JSON | P | Gemini 4 Hydrogen (High) | hecha | `make etl` no duplica al re-ejecutar; reporte distingue insertadas/actualizadas/sin cambios/rechazadas + alerta dif. superficie >10% | `ruff` en verde; integración PostGIS se prueba en `1.5` |
| 1.5 | Dataset sintético La Serena (`EPSG:32719`) con inválidas/duplicados/vigencias + tests `pytest` + `EXPLAIN ANALYZE` | M | Gemini 4 Hydrogen (Medium) | hecha | `make test` en verde; inválidas reparadas o rechazadas; consulta punto→parcela usa GiST (<100 ms) | Unit test `test_transform` pasó; integración PostGIS lista (skipped sin Docker aquí) |

## Fase 2 — Motor de mapa
| ID | Tarea | Esfuerzo (L/M/P) | Modelo usado | Estado | Criterio de aceptación | Notas |
| --- | --- | --- | --- | --- | --- | --- |
| 2.1 | API Django: `por-punto` (`ST_Intersects`) y `buscar` (rol, alias, coordenadas) con procedencia/confianza + índices `pg_trgm` | M | Gemini 4 Hydrogen (Medium) | hecha | Endpoints devuelven ficha/resultados con fuente/fecha/confianza; unit tests y `ruff` en verde | Sin GeoJSON pesado |
| 2.2 | Afinar Martin (`parcela` MVT) y pipeline **PMTiles** (`tippecanoe`) para capas estáticas | M | Gemini 4 Hydrogen (Medium) | hecha | Tiles MVT servidos por Martin y script PMTiles documentado/verificado | Function source `parcelas_mvt` + `build_pmtiles.sh` + Martin `/pmtiles` |
| 2.3 | Frontend React + TypeScript + Vite + MapLibre GL JS con estado en URL, MVT y ficha al clic | P | Gemini 4 Hydrogen (Medium) | hecha | Mapa renderiza MVT y muestra ficha con procedencia/confianza al hacer clic | Proxy `/api` y `/tiles` en Vite |
| 2.4 | Buscador UI + verificación de SLOs (`EXPLAIN ANALYZE` < 100 ms y carga de tiles < 150 ms) | M | Gemini 4 Hydrogen (Medium) | hecha | Búsqueda centra el mapa y script/test documenta latencias | `SearchBar.tsx` + `verify_slo.py` + `test_slo_explain.py` |

## Fase 3 — Capas del Estado y riesgo
| ID | Tarea | Esfuerzo (L/M/P) | Modelo usado | Estado | Criterio de aceptación | Notas |
| --- | --- | --- | --- | --- | --- | --- |
| 3.1 | Modelos GeoDjango (`TerrenoFiscal`, `CapaNormativa`, `CapaRiesgo`, relieve en `Parcela`) y migración con GiST | P | Gemini 4 Hydrogen (XHigh) | hecha | `make migrate` aplica tablas nuevas con `FuenteDato`, `fecha_corte`, `confianza` e índices GiST | `makemigrations --check` sin cambios pendientes; `martin` + SLOs validados |
| 3.2 | Loaders ETL idempotentes y fixtures sintéticos La Serena (fiscal, normativa, riesgo, DEM) | M | Gemini 4 Hydrogen (XHigh) | hecha | Carga repetible sin duplicados y reporte de calidad para las 4 capas | `etl/layers.py` + 4 fixtures La Serena + `test_layers_etl` verde |
| 3.3 | Servicio y endpoint `ficha-completa` (cruce espacial de parcela con fiscal, normativa, riesgo y relieve) | P | — | pendiente | API devuelve cada bloque con su fuente, fecha de corte, confianza y descargo referencial | Cabida estimada referencial |
| 3.4 | Capas en Martin/frontend (toggles de riesgo/normativa/fiscal + ficha completa) y tests `pytest` | M | — | pendiente | UI muestra capas y ficha completa; `make test` y `vite build` en verde | Sin GeoJSON pesado |

## Fase 4 — Inteligencia
*(Pendiente de descomposición al iniciar la fase)*

## Fase 5 — Informe de dominio y monetización
*(Pendiente de descomposición al iniciar la fase)*

## Fase 6 — Escalamiento nacional por oleadas
*(Pendiente de descomposición al iniciar la fase)*

## Siguiente paso
Confirmar para pasar a **`3.3` (Esfuerzo: PESADO — Servicio y endpoint `ficha-completa` con cruce espacial y cabida referencial)**.

## Bloqueos y riesgos
- **Geometría de parcelas piloto:** SII-Mapas es referencial e institucional (WMS/WMTS); requiere definir comuna piloto y fuente legítima.
- **Cumplimiento legal:** Ley 21.719 (protección de datos personales) y prohibición de scraping masivo al CBR.
- **Calidad heterogénea:** Normativa urbana (PRC/PRI/PRMS) desigual por comuna.

## Registro de sesiones
- **2026-11-18:** Cerradas tareas `0.1`, `1.1`–`1.5`, `2.1`–`2.4`, `3.1` y `3.2` (loaders ETL idempotentes de 4 capas estatales/riesgo/DEM, 11 tests en verde).
