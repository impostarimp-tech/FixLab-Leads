# Diseño: Generador de rutas comerciales (FixLab Store)

## Contexto

FixLab/Isolution/Impostar scrapea leads de Google Maps (`prospector.py`) hacia un
Google Sheet con 3 tabs (Repuestos, Fundas, Telefonos), concentrados en
Balvanera/Once, CABA. Hoy no existe forma de armar rutas de visita comercial a
partir de esos leads sin trabajo manual repetido, ni de trackear qué direcciones
ya se compartieron con el vendedor.

Esta es una nueva sección ("generador de rutas") integrada al proyecto Flask
existente (`fixlab-leads/`). Es una **app de escritorio de un solo usuario**, sin
requisito de acceso móvil: el flujo real es generar la ruta en la PC y mandar el
link de Google Maps por WhatsApp al vendedor, que abre el link directamente sin
necesitar acceso a la app.

## Alcance (MVP)

Incluye: leer leads del Sheet, geocodificar, generar lotes de rutas ordenadas
geográficamente, trackear qué se compartió y cuándo.

**Fuera de alcance de este MVP** (fase 2, si hace falta más adelante):
- Vista consolidada de las 3 categorías con filtros avanzados
- Tracking de outreach (contactado → respondió → convertido)
- Reemplazo de las columnas manuales del Sheet (`Tipo_contacto`, `Estado`)

## Arquitectura

- Blueprint nuevo `routes_app.py` registrado en el `app.py` Flask existente.
- Reusa el OAuth2/`token.pickle` ya configurado para leer los 3 tabs vía gspread.
- No modifica `prospector.py` ni la lógica de scraping/dedup existente.
- Estado nuevo vive en una base SQLite separada (`leads_routes.db`); **el Sheet
  nunca se escribe** desde esta nueva sección.
- Geocoding: Nominatim (OSM) público, sin infraestructura propia — justificado
  porque cada dirección se geocodifica una única vez y queda cacheada para
  siempre (ver "Geocoding" abajo).
- Orden de ruta: heurística nearest-neighbor pura por lat/lng (sin OSRM ni
  dependencia externa de ruteo).

## Modelo de datos (SQLite — `leads_routes.db`)

```
leads_cache
  id (PK, interno)
  place_id           -- clave de dedup contra el Sheet (o nombre+direccion si no hay place_id)
  categoria          -- Repuestos / Fundas / Telefonos
  negocio, direccion -- copia liviana, evita ir al Sheet en cada consulta
  lat, lng
  geocode_source     -- 'maps_url' | 'direccion' | 'negocio' | 'fallido'
  last_synced_at

lotes
  id (PK)
  fecha_generado
  origen_lat, origen_lng, origen_texto
  tamaño_solicitado  -- N pedido al generar (ej. 40)

sublotes
  id (PK)
  lote_id (FK)
  orden               -- posición dentro del lote (1, 2, 3...)
  maps_link
  compartido_en       -- null hasta confirmar el envío

sublote_leads
  sublote_id (FK)
  lead_id (FK a leads_cache)
  orden_en_ruta       -- posición dentro del sub-grupo
```

## Sincronización desde el Sheet

Botón manual "Sincronizar leads" (no automático, para no golpear la API de
Sheets sin pedirlo):

1. Lee los 3 tabs vía gspread.
2. Inserta en `leads_cache` las filas nuevas (no existentes por `place_id`).
3. Geocodifica solo las filas nuevas o las marcadas `fallido` previamente.
4. Filas ya en cache (mismo `place_id`) no se regeocodifican ni se pisan,
   aunque hayan cambiado otras columnas del Sheet.

## Geocoding (cadena de fallback)

Por cada lead nuevo o previamente fallido:

1. **Regex sobre `Maps_URL`**: buscar patrón `@-?\d+\.\d+,-?\d+\.\d+` — gratis,
   instantáneo, es la ubicación que Google ya resolvió al scrapear.
2. Si no hay match → **Nominatim** con `Direccion + ", Buenos Aires, Argentina"`.
3. Si falla o no hay dirección → **Nominatim** con `Negocio + ", Buenos Aires, Argentina"`.
4. Si las tres fallan → `geocode_source = 'fallido'`, visible en una vista aparte
   para revisión manual. No bloquea la generación de lotes (esos leads
   simplemente no entran al pool hasta resolverse).

