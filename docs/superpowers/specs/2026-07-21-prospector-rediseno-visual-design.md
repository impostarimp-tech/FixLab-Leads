# Diseño: Rediseño visual + mobile del Lead Prospector (app.py)

## Contexto

El rediseño visual/mobile ya aplicado al generador de rutas
(`docs/superpowers/specs/2026-07-21-rutas-rediseno-visual-design.md`) cubrió
solo el blueprint `routes_app.py` ("Rutas"). La página principal de
`app.py` ("FixLab Lead Prospector" — busqueda de leads en Google Maps e
Instagram, historial, cobertura de zonas) quedó con su estilo original, sin
relación visual con Rutas y sin ningún breakpoint responsive.

Esta es la continuación natural: llevar la misma paleta y el mismo patrón de
mobile (tablas → cards) a esta página, sin tocar su lógica de scraping/sync
existente.

## Alcance

Incluye: paleta/tipografía nueva + responsive real (breakpoint 768px) para
toda la página de `app.py` (formulario de búsqueda, resultados, historial,
cobertura de zonas, sección de Instagram).

**Fuera de alcance:**
- Cualquier cambio a la lógica de scraping, sync, o llamadas a Apify/Instaloader.
- Unificación de navegación con Rutas — la tab-bar existente (Repuestos /
  Fundas / Telefonos / link a Rutas) se mantiene tal cual, solo repintada.
  Decisión explícita: esta página y Rutas siguen siendo dos superficies
  separadas, no una sola app con nav compartida.
- Refactor a variables CSS compartidas con `routes_app.py` — se portan los
  valores hex directamente al estilo existente de `app.py` (que no usa
  variables CSS), para minimizar el diff en una página no tocada hasta ahora.
- La función de geolocalización/ruta-mas-cercana planteada en la misma
  conversación — pertenece a Rutas (Mapa/selección de origen), no a esta
  página, y se diseña por separado.

## Paleta y tipografía

Mismos valores que Rutas, pero como hex directos (no variables), insertados
donde hoy `app.py` usa sus colores actuales:

```
fondo general:        #1a1a1a (header oscuro) -> se mantiene el header oscuro,
                       pero el resto del fondo pasa de #f5f5f5 a #F8FAFC
texto principal:      #1a1a1a -> #334155
texto secundario:     #888/#666 -> #64748B
texto de titulos:     #1a1a1a -> #0F172A
acento/botones:       #1a1a1a (negro) -> #0284C7 (azul primario)
hover de botones:      #333 -> #0369A1
bordes:               #e5e5e5/#ddd -> #D8EBF2
fondos suaves:        #f9f9f9/#f5f5f5 -> #E8F4F8 o #F8FAFC segun el caso
```

Fuente: Inter (mismo `@import` que Rutas).

El header oscuro (`.header { background: #1a1a1a; }`) se mantiene oscuro —
no se fuerza a blanco — porque es un elemento de marca ya establecido en
este dashboard especifico, distinto del header claro de Rutas. Cambio
minimo: mismo negro/gris oscuro, solo tipografia Inter.

## Breakpoint y estrategia responsive

Mismo criterio que Rutas: un solo breakpoint en 768px, con reestructuracion
real donde el contenido no entra razonablemente en una pantalla angosta, no
solo achicado.

## Componentes por seccion

**Formulario de busqueda:** la fila `.row` (Max. resultados / Terminos de
busqueda, hoy `grid-template-columns: 1fr 1fr`) pasa a una sola columna en
mobile.

**Resultados de busqueda (stat-grid):** hoy `repeat(4, 1fr)` — en mobile pasa
a `repeat(2, 1fr)` (grilla 2x2) en vez de 4 columnas apretadas.

**Tabla de leads nuevos:** mismo patron dual-render que CRM/Historial/Fallidos
en Rutas — desktop mantiene la tabla (`#leadsTable`), mobile muestra una
lista de cards generada por JS a partir del mismo array `allLeads` que ya
alimenta la tabla hoy (la tabla se llena via JS, no via Jinja server-side,
asi que el render de cards tambien se hace en `renderLeads()` client-side,
no en el servidor).

**Historial de corridas (`#histTable`):** mismo patron — desktop tabla,
mobile cards generadas por la misma funcion `renderHistorial()` que ya
arma las filas hoy.

**Cobertura de zonas (`.zona-cobertura-table`):** mismo patron — desktop
tabla, mobile cards generadas por `renderCobertura()`.

**Seccion Instagram:** mismo tratamiento para su stat-grid (3 columnas ->
2 columnas en mobile) y su tabla de resultados (`igLeadsTable`, generada por
`showIGResults()`), mismo patron dual-render.

**Log boxes** (`#logBox`, `#igLogBox`): sin cambio estructural, solo la
paleta nueva (fondo oscuro se mantiene, coincide con el estilo de terminal
ya usado).

**Tab-bar** (Repuestos/Fundas/Telefonos/Rutas): sin cambio estructural —
ya es una fila flex de 4 items, misma forma que los tabs de categoria de
Mapa que ya funcionan bien a 375px. Solo color nuevo para el estado activo.

## Diferencia clave con el rediseño de Rutas

En Rutas, las tablas se renderizan server-side (Jinja, `render_template_string`)
y el dual-render es dos bloques `{% for %}` en el HTML. Acá, las tablas de
resultados/historial/cobertura se llenan **client-side via JavaScript**
(`renderLeads()`, `renderHistorial()`, `renderCobertura()`, `showIGResults()`)
después de un fetch o un evento SSE. El dual-render mobile acá significa que
esas mismas funciones JS escriben tanto el `<tbody>` de la tabla como un
`<div class="mobile-cards">` a partir de los mismos datos, no un segundo loop
Jinja.

## Manejo de errores

Sin cambios — esta página no toca la lógica de scraping/sync/errores
existente, solo presentación.

## Testing

Sin tests automatizados nuevos (igual que el rediseño de Rutas) — esta
página no tiene tests de UI/JS hoy y no es el foco de este cambio. Verificación
manual en navegador en ~375px y ~1280px para cada sección antes de dar el
trabajo por terminado.
