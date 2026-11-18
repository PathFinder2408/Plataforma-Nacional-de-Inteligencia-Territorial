# AGENTS.md — Plataforma Nacional de Inteligencia Territorial

## A. Economía de tokens
- Lee `AGENTS.md` y `PROGRESS.md` al inicio de cada sesión y solo los archivos necesarios; nunca recorras el repo completo.
- Antes de leer un archivo grande, busca con grep/símbolos y lee solo el rango relevante.
- No repitas código existente ni pegues archivos completos: muestra solo diffs o fragmentos modificados.
- Respuestas breves: resultado, archivos tocados, cómo verificar. Sin resúmenes largos ni disculpas.
- Una tarea = un objetivo. Si supera ~5 archivos modificados, divídela en `PROGRESS.md` antes de ejecutarla.
- Si tras 2 intentos un error persiste, DETENTE: resume lo probado y propón 2 hipótesis.
- Si la conversación se alarga, resume el estado en `PROGRESS.md` y sugiere abrir sesión nueva.
- No instales dependencias sin justificarlo en 1 línea en `docs/DECISIONS.md`.
- Ejecuta tests, lint y build solo cuando sea relevante para la tarea.

## B. Enrutamiento de modelos (por esfuerzo)
Clasifica cada tarea antes de ejecutarla y recomienda el nivel:
- LIGERO (rápido/económico): renombrados, formato, comentarios, configs/JSON/YAML, README, docs, ajustes triviales.
- MEDIO (equilibrado): modelos/endpoints Django acotados, componentes React/MapLibre, scripts ETL simples, tests unitarios, bugs con causa conocida.
- PESADO (mayor razonamiento): arquitectura inicial, diseño PostGIS/índices/particionado, ETL complejo e idempotente, lógica de puntaje explicable, cumplimiento Ley 21.719, bugs sin causa clara o cambios multi-módulo.
- Escalada: si L o M falla 2 veces, sube de nivel; si P pasa a trabajo mecánico tras planificar, baja a M o L.
- Patrón: planificar con PESADO, implementar con MEDIO/LIGERO, revisar con PESADO si es crítico.

## C. Flujo de trabajo por tarea
1. Anuncia en 1 línea: ID de tarea, esfuerzo y modelo recomendado. Si el modelo actual no coincide, pregunta antes de continuar.
2. Implementa lo mínimo que cumpla el criterio de aceptación; nada extra.
3. Verifica el criterio de aceptación y reporta el resultado real (pasó / falló / no verificado).
4. Actualiza `PROGRESS.md` y haz commit convencional (`feat:`, `fix:`, `chore:`, `docs:`).
5. Detente y espera confirmación antes de pasar a la siguiente tarea.

## D. Calidad y restricciones críticas
- Stack: PostGIS 3.4+, Django/GeoDjango, Martin, PMTiles, React + MapLibre GL JS, GeoPandas/pyogrio, Celery + Redis.
- Datos: sin scraping masivo de CBR (usar patrón Strategy para informe de dominio); respetar Ley 21.719 (minimización, auditoría, retención).
- Cada dato expuesto lleva fuente, fecha de corte y confianza. No inventes fuentes, capas, URLs ni APIs.
- Geometrías en EPSG:4326; áreas/distancias en `geography` o UTM (18S/19S) documentada. Sin GeoJSON pesado al navegador (usar MVT/PMTiles).
- 12-factor (env vars), sin secretos en el repo, código tipado y modular (SOLID).
