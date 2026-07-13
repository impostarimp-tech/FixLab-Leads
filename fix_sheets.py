"""
Corrige filas desalineadas en el sheet de Repuestos.
El script escribe 13 cols en orden fijo, pero la tab tiene 16 cols con orden distinto.
Filas malas: Barrio tiene telefono, Telefono tiene direccion, etc.
"""
import os, pickle, re
import gspread
from google.auth.transport.requests import Request

TOKEN_FILE      = "token.pickle"
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")

creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

gc = gspread.authorize(creds)
sh = gc.open_by_url(SPREADSHEET_URL)

# ── Tab Repuestos (estructura customizada de 16 cols) ──────────────────────
ws = sh.worksheet("Leads FixLab - Talleres CABA (mayorista repuestos)")
all_values = ws.get_all_values()
headers = all_values[0]
print(f"Headers ({len(headers)}): {headers}\n")

# Indices reales de cada columna en la sheet
idx = {h: i for i, h in enumerate(headers)}
print("Mapeo de columnas:")
for k, v in idx.items():
    print(f"  col {v+1}: {k}")

# El script escribe en este orden (13 cols, posicional):
SCRIPT_COLS = ["Zona", "Negocio", "Telefono", "Direccion", "Categoria",
               "Tipo", "Foco_Apple", "Revisar_mayorista",
               "Resenas", "Rating", "Sitio_web", "Maps_URL", "Place_ID"]

def parece_telefono(v):
    v = str(v).strip().lstrip("+")
    return bool(re.match(r'^[\d\s\-\(\)]{7,}$', v)) and sum(c.isdigit() for c in v) >= 6

def parece_direccion(v):
    v = str(v).strip().lower()
    return any(k in v for k in ["av.", "avenida", "calle", "cdad", "buenos aires", "c1", "piso", "local", "depto"])

filas = all_values[1:]
malas = []

for i, fila in enumerate(filas, start=2):
    if not any(v.strip() for v in fila):
        continue
    barrio_val = fila[idx["Barrio"]] if "Barrio" in idx else ""
    tel_val    = fila[idx["Telefono"]] if "Telefono" in idx else ""

    # Fila mala: Barrio tiene un telefono O Telefono tiene una direccion
    if parece_telefono(barrio_val) or parece_direccion(tel_val):
        malas.append((i, fila))

print(f"\nFilas desalineadas detectadas: {len(malas)}")
for i, f in malas[:5]:
    print(f"  Fila {i}: Negocio='{f[idx['Negocio']]}' | Barrio='{f[idx['Barrio']]}' | Telefono='{f[idx['Telefono']]}'")
if len(malas) > 5:
    print(f"  ... y {len(malas)-5} mas")

if not malas:
    print("Todo alineado, nada que corregir.")
    exit()

input(f"\nPresiona Enter para corregir {len(malas)} filas (Ctrl+C para cancelar)...")

# Para cada fila mala:
# Los datos reales vienen en orden SCRIPT_COLS empezando desde col 1 (Zona)
# Los tenemos que redistribuir segun los headers reales del sheet
updates = []
ncols = len(headers)

for row_num, fila in malas:
    # Leer los 13 valores que escribio el script (cols A..M, indices 0..12)
    script_vals = fila[:13]
    script_data = dict(zip(SCRIPT_COLS, script_vals))

    # Construir nueva fila completa respetando el orden real del sheet
    nueva = [""] * ncols
    for col_name, col_idx in idx.items():
        if col_name in script_data:
            nueva[col_idx] = script_data[col_name]
        else:
            # Preservar valor existente para columnas manuales (Barrio, Tipo_contacto, etc.)
            nueva[col_idx] = fila[col_idx] if col_idx < len(fila) else ""

    # Limpiar Barrio y Categoria si tienen datos que no corresponden
    if "Barrio" in idx:
        barrio_actual = nueva[idx["Barrio"]]
        if parece_telefono(barrio_actual) or parece_direccion(barrio_actual):
            nueva[idx["Barrio"]] = ""

    rango = f"A{row_num}:{chr(64+ncols)}{row_num}"
    updates.append({"range": rango, "values": [nueva]})

ws.batch_update(updates, value_input_option="USER_ENTERED")
print(f"\n[OK] {len(updates)} filas corregidas en 'Leads FixLab - Talleres CABA'.")

# ── Tabs Fundas y Telefonos (estructura estandar, verificar) ──────────────
for tab_name in ["Leads Fundas - Maps", "Leads Telefonos - Maps"]:
    try:
        ws2 = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        continue
    vals2 = ws2.get_all_values()
    if len(vals2) < 2:
        continue
    h2 = vals2[0]
    malas2 = []
    for i, fila in enumerate(vals2[1:], start=2):
        zona_v = fila[0] if fila else ""
        neg_v  = fila[1] if len(fila) > 1 else ""
        # Zona no deberia ser un numero ni un telefono
        if parece_telefono(zona_v) or (neg_v and parece_telefono(neg_v) and not zona_v):
            malas2.append(i)
    if malas2:
        print(f"\n{tab_name}: {len(malas2)} filas potencialmente malas en filas {malas2[:10]}")
    else:
        print(f"\n{tab_name}: OK")

print("\n=== Listo ===")
