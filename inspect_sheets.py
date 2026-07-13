"""Lee y muestra las primeras filas de cada tab para entender la estructura real."""
import os, pickle
import gspread
from google.auth.transport.requests import Request

TOKEN_FILE      = "token.pickle"
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")

TABS_MAPS = [
    "Leads FixLab - Talleres CABA (mayorista repuestos)",
    "Leads Fundas - Maps",
    "Leads Telefonos - Maps",
]

creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

gc = gspread.authorize(creds)
sh = gc.open_by_url(SPREADSHEET_URL)

for tab_name in TABS_MAPS:
    try:
        ws = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        print(f"\nSKIP: {tab_name}")
        continue

    print(f"\n{'='*60}")
    print(f"TAB: {tab_name}")
    all_values = ws.get_all_values()
    if not all_values:
        print("  (vacia)")
        continue

    headers = all_values[0]
    print(f"COLUMNAS ({len(headers)}): {headers}")
    print(f"FILAS DE DATOS: {len(all_values)-1}")
    print()

    # Mostrar primeras 5 filas y ultimas 3
    filas = all_values[1:]
    muestra = filas[:5] + (filas[-3:] if len(filas) > 8 else [])
    indices = list(range(2, 7)) + (list(range(len(filas)-1, len(filas)+2)) if len(filas) > 8 else [])

    for idx, fila in zip(indices, muestra):
        print(f"  Fila {idx}:")
        for j, (col, val) in enumerate(zip(headers, fila)):
            if val.strip():
                print(f"    [{j+1}] {col}: {val[:60]}")
        print()
