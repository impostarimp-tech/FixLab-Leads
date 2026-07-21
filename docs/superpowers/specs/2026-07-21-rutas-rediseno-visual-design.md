# Diseño: Rediseño visual + mobile del generador de rutas

## Contexto

El generador de rutas (`routes_app.py`) usa un estilo propio, genérico, sin
identidad visual definida, y sin ningún breakpoint responsive — las páginas
Mapa y CRM en particular tienen layouts de ancho fijo (mapa 600px + panel
lateral 280px, tabla de 8 columnas) que se rompen en una pantalla de celular.

FixLab tiene otro proyecto propio, `catalogo-mayorista-b2b` (React + Tailwind),
con una identidad visual ya pulida: paleta sky/slate, tipografía Inter, cards
`rounded-2xl`, tabs tipo pill, badges de estado suaves. La idea es trasladar
ese lenguaje visual al generador de rutas y, de paso, hacerlo usable desde el
celular — hoy el vendedor solo puede abrir los links de Maps generados, no
navegar la app en sí desde su teléfono.

## Alcance

Incluye: rediseño visual unificado de las 5 páginas existentes (Inicio,
Historial, No geocodificables, Mapa, CRM) + responsive real con distinción
mobile/desktop (no solo "achicar" el layout de escritorio) + un buscador nuevo
en CRM.

**Fuera de alcance:**
- Cualquier cambio a la lógica de negocio existente (algoritmo de rutas, sync,
  geocoding) — este rediseño es visual/estructural, con una única excepción de
  backend (el buscador de CRM, ver abajo).
- Migración a un framework frontend (React, Tailwind con build step, etc.) —
  se mantiene la arquitectura actual de templates Flask con HTML/CSS/JS inline
  en `routes_app.py`.
- PWA / app instalable / notificaciones push — "mobile-friendly" acá significa
  responsive en el navegador del celular, no una app nativa.

## Sistema de diseño

Paleta y tipografía tomadas directamente de `catalogo-mayorista-b2b/src/index.css`:

```
--color-bg:      #F8FAFC   (fondo general)
--color-dark:    #0F172A   (texto de títulos)
--color-text:    #334155   (texto de cuerpo)
--color-muted:   #64748B   (texto secundario)
--color-accent:  #0EA5E9   (acento claro)
--color-primary: #0284C7   (botones, links activos)
--color-sage:    #0369A1   (botones hover/estado)
--color-light:   #E8F4F8   (fondos suaves, badges)
--color-border:  #D8EBF2   (bordes)
```

Fuente: Inter (Google Fonts, ya usado por `catalogo-mayorista-b2b`).

Estos valores reemplazan las variables CSS que ya existen hoy en
`BASE_STYLE` (`--blue`, `--bg`, `--text`, `--text-muted`, `--border`) —
mismo mecanismo, paleta nueva.

**Componentes base** (reemplazan sus equivalentes actuales en `BASE_STYLE`):
- Cards: `border-radius: 16px`, borde suave, `box-shadow` sutil, hover con
  sombra más marcada — igual que `ProductCard.tsx`.
- Badges/tags: `border-radius` pequeño, texto uppercase diminuto,
  fondo pastel + texto de color a juego (igual que los badges de stock del
  catálogo: verde/ámbar/naranja/rojo → acá se reusa para los estados de
  outreach: sin_contactar/contactado/respondió/convertido).
- Botones: `border-radius: 12px`, color primario con hover más oscuro,
  sin gradientes.
- Tabs/pills: `border-radius: 999px`, activo con fondo claro + texto
  primario + borde primario.

No se agrega ninguna dependencia nueva (no Tailwind CDN, no librería de
iconos) — los iconos que use el catálogo (`lucide-react`, paquete npm) se
reemplazan acá por SVG inline simples o glifos unicode, ya que este proyecto
no tiene build step.

## Breakpoint y estrategia responsive

Un solo breakpoint: **768px**. Por debajo es "mobile", desde ahí para arriba
es "desktop" (comportamiento actual, con la paleta nueva).

