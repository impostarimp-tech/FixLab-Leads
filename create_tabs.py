"""Crea todas las tabs necesarias en el Google Sheet."""
import os, sys, pickle
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE             = "token.pickle"
SPREADSHEET_URL        = os.getenv("SPREADSHEET_URL", "")

MAPS_COLS = [
    "Zona", "Negocio", "Telefono", "Direccion", "Categoria",
    "Tipo", "Foco_Apple", "Revisar_mayorista",
    "Resenas", "Rating", "Sitio_web", "Maps_URL", "Place_ID",
]
IG_COLS = [
    "Negocio", "Username", "Seguidores", "Bio", "Telefono", "Email",
    "Sitio_web", "Ultimo_post", "Foco_Apple", "Revisar_mayorista",
    "Tipo_contacto", "Estado", "Instagram_URL",
]

TABS = [
    ("Leads Fundas - Maps",          MAPS_COLS),
    ("Leads Telefonos - Maps",       MAPS_COLS),
    ("Leads Instagram Fundas",       IG_COLS),
    ("Leads Instagram Telefonos",    IG_COLS),
]

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDENTIALS_FILE, scopes)
        creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

gc = gspread.authorize(creds)
sh = gc.open_by_url(SPREADSHEET_URL)

for tab_name, cols in TABS:
    try:
        sh.worksheet(tab_name)
        print(f"  Ya existe: '{tab_name}'")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(cols))
        ws.append_row(cols, value_input_option="USER_ENTERED")
        print(f"  [OK] Creada: '{tab_name}'")

print("\nListo.")
