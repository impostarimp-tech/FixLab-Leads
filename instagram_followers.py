"""
FixLab Store - Instagram Followers Scraper (via Instaloader)
Scrapea los seguidores de las distribuidoras de referencia usando
una cuenta propia de Instagram. Sin costo por resultado.

Limites de seguridad:
  - Pausa de 3-6 segundos entre perfiles
  - Max 150 seguidores por cuenta (Instagram limita ~200/hora en total)
  - Pausa de 60 segundos entre cuentas
"""

import argparse
import os
import sys
import time
import pickle
import random
import json as _json

import instaloader
import pandas as pd
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

IG_USERNAME            = os.getenv("IG_USERNAME", "")
IG_PASSWORD            = os.getenv("IG_PASSWORD", "")
OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE             = "token.pickle"
SPREADSHEET_URL        = os.getenv("SPREADSHEET_URL", "")
SHEET_TAB_NAME         = "Leads Instagram"

DISTRIBUTOR_ACCOUNTS = [
    "bhtech.ba",
    "premiumcell_oficial",
    "infinitcell.ar",
    "todocelurepuestos",
    "todocelulanus",
    "smartparts_repuestos",
    "celupro_repuestos",
    "patagoniacell",
]

MAX_FOLLOWERS_PER_ACCOUNT = 150
PAUSE_BETWEEN_PROFILES    = (3, 6)   # segundos, aleatorio
PAUSE_BETWEEN_ACCOUNTS    = 60       # segundos

IG_COLUMNS = [
    "Negocio", "Username", "Seguidores", "Bio", "Telefono", "Email",
    "Sitio_web", "Ultimo_post", "Foco_Apple", "Revisar_mayorista",
    "Tipo_contacto", "Estado", "Instagram_URL",
]

PALABRAS_APPLE     = {"iphone", "apple", "mac", "ios", "airpod", "ipad"}
PALABRAS_MAYORISTA = {"repuesto", "mayorista", "insumo", "distribuidora", "al por mayor", "wholesale"}


# ──────────────────────────────────────────────
#  VALIDACION
# ──────────────────────────────────────────────

def validar_configuracion():
    errores = []
    if not IG_USERNAME:
        errores.append("IG_USERNAME no configurado.")
    if not IG_PASSWORD:
        errores.append("IG_PASSWORD no configurado.")
    if not SPREADSHEET_URL:
        errores.append("SPREADSHEET_URL no configurado.")
    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        errores.append(f"No se encontro '{OAUTH_CREDENTIALS_FILE}'.")
    if errores:
        print("\nERROR - Faltan configuraciones:")
        for e in errores:
            print(f"  - {e}")
        sys.exit(1)
    print("  [OK] IG_USERNAME presente")
    print("  [OK] IG_PASSWORD presente")
    print("  [OK] SPREADSHEET_URL presente")
    print("  [OK] oauth_credentials.json presente")


# ──────────────────────────────────────────────
#  GOOGLE SHEETS
# ──────────────────────────────────────────────

def conectar_sheets():
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
        print(f"  [OK] Tab '{SHEET_TAB_NAME}' encontrada.")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=len(IG_COLUMNS))
        ws.append_row(IG_COLUMNS, value_input_option="USER_ENTERED")
        print(f"  [OK] Tab '{SHEET_TAB_NAME}' creada con encabezados.")

    datos = ws.get_all_records()
    df_existentes = pd.DataFrame(datos) if datos else pd.DataFrame()
    print(f"  [OK] Cuentas ya en planilla: {len(df_existentes)}")
    return ws, df_existentes


# ──────────────────────────────────────────────
#  INSTALOADER - LOGIN
# ──────────────────────────────────────────────

def login_instaloader():
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )

    # Instaloader guarda la sesion en el directorio del usuario con este nombre
    session_file = os.path.join(
        os.path.expanduser("~"),
        f".instaloader-session-{IG_USERNAME}"
    )
    # Tambien buscar en el directorio del script (si se genero ahi)
    session_file_local = f"ig_session_{IG_USERNAME}"

    archivo = None
    if os.path.exists(session_file):
        archivo = session_file
    elif os.path.exists(session_file_local):
        archivo = session_file_local

    if not archivo:
        print("ERROR: No se encontro sesion guardada de Instagram.")
        print("  Ejecuta 'ig_login.bat' una vez para crear la sesion.")
        print(f"  Archivo esperado: {session_file}")
        sys.exit(1)

    try:
        L.load_session_from_file(IG_USERNAME, archivo)
        print(f"  [OK] Sesion cargada para @{IG_USERNAME}")
    except Exception as e:
        print(f"ERROR: No se pudo cargar la sesion: {e}")
        print("  Ejecuta 'ig_login.bat' para renovar la sesion.")
        sys.exit(1)

    return L