Nominatim se llama respetando 1 req/seg. Solo aplica a los pasos 2 y 3 — la
mayoría de los leads scrapeados debería resolverse gratis por URL en el paso 1.
Reintento simple (1-2 veces con backoff) ante fallos transitorios/rate-limit.

## Pool de candidatos para un lote

Leads en `leads_cache` con `geocode_source != 'fallido'` **y** que:
- Nunca fueron incluidos en un sub-lote compartido, **o**
- Fueron compartidos hace 30+ días (vuelven a ser candidatos automáticamente).

Sin otros filtros automáticos (categoría, Foco_Apple, etc.) — el pool combina
las 3 categorías (Repuestos, Fundas, Telefonos) sin distinción.

## Algoritmo de generación de lote

1. Usuario ingresa **origen** (dirección en texto libre, se geocodifica al
   vuelo — no necesita ser un lead existente) y **tamaño N** (ej. 40,
   configurable en cada generación).
2. Se toman los **N candidatos más cercanos al origen** (distancia **haversine**,
   en metros — no Pythagorean naive sobre grados lat/lng crudos, que distorsiona
   la escala real a esta latitud) del pool.
3. Se ordenan con **nearest-neighbor**: arranca en el origen, va siempre al
   candidato no visitado más cercano (misma distancia haversine), hasta recorrer
   los N. Da una secuencia geográficamente continua de principio a fin.
4. Se parte la secuencia en **sub-lotes de hasta 9**, respetando el orden (sin
   reordenar entre cortes) — el sub-lote 2 arranca geográficamente donde
   terminó el sub-lote 1 (no vuelve al origen original en cada sub-lote).
5. Por cada sub-lote se genera un link de Google Maps:
   `origin = <último punto del sub-lote anterior, u origen real si es el primero>`,
   `waypoints = <hasta 8 leads intermedios>`, `destination = <último lead del sub-lote>`.
6. Si hay menos de N candidatos disponibles, se genera el lote con los que
   haya y se avisa cuántos se pudieron incluir (no es un error).

Resultado: lista de sub-lotes, cada uno con su link de Maps y el detalle de
direcciones incluidas, listos para copiar y enviar por WhatsApp uno por uno a
medida que el vendedor avanza.

## UI / flujo

- **Generar lote**: formulario (origen, tamaño N) → resultado con sub-lotes,
  cada uno con su link de Maps y botón "Marcar como compartido" (individual, o
  "marcar todo el lote").
- **Aviso en pantalla**: si el vendedor abre el link desde el navegador móvil
  en vez de la app de Maps instalada, puede que solo se respeten 3 waypoints en
  vez de 9 — recomendar abrir con la app instalada.
- **Vista de leads no geocodificables**: listado de `geocode_source = 'fallido'`
  para revisión manual, no bloquea el resto del flujo.
- **Historial de lotes**: lotes/sub-lotes generados, con fecha y estado de
  compartido.

## Manejo de errores

- **Origen no geocodificable**: error claro antes de generar el lote, no se
  genera un link roto.
- **Menos de N candidatos**: se genera con lo disponible, se informa el total
  real incluido.
- **Nominatim caído/rate-limited**: reintento con backoff; si persiste, la fila
  queda `fallido` sin trabar el resto del sync.
- **Sheet inaccesible** (token vencido, sin conexión): error visible en la UI de
  esta sección, sin afectar el resto de `fixlab-leads` (scraper/dashboard
  existentes siguen funcionando).

## Testing

Foco en la lógica pura (la que puede romperse en silencio):
- Parseo de coordenadas desde `Maps_URL` (con y sin match).
- Orden nearest-neighbor sobre un set de puntos conocido.
- Partición en sub-lotes de ≤9 preservando el orden de la secuencia.
- Generación del link de Maps (formato correcto de origin/waypoints/destination).

Sin tests de UI/Flask end-to-end automatizados — se prueba el flujo completo a
mano una vez implementado, dado el volumen de uso real (una persona, pocas
veces por semana).
