# Registro de Decisiones de Arquitectura (ADR)

Registra cada decisión en 1 a 3 líneas (fecha, decisión, motivo).

- **2026-11-18 | ADR-001 (CRS y superficie):** Geometrías almacenadas en `EPSG:4326` (reproyectando desde CRS origen); `superficie_m2` calculada al cargar con `ST_Area(geom::geography)` junto a `superficie_declarada` (alerta si difieren > 10 %). Evita elegir zona UTM 18S/19S en consultas y detecta polígonos defectuosos sin costo en lectura.
- **2026-11-18 | ADR-002 (Particionado diferido):** En Iteración 1 no se activa particionado declarativo; se incluye `region_id` (`smallint`, not null) e índice `(region_id, comuna_id, rol)`. Se activará vía migración SQL dedicada (`RunSQL`) al superar 50 M de filas o degradación medida con `EXPLAIN ANALYZE`, evitando complejidad prematura en PK, FKs y Martin.
- **2026-11-18 | ADR-003 (Fuentes, tiles y dominio):** ETL agnóstico a la fuente con registro de hash/licencia en `FuenteDato`; tiles desde Martin con índice GiST (y simplificación por zoom solo si `EXPLAIN ANALYZE` lo justifica). Sin scraping masivo de CBR: dominio resuelto bajo demanda con patrón Strategy y cumplimiento Ley 21.719.
- **2026-11-18 | ADR-004 (Dependencias Python base):** Se instalan `django`, `psycopg[binary]`, `geopandas`, `pyogrio`, `pyyaml`, `redis` y en dev `pytest`, `pytest-django`, `ruff`, fijadas con `uv.lock` para builds reproducibles en Docker.
- **2026-11-18 | ADR-005 (Dependencias Frontend):** Se instalan `react`, `react-dom`, `maplibre-gl` (y `vite` + `typescript` en dev) para renderizar tiles MVT/PMTiles sin costos ni bloqueo de Mapbox.
- **2026-11-18 | ADR-006 (Indexación H3):** Se instala `h3` (>=4.1) en Python para generar hexágonos H3 (res. 7–9) y polígonos límite de agregación sin requerir compilación de extensiones C en la imagen PostGIS.