Regla general: mobile no es "lo mismo pero apretado" — donde la información
no entra razonablemente en una pantalla angosta, cambia de forma (tabla →
lista de cards, panel lateral → hoja deslizable, fila de nav → barra fija
abajo), no solo de tamaño.

## Navegación

- **Desktop (≥768px):** se mantiene la fila de pills actual (`NAV_LINKS`).
- **Mobile (<768px):** se reemplaza por una barra fija abajo de la pantalla
  con los mismos 5 destinos (Inicio, Historial, No geocodificables, Mapa,
  CRM), cada uno con un ícono simple + label chico. Estilo "app nativa"
  (fijo, siempre visible, sin scroll).

## Página CRM

**Buscador nuevo** (arriba de los filtros existentes, en desktop y mobile):
campo de texto libre que busca por coincidencia parcial en `negocio`,
`direccion` o `telefono`. Se combina con los filtros existentes (categoría,
estado, reviews mínimas, rating mínimo) — todos aplican en conjunto (AND).

Cambios de backend necesarios (únicos de este spec que tocan lógica, no solo
presentación):
- `routes_db._crm_filters_clause`: nuevo parámetro `q: str | None`, agrega
  `AND (negocio LIKE ? OR direccion LIKE ? OR telefono LIKE ?)` con
  parámetros `%q%` (consulta parametrizada, sin concatenación directa de
  strings — evita inyección SQL).
- `get_crm_leads`, `count_crm_leads`, `get_crm_leads_all`: agregan el
  parámetro `q` y lo pasan al clause builder.
- `routes_app.crm()`: lee `request.args.get("q", "").strip()`, lo pasa a las
  funciones de arriba y lo re-inyecta en el formulario y en los links de
  paginación/exportación CSV (mismo patrón que `categoria`/`estado` hoy).

**Layout:**
- Desktop: tabla actual sin cambios estructurales (más paleta nueva).
- Mobile: cada lead se renderiza como una card (nombre + tag de categoría,
  dirección/teléfono/rating, badge de geocodificación, selector de estado).
  Los filtros (categoría/estado/reviews/rating) se colapsan detrás de un
  botón "Filtros" que los despliega — no van sueltos en la pantalla.

## Página Mapa

- Tabs de categoría (Todos/Repuestos/Fundas/Telefonos) y la lista de
  checkboxes de lotes se mantienen arriba, igual en mobile y desktop; en
  mobile los checkboxes de lotes se colapsan detrás de un botón "Filtros"
  igual que en CRM.
- **Desktop:** mapa + panel lateral de detalle, sin cambios estructurales
  (paleta nueva).
- **Mobile:** el mapa ocupa el ancho completo y mantiene su tamaño fijo
  (no se achica al abrir un detalle). Al tocar un marcador, el detalle
  aparece como una **hoja deslizable (bottom sheet)** que sube desde abajo
  por encima del mapa — mismo patrón visual "app nativa" que la barra de
  navegación fija. Se puede cerrar deslizando hacia abajo o tocando afuera.

## Páginas Historial y No geocodificables

Aplican la paleta/tipografía nueva y el mismo patrón tabla→cards en mobile
que CRM (son listados de una sola tabla cada uno, sin filtros complejos —
el cambio acá es más chico que en CRM).

## Manejo de errores

No cambia nada del manejo de errores existente (sync, geocoding, generación
de rutas) — este spec es visual/estructural. La única superficie nueva
(buscador CRM) sigue el mismo patrón de validación que los filtros
existentes: parámetros opcionales, sin resultados → mensaje "No hay leads
para este filtro" (ya existe hoy).

## Testing

- **Buscador CRM** (única lógica nueva): tests unitarios sobre
  `_crm_filters_clause`/`get_crm_leads`/`count_crm_leads` con el parámetro
  `q` — coincidencia parcial case-insensitive, combinación con otros
  filtros, sin resultados.
- **Resto (CSS/HTML/JS de presentación):** sin tests automatizados —
  verificación manual en navegador en al menos dos anchos (mobile ~375px,
  desktop ~1280px) para cada página antes de dar por terminado el trabajo,
  igual que se hizo para la barra de progreso del sync.