# ──────────────────────────────────────────────
#  SCRAPING DE SEGUIDORES
# ──────────────────────────────────────────────

def scrape_followers_of(L, username, max_followers, test_mode=False):
    """Obtiene los seguidores de una cuenta distribuidora."""
    print(f"  Scrapeando seguidores de @{username}...")

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"    AVISO: @{username} no existe o es privada, saltando.")
        return []
    except Exception as e:
        print(f"    AVISO: No se pudo cargar @{username}: {e}")
        return []

    if profile.is_private:
        print(f"    AVISO: @{username} es privada, no se puede acceder a seguidores.")
        return []

    followers = []
    count = 0

    try:
        for follower in profile.get_followers():
            if count >= max_followers:
                break

            followers.append({
                "username":  follower.username,
                "full_name": follower.full_name or "",
                "bio":       follower.biography or "",
                "followers": follower.followers,
                "following": follower.followees,
                "is_business": follower.is_business_account,
                "external_url": follower.external_url or "",
                "is_private":   follower.is_private,
            })
            count += 1

            # Pausa entre perfiles para no triggear rate limit
            if not test_mode:
                time.sleep(random.uniform(*PAUSE_BETWEEN_PROFILES))

            if count % 25 == 0:
                print(f"    -> {count} seguidores procesados...")

    except instaloader.exceptions.QueryReturnedBadRequestException:
        print(f"    AVISO: Instagram limito la consulta en @{username}. Pausando 120s...")
        time.sleep(120)
    except instaloader.exceptions.ConnectionException as e:
        print(f"    AVISO: Error de conexion en @{username}: {e}")

    print(f"    -> {len(followers)} seguidores obtenidos de @{username}")
    return followers


# ──────────────────────────────────────────────
#  CLASIFICACION
# ──────────────────────────────────────────────

def _foco_apple(bio, username):
    texto = (bio + " " + username).lower()
    return "Si" if any(w in texto for w in PALABRAS_APPLE) else "Multimarca"


def _revisar_mayorista(bio):
    return "Si" if any(w in bio.lower() for w in PALABRAS_MAYORISTA) else "No"


def _tipo_contacto(email, telefono, sitio_web):
    tipos = []
    if email:     tipos.append("Email")
    if telefono:  tipos.append("Telefono")
    if sitio_web: tipos.append("Web")
    return " / ".join(tipos) if tipos else "DM"


KEYWORDS_TELEFONIA = {
    # reparación / servicio técnico
    "repair", "fix", "taller", "reparacion", "reparación", "tecnico", "técnico",
    # productos / partes
    "iphone", "apple", "celular", "repuesto", "repuestos",
    "insumo", "pantalla", "bateria", "batería", "carcasa", "modulo", "módulo",
    # términos del rubro
    "gsm", "lab", "fixlab", "cell", "movil", "móvil", "smartphone",
}

def _es_probable_negocio(perfil):
    """Filtra cuentas relacionadas con telefonía/reparación de celulares."""
    bio      = perfil.get("bio", "").lower()
    username = perfil.get("username", "").lower()
    texto    = bio + " " + username
    return any(k in texto for k in KEYWORDS_TELEFONIA)


# ──────────────────────────────────────────────
#  PROCESAMIENTO
# ──────────────────────────────────────────────

def construir_dataframe(todos_followers):
    registros = []
    for p in todos_followers:
        username = p.get("username", "").strip()
        if not username:
            continue
        if p.get("is_private"):
            continue  # privadas: no podemos ver nada util

        bio       = p.get("bio", "").strip()
        full_name = p.get("full_name", "").strip()
        followers = p.get("followers", 0)
        website   = p.get("external_url", "").strip()

        registros.append({
            "Negocio":           full_name or username,
            "Username":          username,
            "Seguidores":        followers,
            "Bio":               bio,
            "Telefono":          "",
            "Email":             "",
            "Sitio_web":         website,
            "Ultimo_post":       "",
            "Foco_Apple":        _foco_apple(bio, username),
            "Revisar_mayorista": _revisar_mayorista(bio),
            "Tipo_contacto":     _tipo_contacto("", "", website),
            "Estado":            "",
            "Instagram_URL":     f"https://www.instagram.com/{username}/",
        })

    if not registros:
        return pd.DataFrame(columns=IG_COLUMNS)

    df = pd.DataFrame(registros)
    df = df.drop_duplicates(subset="Username").reset_index(drop=True)
    return df


