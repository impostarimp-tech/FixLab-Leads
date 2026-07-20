"""Reads leads from the 3 Google Sheet tabs and upserts them into the local
SQLite cache. Reuses the same OAuth2/token.pickle flow as prospector.py for
local desktop use. On a hosted deployment, authorizes either via a service
account (GOOGLE_SERVICE_ACCOUNT_JSON) or by reusing an already-authorized
user credential exported from a local token.pickle (GOOGLE_OAUTH_TOKEN_JSON)
-- the latter is for organizations whose Cloud policy blocks service account
key creation entirely. Never writes back to the Sheet."""
from __future__ import annotations

import json
import os
import pickle
import sqlite3

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

import routes_db as db
import routes_geocoding as geocoding

OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE = "token.pickle"
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")
SERVICE_ACCOUNT_JSON_ENV = "GOOGLE_SERVICE_ACCOUNT_JSON"
OAUTH_TOKEN_JSON_ENV = "GOOGLE_OAUTH_TOKEN_JSON"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

CATEGORIA_TABS = {
    "Repuestos": "Leads FixLab - Talleres CABA (mayorista repuestos)",
    "Fundas": "Leads Fundas - Maps",
    "Telefonos": "Leads Telefonos - Maps",
}


def get_sheets_client() -> gspread.Client:
    """Authorizes against Google Sheets, in priority order:
    1. GOOGLE_SERVICE_ACCOUNT_JSON -- a service account key, if the org allows
       creating one.
    2. GOOGLE_OAUTH_TOKEN_JSON -- a previously authorized user credential
       (exported from a working local token.pickle via export_oauth_token.py),
       refreshed as needed. No browser, no service account key required.
    3. Local desktop fallback: reuses token.pickle if valid/refreshable, or
       runs the interactive OAuth flow (same as prospector.py)."""
    service_account_json = os.getenv(SERVICE_ACCOUNT_JSON_ENV)
    if service_account_json:
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)

    oauth_token_json = os.getenv(OAUTH_TOKEN_JSON_ENV)
    if oauth_token_json:
        creds = UserCredentials.from_authorized_user_info(json.loads(oauth_token_json), scopes=SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return gspread.authorize(creds)

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        necesita_login = True
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                necesita_login = False
            except RefreshError:
                os.remove(TOKEN_FILE)

        if necesita_login:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return gspread.authorize(creds)


def _cell_str(row: dict, key: str) -> str:
    """Stringifies a Sheet cell value safely — gspread's get_all_records() returns
    numeric-looking cells (e.g. a phone number with no leading zero/dash) as int
    or float instead of str, which breaks a bare .strip() call."""
    value = row.get(key)
    return str(value).strip() if value else ""


def _cell_int(row: dict, key: str) -> int | None:
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cell_float(row: dict, key: str) -> float | None:
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_place_id(row: dict, categoria: str) -> str:
    """Real Place_ID when present; otherwise a synthetic key from category+name+address."""
    place_id = _cell_str(row, "Place_ID")
    if place_id:
        return place_id
    negocio = _cell_str(row, "Negocio").lower()
    direccion = _cell_str(row, "Direccion").lower()
    return f"NOID:{categoria}:{negocio}|{direccion}"


def sync_all_tabs_progress(conn: sqlite3.Connection, client: gspread.Client):
    """Same work as sync_all_tabs, but yields progress events as it goes:
    {"type": "log", "msg": str} for tab-level milestones,
    {"type": "progress", "actual": int, "total": int, "negocio": str} per lead geocoded,
    and a final {"type": "done", "summary": {...}}."""
    sh = client.open_by_url(SPREADSHEET_URL)
    nuevos = 0

    for categoria, tab_name in CATEGORIA_TABS.items():
        yield {"type": "log", "msg": f"Leyendo '{tab_name}'..."}
        ws = sh.worksheet(tab_name)
        nuevos_en_tab = 0
        for row in ws.get_all_records():
            negocio = _cell_str(row, "Negocio")
            if not negocio:
                continue
            place_id = _row_place_id(row, categoria)
            telefono = _cell_str(row, "Telefono")
            reviews_count = _cell_int(row, "Reseñas")
            rating = _cell_float(row, "Rating")
            existing = conn.execute(
                "SELECT id, telefono FROM leads_cache WHERE place_id = ?", (place_id,)
            ).fetchone()
            if existing:
                if not existing["telefono"] and telefono:
                    db.set_telefono(conn, existing["id"], telefono)
                db.set_reviews_rating(conn, existing["id"], reviews_count, rating)
                continue
            db.upsert_lead(
                conn,
                place_id,
                categoria,
                negocio,
                _cell_str(row, "Direccion"),
                _cell_str(row, "Maps_URL"),
                telefono,
                reviews_count,
                rating,
            )
            nuevos += 1
            nuevos_en_tab += 1
        yield {"type": "log", "msg": f"{tab_name}: {nuevos_en_tab} nuevos."}

    pendientes = db.get_pending_geocode(conn)
    total_pendientes = len(pendientes)
    if total_pendientes:
        yield {"type": "log", "msg": f"Geocodificando {total_pendientes} leads pendientes..."}

    geocodificados = 0
    fallidos = 0
    for i, row in enumerate(pendientes, start=1):
        coords, source = geocoding.geocode_lead(
            negocio=row["negocio"], direccion=row["direccion"], maps_url=row["maps_url"]
        )
        if coords:
            db.set_geocode_result(conn, row["id"], coords[0], coords[1], source)
            geocodificados += 1
        else:
            db.set_geocode_result(conn, row["id"], None, None, "fallido")
            fallidos += 1
        yield {
            "type": "progress",
            "actual": i,
            "total": total_pendientes,
            "negocio": row["negocio"],
        }

    summary = {"nuevos": nuevos, "geocodificados": geocodificados, "fallidos": fallidos}
    yield {"type": "done", "summary": summary}


def sync_all_tabs(conn: sqlite3.Connection, client: gspread.Client) -> dict:
    """Reads all 3 tabs, inserts new leads into leads_cache, geocodes pending/failed rows.
    Returns {"nuevos": int, "geocodificados": int, "fallidos": int}. Synchronous wrapper
    around sync_all_tabs_progress for callers that don't need progress events."""
    summary = None
    for event in sync_all_tabs_progress(conn, client):
        if event["type"] == "done":
            summary = event["summary"]
    return summary
