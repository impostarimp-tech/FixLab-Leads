"""Script de una sola vez: crea la tab 'Leads Instagram' en el Sheet."""
import os, sys, pickle
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE             = "token.pickle"
SPREADSHEET_URL        = os.getenv("SPREADSHEET_URL", "")
SHEET_TAB_NAME         = "Leads Instagram"

IG_COLUMNS = [
    "Negocio", "Username", "Seguidores", "Bio", "Telefono", "Email",
    "Sitio_web", "Ultimo_post", "Foco_Apple", "Revisar_mayorista",
    "Tipo_contacto", "Estado", "Instagram_URL",
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

try:
    ws = sh.worksheet(SHEET_TAB_NAME)
    print(f"La tab '{SHEET_TAB_NAME}' ya existe.")
except gspread.exceptions.WorksheetNotFound:
    ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=len(IG_COLUMNS))
    ws.append_row(IG_COLUMNS, value_input_option="USER_ENTERED")
    print(f"[OK] Tab '{SHEET_TAB_NAME}' creada con {len(IG_COLUMNS)} columnas.")

print("Columnas:", IG_COLUMNS)
