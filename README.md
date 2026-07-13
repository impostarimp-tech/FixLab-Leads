# FixLab Lead Prospector — Guía de configuración

## Paso 1 — Instalar dependencias

Abrí PowerShell en esta carpeta y ejecutá:

```powershell
pip install -r requirements.txt
```

---

## Paso 2 — Crear cuenta en Apify y obtener API token

1. Entrá a **https://apify.com** → crear cuenta gratuita (o usá Google).
2. Una vez adentro, andá a **Settings → Integrations → API token**.
3. Copiá el token (empieza con `apify_api_...`).
4. Plan gratuito: **$5 de crédito mensual** — alcanza para ~300-500 resultados por mes.  
   Si necesitás más, el plan Starter cuesta $49/mes.

> El actor `compass/crawler-google-places` cobra aprox. $0.002 por resultado.  
> Con 5 búsquedas × 150 resultados = 750 registros ≈ $1.50 por corrida.

---

## Paso 3 — Conectar Google Sheets

### 3a. Crear proyecto en Google Cloud

1. Entrá a **https://console.cloud.google.com**.
2. Arriba a la izquierda, hacé clic en el selector de proyecto → **Nuevo proyecto**.  
   Nombre: `fixlab-leads` → Crear.
3. Activá las APIs necesarias:  
   - Buscá "Google Sheets API" → Habilitar  
   - Buscá "Google Drive API" → Habilitar

### 3b. Crear cuenta de servicio

1. En el menú: **IAM y administración → Cuentas de servicio → Crear cuenta de servicio**.  
   - Nombre: `fixlab-sheets`  
   - Rol: **Editor** (o "Básico → Editor")  
   - Crear y continuar → Listo.
2. Hacé clic en la cuenta de servicio creada → pestaña **Claves** → **Agregar clave → JSON**.
3. Se descarga un archivo JSON → **renombralo `google_credentials.json`** y copialo  
   a la misma carpeta que `prospector.py`.

### 3c. Compartir la planilla con la cuenta de servicio

1. Abrí el archivo JSON recién descargado y copiá el valor de `"client_email"`.  
   Tiene este formato: `fixlab-sheets@fixlab-leads.iam.gserviceaccount.com`
2. Abrí tu Google Sheet → botón **Compartir** → pegá ese email → rol **Editor** → Listo.

---

## Paso 4 — Configurar el script

Abrí `run_weekly.bat` con el Bloc de notas y reemplazá:

```
set APIFY_API_TOKEN=TU_TOKEN_AQUI
```
por tu token de Apify.

```
set SPREADSHEET_URL=TU_LINK_DE_GOOGLE_SHEETS_AQUI
```
por la URL completa de tu planilla (la de la barra del navegador).

---

## Paso 5 — Primera corrida manual

Hacé doble clic en `run_weekly.bat`.  
El script va a:
1. Buscar talleres en CABA
2. Limpiarlos y clasificarlos
3. Agregarlos a tu planilla

---

## Paso 6 — Automatización semanal (Programador de tareas de Windows)

1. Buscá "Programador de tareas" en el menú Inicio → Abrir.
2. Panel derecho → **Crear tarea básica**.
3. Nombre: `FixLab Lead Prospector`
4. Desencadenador: **Semanal** → día y hora que quieras (ej: lunes 9:00 AM)
5. Acción: **Iniciar un programa**  
   - Programa: ruta completa a `run_weekly.bat`  
     ej: `C:\Users\Jonathan\fixlab-leads\run_weekly.bat`
6. Finalizar.

---

## Uso desde línea de comandos

```powershell
# CABA (default)
python prospector.py

# Otra zona
python prospector.py --zona "Quilmes, Buenos Aires, Argentina"

# Limitar resultados (más barato)
python prospector.py --zona "Palermo, Buenos Aires, Argentina" --max 50
```

---

## Columnas que se agregan a la planilla

| Columna | Descripción |
|---|---|
| Nombre | Nombre del negocio en Google Maps |
| Teléfono | Teléfono listado en Maps |
| Dirección | Dirección completa |
| Categoría | Categoría de Google Maps |
| Tipo | Cadena / Independiente alto volumen / Independiente chico-mediano |
| Foco_Apple | Sí (menciona apple/iphone/mac) / Multimarca |
| Revisar_mayorista | Sí si el nombre sugiere revendedor de repuestos |
| Reseñas | Cantidad de reseñas en Google |
| Rating | Calificación promedio |
| Sitio_web | Web del negocio |
| Maps_URL | Link directo a Google Maps |
| Place_ID | ID único de Google Places (evita duplicados entre corridas) |

---

## Agregar nuevas cadenas conocidas

Abrí `prospector.py` y editá el set `CADENAS_CONOCIDAS` (línea ~50).
