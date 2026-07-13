# Diseño: Backfill de geocoding vía Apify para leads fallidos

## Contexto

El generador de rutas comerciales (ver [2026-07-13-rutas-comerciales-design.md](2026-07-13-rutas-comerciales-design.md))
geocodifica leads con Nominatim (OSM), que no indexa bien locales chicos. De
1389 leads totales, 728 quedaron `geocode_source = 'fallido'` — sin dato
geocodificable vía Nominatim, ni por dirección ni por nombre de negocio.

Se evaluaron dos alternativas para recuperarlos:
- **Google Places API (Place Details)**: más precisa, usando los Place_ID reales
  ya guardados, pero requiere API key + cuenta de Google Cloud con billing —
  costo recurrente que se evitó deliberadamente al iniciar el proyecto.
- **Apify (actor `compass/crawler-google-places`, ya usado por `prospector.py`)**:
  buscando por nombre de negocio directo en Google Maps. Costo estimado
  ~$0.002/resultado (~$1-2 para los 728), sin cuenta de GCP ni costo recurrente.

Se elige **Apify**, descartando Places API por ahora.

## Alcance

Un **script standalone, disparado manualmente** — no se integra al pipeline de
sync existente. Un lead nuevo que falle Nominatim en un sync futuro queda
`'fallido'` hasta que alguien corra este script de nuevo a propósito. Esto evita
generar costo automático (aunque chico) sin decisión explícita en cada sync.

Este backfill también escribe, de forma acotada, la columna `Direccion` en el
Google Sheet — única excepción documentada al invariante "el Sheet nunca se
escribe" del diseño original de rutas (`routes_db.py`). Ver sección "Escritura
al Sheet" para el alcance exacto de esa excepción.

**Fuera de alcance:**
- Google Places API (descartada, ver Contexto).
- Cualquier cambio al pipeline de sync o geocoding automático existente.
- Reintentos automáticos programados (cron, etc.) — se corre a mano.

## Arquitectura

Dos módulos nuevos, sin tocar el pipeline de sync/geocoding existente:

- **`routes_apify_geocoding.py`** — funciones puras: matching por Place_ID,
  matching por nombre con verificación, construcción de inputs para el actor.
- **`backfill_apify_geocoding.py`** — script orquestador (CLI), estilo
  `add_zona_column.py`/`fix_bottom_rows.py`: conecta a la DB, llama Apify en
  lotes, actualiza `leads_cache`, y al final actualiza el Sheet.

`routes_geocoding.py`, `routes_db.py` (salvo los nuevos valores de
`geocode_source`, sin cambio de schema) y `routes_sheet_sync.py` no se
modifican.

## Flujo

