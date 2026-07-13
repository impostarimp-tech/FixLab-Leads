# FixLab Lead Prospector — Handoff Document
_Generado: 2026-06-24_

---

## 1. RESUMEN DEL PROYECTO

**Qué es:** Herramienta B2B de prospección de leads para FixLab Store. Busca negocios (talleres de celulares, tiendas de accesorios, revendedores de iPhones) en Google Maps vía Apify y los vuelca en un Google Sheet compartido, sin pisar leads ya existentes.

**Stack:**
| Capa | Tecnología |
|---|---|
| Backend/UI | Python 3.12 + Flask (puerto 5000, solo local) |
| Scraping Maps | Apify actor `compass/crawler-google-places` ($0.002/resultado) |
| Scraping Instagram | Apify actor `apify/instagram-scraper` + Instaloader 4.13.1 |
| Storage | Google Sheets vía `gspread` + OAuth2 (`token.pickle`) |
| Streaming logs | Server-Sent Events (SSE) desde subprocess stdout |
| Historial local | `historial.json` (newest-first) |

**Arranque:** `launch.bat` → setea env vars (`APIFY_API_TOKEN`, `SPREADSHEET_URL`, `IG_USERNAME`, `IG_PASSWORD`) → corre `python app.py`

**Directorio:** `C:\Users\Jonathan\Desktop\fixlab-leads\`

---

## 2. ESTADO ACTUAL — FUNCIONALIDADES IMPLEMENTADAS

### Google Maps Scraping (`prospector.py`)
- **3 categorías** de búsqueda: `repuestos`, `fundas`, `telefonos` — cada una con su tab en Sheets y sus 6 términos de búsqueda.
- **Modos:** `full` (max=60, 6 términos), `eco` (max=60, 4 términos), `test` (max=10, 1 término).
- **Zonas:** 15 comunas CABA + 48 barrios individuales, más zonas GBA libres.
- **Filtro de relevancia (`es_relevante`):** 2 capas — categoría Maps + keyword en nombre. Recibe `categoria` como parámetro (no global). Elimina resultados como "Helados Daniel", "Puma Energy", etc.
- **Limpieza:** strip `+` del teléfono, dedup interna por `(nombre|telefono)` y `Place_ID`.
- **Dedup vs Sheet:** por nombre, Place_ID **y teléfono** (añadido en esta sesión).
- **Sheets (`volcar_a_sheets`):** mapea por nombre de columna (no posicional) — tolera columnas manuales extras.
- **Manejo de errores Apify:** `try/except` por término; si uno falla, continúa con el siguiente.
- **Métricas para UI:** imprime `Total unicos: X` (post-dedup interna) y `LEADS_JSON:{...}`.

### Interfaz Web (`app.py`)
- Dashboard Flask con SSE para logs en tiempo real.
- Selector de zona con 63 opciones predefinidas.
- Configuración de modo (full/eco/test) con estimación de costo.
- **Cobertura de zonas:** tabla que muestra qué zonas ya fueron scrapeadas, cuántas corridas, leads nuevos, % duplicados de la última corrida, y fecha.
- **% duplicados:** usa `ultima_bruto` / `ultima_nuevos` de la corrida más reciente (no promedio histórico).
- **Panel inline de zona:** al seleccionar una zona en el dropdown, muestra historial de corridas y % por categoría.
- **Indicador visual en dropdown:** añade `✓` a zonas ya procesadas.

### Google Sheets — Estado actual
- **Tab Repuestos** (`Leads FixLab - Talleres CABA (mayorista repuestos)`): 698 filas, **16 columnas** en orden:
  `Zona | Negocio | Direccion | Telefono | Reseñas | Rating | Tipo | Foco_Apple | Revisar_mayorista | Tipo_contacto | Web_o_red | Estado | Categoria | Sitio_web | Maps_URL | Place_ID`
  _(columnas C=Direccion, D=Telefono corregidas manualmente por el usuario)_
- **Tab Fundas** (`Leads Fundas - Maps`): 10 filas, 13 columnas estándar.
- **Tab Telefonos** (`Leads Telefonos - Maps`): 4 filas, 13 columnas estándar.

### Scripts de utilidad (ya corridos, no necesitan correrse de nuevo)
- `add_zona_column.py` — insertó columna "Zona" en las 3 tabs Maps.
- `fix_sheets.py` — corrigió 37 filas con columnas mezcladas (corrida anterior).
- `fix_bottom_rows.py` — corrigió 103 filas con dirección en columna Barrio + eliminó "Aon Risk Services".

---

## 3. TAREAS PENDIENTES (priorizadas)

### P1 — Verificar que `volcar_a_sheets` escribe correctamente con el nuevo orden de columnas en Repuestos
El usuario movió manualmente C=Direccion, D=Telefono. El script usa mapeo por nombre de columna (`ws.row_values(1)`) por lo que debería funcionar sin cambios. **Verificar con una corrida test** (`--test --categoria repuestos`) y confirmar que las columnas nuevas de Repuestos no reciben datos fuera de lugar.

### P2 — Columna "Reseñas" con tilde en Repuestos
La columna en el sheet se llama `Reseñas` (con ñ), pero `prospector.py` la llama `Resenas` (sin ñ) en `cols_script` de `volcar_a_sheets`. Esto hace que esa columna quede vacía al escribir nuevas filas en Repuestos.

**Archivo:** `prospector.py` línea ~395  
**Fix:** agregar `"Reseñas"` a `cols_script` Y mapear correctamente desde el DataFrame (columna interna se llama `Resenas`). Opciones:
- Renombrar la columna del DF antes de volcar: `df.rename(columns={"Resenas": "Reseñas"}, inplace=False)` antes del loop.
- O agregar lógica especial en el loop para ese caso.

### P3 — Teléfonos con formato "54 11 XXXX-XXXX" en filas antiguas
Las filas originales del sheet tienen teléfonos formateados como `"54 11 3946-4805"` en vez de `"541139464805"`. La dedup por teléfono no los va a matchear contra los nuevos (que vienen sin espacios ni guiones). No es urgente pero genera falsos no-duplicados.

**Fix sugerido (opcional):** normalizar teléfono en `filtrar_nuevos` antes de comparar: eliminar espacios, guiones y el prefijo "54".

### P4 — GBA (Gran Buenos Aires) — zonas no cubiertas
El scraping actual es 100% CABA. Faltan partidos del GBA (Quilmes, Lomas de Zamora, Lanús, Avellaneda, etc.). Ya existe soporte para zona custom en la UI — solo es cuestión operativa de correr con esas zonas.

### P5 — Relevancia: falsos positivos en Repuestos
"Aon Risk Services" fue detectado y eliminado, pero el filtro de relevancia lo dejó pasar (no tenía teléfono ni keyword). Evaluar si agregar condición: `if not telefono: continue` antes del filtro de relevancia en `limpiar()`.

---

## 4. ENFOQUES FALLIDOS — NO REPETIR

| Problema | Lo que se intentó | Por qué falló |
|---|---|---|
| % duplicados mostraba 49% en vez de 98% | Calcular % dividiendo acumulado total (bruto/nuevos sumados) | El historial es newest-first; al sumar todas las corridas el % se diluía |
| "Encontrados" mostraba 227 (inflado) | Parsear `"Total bruto:"` en app.py | Era el conteo bruto de Apify antes de dedup interna; hay duplicados internos por términos distintos que devuelven el mismo lugar |
| Columnas mezcladas en Repuestos (37 filas) | `volcar_a_sheets` escribía posicionalmente (columna 1, 2, 3...) | El tab Repuestos tiene 16 columnas con orden distinto a lo que el script asumía |
| `time.sleep(1)` entre llamadas Apify | Poner sleep para "respetar rate limits" | Apify `.call()` es bloqueante (espera que el actor termine), el sleep no tenía efecto |
| `es_relevante()` usando global `CATEGORIA_ACTUAL` | Declarar la variable a nivel módulo y sobreescribir en `main()` | Riesgo de usar "repuestos" como default silencioso si la función se llama antes de `main()`; resuelto pasando `categoria` como parámetro |
| fix_bottom_rows.py con updates individuales | Llamar `ws.update()` una vez por celda | Rate limit de Sheets API (429) al hacer 200+ llamadas individuales; resuelto con `ws.batch_update()` |

---

## 5. INSTRUCCIONES PARA EL NUEVO CHAT

Copiar esto al inicio de la nueva sesión:

---

```
Estoy desarrollando una herramienta B2B de prospección de leads llamada "FixLab Lead Prospector".
El proyecto está en C:\Users\Jonathan\Desktop\fixlab-leads\

