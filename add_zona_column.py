"""Inserta columna 'Zona' como primera columna en las tabs de Maps que ya existen."""
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
        print(f"  SKIP (no existe): '{tab_name}'")
        continue

    headers = ws.row_values(1)
    if headers and headers[0] == "Zona":
        print(f"  Ya tiene Zona: '{tab_name}'")
        continue

    # Inserta columna en posicion 1 (A)
    ws.insert_cols([[]], col=1)
    ws.update_cell(1, 1, "Zona")
    print(f"  [OK] Columna Zona agregada: '{tab_name}'")

print("\nListo.")
