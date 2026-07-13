"""
Corrige filas mal alineadas del tab Repuestos usando batch update (1 sola llamada API).
- Filas con direccion en columna Barrio en vez de Direccion: se mueven
- Filas con negocios irrelevantes: se eliminan
"""
import os
import pickle
import gspread
from google.auth.transport.requests import Request

TOKEN_FILE      = "token.pickle"
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")
TAB_NAME        = "Leads FixLab - Talleres CABA (mayorista repuestos)"

NEGOCIOS_IRRELEVANTES = {"Aon Risk Services Argentina S.A."}

creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

gc = gspread.authorize(creds)
ws = gc.open_by_url(SPREADSHEET_URL).worksheet(TAB_NAME)

all_values = ws.get_all_values()
headers = all_values[0]
col = {h: i for i, h in enumerate(headers)}

print(f"Total filas (con header): {len(all_values)}")
print(f"Col Barrio: {col.get('Barrio')}  Col Direccion: {col.get('Direccion')}")

# ── Paso 1: detectar filas a corregir y construir batch ──────────────────────
col_barrio_letter = chr(ord('A') + col['Barrio'])
col_direc_letter  = chr(ord('A') + col['Direccion'])

batch_updates = []   # lista de {range, values} para batch_update
rows_to_delete = []  # sheet rows 1-indexed, se eliminan al final (de abajo hacia arriba)

fixed_count = 0

for i in range(1, len(all_values)):  # 1-indexed data rows (skip header)
    row = all_values[i]
    negocio    = row[col['Negocio']]    if 'Negocio'    in col else ''
    barrio_val = row[col['Barrio']]     if 'Barrio'     in col else ''
    direc_val  = row[col['Direccion']]  if 'Direccion'  in col else ''

    if negocio in NEGOCIOS_IRRELEVANTES:
        rows_to_delete.append(i + 1)  # 1-indexed sheet row
        safe_n = negocio[:50].encode('ascii', 'replace').decode()
        print(f"  -> ELIMINAR fila {i+1}: '{safe_n}'")
        continue

    # Detectar: Barrio tiene direccion Y Direccion esta vacia
    es_direccion = (
        barrio_val and not direc_val and (
            "Buenos Aires" in barrio_val or
            "Cdad." in barrio_val or
            any(c.isdigit() for c in barrio_val[:10])
        )
    )

    if es_direccion:
        sheet_row = i + 1
        # Limpiar Barrio
        batch_updates.append({
            "range": f"{col_barrio_letter}{sheet_row}",
            "values": [[""]],
        })
        # Poner direccion en Direccion
        batch_updates.append({
            "range": f"{col_direc_letter}{sheet_row}",
            "values": [[barrio_val]],
        })
        fixed_count += 1

print(f"\nFilas a corregir: {fixed_count}")
print(f"Filas a eliminar: {len(rows_to_delete)}")

# ── Paso 2: aplicar batch update (1 llamada) ─────────────────────────────────
if batch_updates:
    ws.batch_update(batch_updates, value_input_option="USER_ENTERED")
    print(f"[OK] {fixed_count} filas corregidas via batch")

# ── Paso 3: eliminar filas irrelevantes (de abajo hacia arriba) ──────────────
for sheet_row in sorted(rows_to_delete, reverse=True):
    ws.delete_rows(sheet_row)
    print(f"[OK] Fila {sheet_row} eliminada")

# ── Verificacion final ────────────────────────────────────────────────────────
all_values = ws.get_all_values()
print(f"\nTotal filas final: {len(all_values)}")
print("=== Ultimas 5 filas ===")
for i, row in enumerate(all_values[-5:], start=len(all_values)-4):
    negocio   = row[col['Negocio']][:35].encode('ascii','replace').decode() if 'Negocio' in col else ''
    barrio_v  = row[col['Barrio']][:25].encode('ascii','replace').decode()  if 'Barrio'  in col else ''
    direc_v   = row[col['Direccion']][:35].encode('ascii','replace').decode() if 'Direccion' in col else ''
    print(f"  Fila {i}: '{negocio}' | Barrio='{barrio_v}' | Dir='{direc_v}'")
