# Diseño: Geolocalización del celular en Rutas (nearest-to-me + origen GPS)

## Contexto

El generador de rutas ya soporta un origen dado por coordenadas exactas
(`origen_coords`) además de texto libre/zona — `_resolve_origen()` en
`routes_app.py` ya distingue entre `guardado|lat|lng|texto` (coords directas,
sin geocodificar), `zona|texto` y texto libre (ambos se geocodifican server-side
al generar el lote). La página Mapa (`PAGE_MAPA`) ya carga **todos** los leads
geocodificados en un array JS (`allLeads`, con `lat`/`lng`) para dibujar los
marcadores — no hace falta pedirle nada nuevo al servidor para saber dónde
está cada lead.

Con el celular del vendedor en la calle, dos casos de uso concretos:
1. Saber cuál es el negocio geocodificado más cercano a donde está parado.
2. Generar una ruta completa (el flujo "Generar lote" que ya existe) usando
   su ubicación GPS actual como origen, sin tener que escribir una dirección.

## Alcance

Incluye: botón "Cerca de mi" en Mapa (lookup del lead más cercano, sin
generar ruta) + botón "Usar mi ubicacion" en el formulario de generación de
lotes (Home), ambos basados en `navigator.geolocation` del navegador.

**Fuera de alcance:**
- Cualquier endpoint nuevo de backend — todo el cálculo de distancia corre
  client-side en JS, ya que los datos (todos los leads con lat/lng) ya están
  cargados en el navegador en la página Mapa.
- Reverse-geocoding de las coordenadas GPS a una dirección legible — el
  origen generado por GPS se etiqueta simplemente como "Mi ubicacion (GPS)",
  sin llamar a ningún servicio externo adicional.
- Tracking en tiempo real / actualización continua de la ubicación — es una
  lectura puntual de posición al tocar el botón, no un seguimiento en vivo.
- PWA / acceso a geolocalización en background — solo funciona con la página
  abierta y en foreground, como cualquier uso normal del navegador.

## Componente 1: "Cerca de mi" en Mapa

Botón nuevo cerca de los tabs de categoría en `PAGE_MAPA`. Al tocarlo:

1. Llama a `navigator.geolocation.getCurrentPosition()`.
2. Con las coords devueltas, recorre `allLeads` (**todas las categorías,
   ignorando el tab activo** — decisión explícita) calculando distancia
   haversine a cada uno.
3. Encuentra el lead con menor distancia.
4. Centra/hace zoom del mapa a ese punto (`map.setView(...)` o
   `map.panTo(...)`) y abre su detalle reusando `renderPanel()` — el mismo
   mecanismo que ya existe para el click en un marcador (panel lateral en
   desktop, hoja deslizable en mobile, ya implementado en el rediseño
   visual).
5. Muestra la distancia en el panel de detalle (ej. "a 350m de tu
   ubicacion").

**Manejo de errores:** si `getCurrentPosition` falla (permiso denegado,
timeout, navegador sin soporte, o `allLeads` vacío), se muestra un mensaje
inline claro (ej. "No se pudo obtener tu ubicacion — revisa los permisos
del navegador.") — nunca falla en silencio, y el resto del mapa sigue
funcionando normalmente.

## Componente 2: "Usar mi ubicacion" en el formulario de generación (Home)

Botón nuevo junto al `<select>` de origen en `PAGE_HOME`. Al tocarlo:

1. Llama a `navigator.geolocation.getCurrentPosition()`.
2. Con las coords devueltas, arma el mismo formato que ya entiende
   `_resolve_origen()` para un origen "guardado": setea el valor del select
   a `guardado|<lat>|<lng>|Mi ubicacion (GPS)` (o inserta/selecciona
   dinámicamente una opción nueva con ese value) y dispara
   `onOrigenSelectChange()` para que el resto del formulario (cantidad de
   direcciones, categoría, etc.) se comporte exactamente igual que si el
   vendedor hubiera elegido un origen guardado existente.
3. El submit del formulario (`POST /rutas/generar`) no cambia — sigue
   yendo a `_resolve_origen()` y `batch.generate_lote()` tal cual existen
   hoy, ya que el value ya viene en el formato `guardado|lat|lng|texto` que
   esas funciones ya parsean.

**Manejo de errores:** mismo criterio que el Componente 1 — mensaje inline
claro si falla, sin romper el resto del formulario.

## Cálculo de distancia (haversine en JS)

La formula haversine ya existe en Python (`routes_algorithm.py`), pero no se
comparte con el cliente — se escribe una función JS equivalente directamente
en el `<script>` de `PAGE_MAPA` (y reusada si `PAGE_HOME` también la
necesita, aunque para el Componente 2 no hace falta calcular distancias, solo
pasar las coords crudas). Es una fórmula de ~5 líneas, no amerita una
implementación compartida entre Python y JS para este alcance.

## Testing

Sin tests automatizados nuevos — esta es lógica 100% client-side (JS en el
navegador), y ninguna función Python cambia (`_resolve_origen`/
`generate_lote` reciben exactamente el mismo formato de datos que ya
soportan). Verificación manual: simular `getCurrentPosition` con coords de
prueba (via devtools o mockeando la función en consola) para confirmar que
"Cerca de mi" encuentra el lead correcto y que "Usar mi ubicacion" genera un
lote correctamente desde esas coords. También verificar el mensaje de error
cuando se deniega el permiso.