Stack: Python 3.12 + Flask (puerto 5000) + Apify (Google Maps scraping) + Google Sheets (gspread OAuth2).
Se arranca con launch.bat que setea las variables de entorno y corre app.py.

Archivos principales:
- prospector.py (514 líneas): lógica de scraping Maps, limpieza, clasificación, volcado a Sheets
- app.py (~1400 líneas): interfaz web Flask con SSE, historial de corridas, cobertura de zonas
- historial.json: registro local de corridas (newest-first)

Google Sheet: https://docs.google.com/spreadsheets/d/1Koie8Rc0JNfDaMKqisaGzTIHKP4ie4-pW-z2tNTPLxo/
3 tabs Maps: "Leads FixLab - Talleres CABA (mayorista repuestos)" (698 filas, 16 cols),
             "Leads Fundas - Maps" (10 filas), "Leads Telefonos - Maps" (4 filas)

El tab Repuestos tiene columnas en orden diferente al estándar:
  A=Zona, B=Negocio, C=Direccion, D=Telefono, E=Reseñas, F=Rating, G=Tipo, H=Foco_Apple,
  I=Revisar_mayorista, J=Tipo_contacto, K=Web_o_red, L=Estado, M=Categoria, N=Sitio_web,
  O=Maps_URL, P=Place_ID
El script ya mapea por nombre de columna (no posicional), pero la columna "Reseñas" (con ñ)
no se está escribiendo porque internamente se llama "Resenas" (sin ñ) — esto es tarea P2.

Tarea inmediata: [DESCRIBIR AQUÍ LO QUE QUERÉS HACER]

Lee el archivo handoff.md en el directorio del proyecto para el contexto completo.
```

---

_Fin del documento de transferencia._
