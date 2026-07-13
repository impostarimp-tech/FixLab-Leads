"""Reads leads from the 3 Google Sheet tabs and upserts them into the local
SQLite cache. Reuses the same OAuth2/token.pickle flow as prospector.py.
Never writes back to the Sheet."""
from __future__ import annotations

import os
import pickle
import sqlite3

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

import routes_db as db
import routes_geocoding as geocoding

OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE = "token.pickle"
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")

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
    """Authorizes against Google Sheets, reusing token.pickle if valid/refreshable,
    otherwise runs the interactive OAuth flow (same as prospector.py)."""
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


def _row_place_id(row: dict, categoria: str) -> str:
    """Real Place_ID when present; otherwise a synthetic key from category+name+address."""
    place_id = (row.get("Place_ID") or "").strip()
    if place_id:
        return place_id
    negocio = (row.get("Negocio") or "").strip().lower()
    direccion = (row.get("Direccion") or "").strip().lower()
    return f"NOID:{categoria}:{negocio}|{direccion}"


def sync_all_tabs(conn: sqlite3.Connection, client: gspread.Client) -> dict:
    """Reads all 3 tabs, inserts new leads into leads_cache, geocodes pending/failed rows.
    Returns {"nuevos": int, "geocodificados": int, "fallidos": int}."""
    sh = client.open_by_url(SPREADSHEET_URL)
    nuevos = 0

    for categoria, tab_name in CATEGORIA_TABS.items():
        ws = sh.worksheet(tab_name)
        for row in ws.get_all_records():
            negocio = (row.get("Negocio") or "").strip()
            if not negocio:
                continue
            place_id = _row_place_id(row, categoria)
            existing = conn.execute(
                "SELECT id FROM leads_cache WHERE place_id = ?", (place_id,)
            ).fetchone()
            if existing:
                continue
            db.upsert_lead(
                conn,
                place_id,
                categoria,
                negocio,
                (row.get("Direccion") or "").strip(),
                (row.get("Maps_URL") or "").strip(),
            )
            nuevos += 1

    geocodificados = 0
    fallidos = 0
    for row in db.get_pending_geocode(conn):
        coords, source = geocoding.geocode_lead(
            negocio=row["negocio"], direccion=row["direccion"], maps_url=row["maps_url"]
        )
        if coords:
            db.set_geocode_result(conn, row["id"], coords[0], coords[1], source)
            geocodificados += 1
        else:
            db.set_geocode_result(conn, row["id"], None, None, "fallido")
            fallidos += 1

    return {"nuevos": nuevos, "geocodificados": geocodificados, "fallidos": fallidos}