def filtrar_nuevos(df_nuevos, df_existentes):
    if df_existentes.empty or "Username" not in df_existentes.columns:
        return df_nuevos
    existentes = set(df_existentes["Username"].str.lower().str.strip().tolist())
    mask = ~df_nuevos["Username"].str.lower().str.strip().isin(existentes)
    return df_nuevos[mask].reset_index(drop=True)


def volcar_a_sheets(ws, df):
    if df.empty:
        print("  No hay cuentas nuevas para agregar.")
        return
    filas = df[IG_COLUMNS].fillna("").values.tolist()
    ws.append_rows(filas, value_input_option="USER_ENTERED")
    print(f"  [OK] {len(filas)} cuentas nuevas agregadas a la planilla.")


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FixLab Instagram Followers Scraper")
    parser.add_argument("--accounts", type=int, default=len(DISTRIBUTOR_ACCOUNTS),
                        help="Cuantas distribuidoras scrapear")
    parser.add_argument("--max", type=int, default=MAX_FOLLOWERS_PER_ACCOUNT,
                        help="Max seguidores por cuenta")
    parser.add_argument("--test", action="store_true",
                        help="Modo prueba: 2 cuentas x 20 seguidores, sin pausas largas")
    args = parser.parse_args()

    print("\n=== FixLab Instagram Followers Scraper (Instaloader) ===")

    if args.test:
        print("MODO PRUEBA - 2 cuentas x 20 seguidores")
        n_accounts   = 2
        max_followers = 20
        test_mode    = True
    else:
        n_accounts    = max(1, min(args.accounts, len(DISTRIBUTOR_ACCOUNTS)))
        max_followers = args.max
        test_mode     = False

    accounts_a_usar = DISTRIBUTOR_ACCOUNTS[:n_accounts]
    total_estimado  = n_accounts * max_followers
    print(f"Cuentas: {n_accounts} | Max por cuenta: {max_followers} | Total estimado: {total_estimado}")
    print(f"Costo: $0.00 (Instaloader, sin Apify)")
    print()

    print("[0/4] Validando configuracion...")
    validar_configuracion()

    print("\n[PRE] Verificando conexion con Google Sheets...")
    ws, df_existentes = conectar_sheets()

    print(f"\n[1/4] Login en Instagram como @{IG_USERNAME}...")
    L = login_instaloader()
    print("  [OK] Conectado a Instagram\n")

    print(f"[2/4] Scrapeando y volcando cuenta por cuenta...")
    perfiles_procesados = 0
    total_escritos      = 0
    todos_leads         = []

    for i, account in enumerate(accounts_a_usar):
        print(f"\n  [{i+1}/{n_accounts}] @{account}")
        raw = scrape_followers_of(L, account, max_followers, test_mode)
        perfiles_procesados += len(raw)

        # Procesar y filtrar esta cuenta de inmediato
        df_cuenta = construir_dataframe(raw)
        mask = df_cuenta.apply(lambda r: _es_probable_negocio({
            "bio": r["Bio"], "username": r["Username"],
        }), axis=1)
        df_cuenta   = df_cuenta[mask].reset_index(drop=True)
        df_nuevos_c = filtrar_nuevos(df_cuenta, df_existentes)

        if not df_nuevos_c.empty:
            volcar_a_sheets(ws, df_nuevos_c)
            # Agregar a existentes para evitar duplicados entre cuentas
            df_existentes = pd.concat([df_existentes, df_nuevos_c]).reset_index(drop=True)
            total_escritos += len(df_nuevos_c)
            todos_leads.extend(df_nuevos_c.to_dict(orient="records"))
            print(f"  -> {len(df_nuevos_c)} leads nuevos escritos al Sheet (total: {total_escritos})")
        else:
            print(f"  -> Sin leads nuevos relevantes en @{account}")

        # Progreso para la barra en la UI
        print(f"PROGRESS:{perfiles_procesados}/{total_estimado}", flush=True)

        if i < len(accounts_a_usar) - 1 and not test_mode:
            print(f"  Pausa entre cuentas ({PAUSE_BETWEEN_ACCOUNTS}s)...")
            time.sleep(PAUSE_BETWEEN_ACCOUNTS)

    print(f"\n  Total bruto: {perfiles_procesados} seguidores procesados")
    print(f"  Total leads escritos: {total_escritos}")
    print(f"  Costo real: $0.00 USD (Instaloader)")

    if todos_leads:
        cols = ["Negocio", "Username", "Seguidores", "Foco_Apple", "Tipo_contacto", "Instagram_URL"]
        leads_out = [{c: r.get(c, "") for c in cols if c in r} for r in todos_leads]
        print(f"LEADS_JSON:{_json.dumps(leads_out, ensure_ascii=False)}")

    print("\n=== Listo ===\n")


if __name__ == "__main__":
    main()