1. Leer de `leads_cache` todos los leads con `geocode_source = 'fallido'`.
2. Separar en dos grupos según si `place_id` es un Place_ID real de Google o
   una clave sintética (prefijo `NOID:`, ver `routes_sheet_sync.py:_row_place_id`):
   - **Con Place_ID real** (~107): lookup directo al actor con input `placeIds`.
   - **Sin Place_ID real** (~621): búsqueda por nombre, en lotes de ~50-100 vía
     `searchStringsArray`, con `locationQuery` amplio ("Ciudad Autónoma de
     Buenos Aires, Argentina") y `maxCrawledPlacesPerSearch: 1`.
3. Verificar cada resultado (ver "Matching y verificación").
4. Guardar cada match aceptado en `leads_cache` (`lat`, `lng`,
   `geocode_source`) apenas se confirma — no al final del batch. Esto hace el
   script resumible sin trabajo extra: si se corta a la mitad, los leads ya
   resueltos dejan de aparecer como `'fallido'` en la próxima corrida.
5. Al terminar el backfill de la DB, actualizar el Sheet para los leads
   elegibles (ver "Escritura al Sheet").
6. Imprimir resumen final.

## Matching y verificación

- **Por Place_ID** (alta confianza): se acepta si el resultado trae
  coordenadas y estas caen dentro del bounding box AMBA ya definido en
  `routes_geocoding.py` (`_within_amba_bounds`). No se compara nombre — un
  Place_ID real ya identifica el negocio exacto.
- **Por nombre** (menor confianza): se acepta solo si se cumplen **ambas**
  condiciones:
  1. Similitud de texto entre `negocio` (original) y `title` (resultado de
     Apify) por encima de un umbral — `difflib.SequenceMatcher`, normalizando
     mayúsculas/acentos antes de comparar, umbral inicial `0.6`.
  2. Coordenadas dentro del bounding box AMBA.
- Si no pasa la verificación, el lead queda `'fallido'` — mismo estado que
  tenía, sin riesgo de introducir un match incorrecto (evita repetir el bug de
  coincidencias falsas del `direccion = "-"` documentado en el handoff previo).
- Nuevos valores de `geocode_source`: `apify_placeid` y `apify_nombre` —
  permiten auditar más adelante cuáles son de menor confianza si hiciera falta
  revisión manual.

**Riesgo a confirmar en implementación**: al mandar varios nombres en un mismo
`searchStringsArray`, hay que verificar que cada ítem del dataset resultante
indique a qué string de búsqueda corresponde (típicamente un campo
`searchString` en el actor `compass/crawler-google-places`). Se valida con una
prueba chica (2-3 nombres) antes de correr el batch completo. Si el actor no
lo provee, el fallback es achicar los lotes a una búsqueda por corrida.

## Escritura al Sheet

Excepción acotada al invariante "nunca se escribe al Sheet":

- **Filas elegibles**: solo leads con `geocode_source` nuevo (`apify_placeid`
  o `apify_nombre`) **y** cuya `direccion` original en la DB era vacía o
  `"-"`. No se toca ninguna fila que ya tuviera una dirección escrita, aunque
  Nominatim no la haya podido geocodificar.
- **Valor escrito**: la dirección formateada que devuelve el resultado de
  Apify para ese negocio.
- **Cómo se ubica la fila en el Sheet**:
  - Con Place_ID real: match exacto por columna `Place_ID`.
  - Con clave sintética (`NOID:...`): esas filas tienen la celda Place_ID
    vacía en el Sheet, así que se matchea por `Negocio` (case-insensitive)
    dentro de la pestaña de su categoría.
  - Si no se encuentra la fila (el Sheet pudo cambiar desde el último sync),
    se loguea como advertencia y se continúa — no rompe el script.
- **Cómo se escribe**: agrupado por pestaña (un `batch_update`/`update_cells`
  por tab, no una llamada por fila), para quedar cómodos dentro de los límites
  de rate de la API de Sheets (gratis, sin costo — a diferencia de los
  créditos de Apify).
- Reusa el mismo OAuth2/`token.pickle` que ya usan `prospector.py` y
  `routes_sheet_sync.py`.

## CLI y modo dry-run

`python backfill_apify_geocoding.py [--dry-run]`

- **`--dry-run`**: corre el flujo completo contra Apify de verdad (sí gasta
  créditos, porque necesita resultados reales para mostrar qué se aceptaría o
  rechazaría), pero no escribe en la DB ni en el Sheet. Útil para validar el
  umbral de similitud antes de comprometer el resultado.
- Progreso impreso por lote, ej.: `Lote 3/7 (nombres 101-150): 42 aceptados,
  8 rechazados por verificación`.
- Resumen final: resueltos por Place_ID, resueltos por nombre, rechazados por
  verificación, siguen fallidos, direcciones actualizadas en el Sheet, costo
  estimado (`resultados_totales * $0.002`).

## Testing

Mismo patrón que los 74 tests existentes (pytest, `ApifyClient` mockeado —
nunca se llama a la API real en tests):

- Similitud de nombre: acentos/mayúsculas distintas, nombres claramente
  distintos, nombres iguales.
- Aceptación por Place_ID: dentro de AMBA vs fuera de AMBA.
- Aceptación por nombre: pasa ambos chequeos / falla similitud / falla zona
  → en los dos últimos casos, el lead queda `'fallido'`.
- Mapeo de resultados de un lote de `searchStringsArray` de vuelta a los leads
  originales.
- Matching de fila en el Sheet: por Place_ID, por Negocio+categoría
  (sintético), y caso "no encontrado" (solo advertencia, no falla).
- División de una lista de leads en lotes del tamaño configurado.

## Decisiones descartadas

- **Places API**: descartada por requerir cuenta de GCP con billing (ver
  Contexto).
- **Integrar Apify al pipeline de sync automático**: descartado para esta
  primera versión — se prefiere mantenerlo manual y explícito dado que genera
  costo (aunque chico) en cada corrida.
- **Aceptar el primer resultado de Apify sin verificación**: descartado — se
  aprendió del bug de `direccion = "-"` que aceptar matches sin verificar
  puede introducir coordenadas incorrectas silenciosamente.
- **Actualizar Direccion para cualquier lead resuelto por Apify**: descartado
  — solo se sobreescriben direcciones vacías o `"-"`, nunca una dirección
  existente aunque no se haya podido geocodificar.
