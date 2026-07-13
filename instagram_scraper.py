"""
FixLab Store - Instagram Lead Scraper
Estrategia de dos fuentes:
  1. Menciones de distribuidoras conocidas -> clientes que las etiquetan en posts
  2. Busqueda por username/keyword -> perfiles relevantes directos
Vuelca los datos en la tab "Leads Instagram" del Google Sheet.
"""

import argparse
import os
import sys
import pickle
import json as _json

import pandas as pd
from apify_client import ApifyClient
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

APIFY_API_TOKEN        = os.getenv("APIFY_API_TOKEN", "")
OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE             = "token.pickle"
SPREADSHEET_URL        = os.getenv("SPREADSHEET_URL", "")
CATEGORIAS_IG = {
    "repuestos": {
        "sheet_tab": "Leads Instagram",
        "distributor_accounts": [
            "bhtech.ba", "premiumcell_oficial", "infinitcell.ar",
            "todocelurepuestos", "todocelulanus", "smartparts_repuestos",
            "celupro_repuestos", "patagoniacell",
        ],
        "search_queries": [
            "fixlab", "fix", "tech", "lab",
            "reparaciones", "cell", "service", "repuestos",
        ],
    },
    "fundas": {
        "sheet_tab": "Leads Instagram Fundas",
        "distributor_accounts": [],
        "search_queries": [
            "fundas iphone", "carcasas iphone", "accesorios iphone",
            "accesorios apple", "funda iphone", "protector iphone",
        ],
    },
    "telefonos": {
        "sheet_tab": "Leads Instagram Telefonos",
        "distributor_accounts": [],
        "search_queries": [
            "iphone usado", "iphone seminuevo", "iphone reacondicionado",
            "compra venta iphone", "venta iphone", "celulares iphone",
        ],
    },
}

# Se sobreescriben en main() segun --categoria
SHEET_TAB_NAME       = CATEGORIAS_IG["repuestos"]["sheet_tab"]
DISTRIBUTOR_ACCOUNTS = CATEGORIAS_IG["repuestos"]["distributor_accounts"]
SEARCH_QUERIES       = CATEGORIAS_IG["repuestos"]["search_queries"]

MAX_MENTIONS_PER_ACCOUNT = 50
MAX_SEARCH_RESULTS       = 20
MAX_PROFILES_TO_SCRAPE   = 200

IG_COLUMNS = [
    "Negocio", "Username", "Seguidores", "Bio", "Telefono", "Email",
    "Sitio_web", "Ultimo_post", "Foco_Apple", "Revisar_mayorista",
    "Tipo_contacto", "Estado", "Instagram_URL",
]

PALABRAS_APPLE     = {"iphone", "apple", "mac", "ios", "airpod", "ipad"}
PALABRAS_MAYORISTA = {"repuesto", "mayorista", "insumo", "distribuidora", "al por mayor", "wholesale"}
PALABRAS_AR        = {"argentina", "buenos aires", "caba", " ba ", "cordoba", "rosario", "mendoza"}


# ──────────────────────────────────────────────
#  VALIDACION
# ──────────────────────────────────────────────

def validar_configuracion():
    errores = []
    if not APIFY_API_TOKEN:
        errores.append("APIFY_API_TOKEN no esta configurado.")
    if not SPREADSHEET_URL:
        errores.append("SPREADSHEET_URL no esta configurado.")
    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        errores.append(f"No se encontro '{OAUTH_CREDENTIALS_FILE}'.")
    if errores:
        print("\nERROR - Faltan configuraciones:")
        for e in errores:
            print(f"  - {e}")
        sys.exit(1)
    print("  [OK] APIFY_API_TOKEN presente")
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
#  FASE 1 - MENCIONES DE DISTRIBUIDORAS
# ──────────────────────────────────────────────

def scrape_mentions(client, distributor_urls, max_per_account):
    """
    Obtiene posts donde las distribuidoras son mencionadas/etiquetadas.
    El autor de cada post es un cliente activo de la distribuidora.
    """
    print(f"  Buscando menciones en {len(distributor_urls)} cuentas x {max_per_account} menciones max...")

    run = client.actor("apify/instagram-scraper").call(
        run_input={
            "directUrls":   distributor_urls,
            "resultsType":  "mentions",
            "resultsLimit": max_per_account,
            "proxy":        {"useApifyProxy": True},
        }
    )

    items = list(client.dataset(run.default_dataset_id).iterate_items())
    print(f"    -> {len(items)} menciones encontradas")

    # Extraer autores unicos de los posts que mencionan a las distribuidoras
    usuarios = {}
    for item in items:
        username = (item.get("ownerUsername") or "").strip()
        if not username:
            continue
        ts = item.get("timestamp", "")
        if username not in usuarios or ts > usuarios[username].get("timestamp", ""):
            usuarios[username] = {
                "username":  username,
                "full_name": (item.get("ownerFullName") or "").strip(),
                "timestamp": ts,
                "fuente":    "mencion",
            }

    print(f"    -> {len(usuarios)} cuentas unicas (autores de menciones)")
    return list(usuarios.values())


# ──────────────────────────────────────────────
#  FASE 2 - BUSQUEDA POR KEYWORD
# ──────────────────────────────────────────────

def scrape_user_search(client, queries, max_per_query):
    """
    Busca perfiles de Instagram por keyword.
    Retorna lista de profiles con datos basicos.
    """
    print(f"  Buscando perfiles por {len(queries)} keywords x {max_per_query} resultados...")

    todos = []
    for query in queries:
        print(f"    Buscando: '{query}'...")
        run = client.actor("apify/instagram-scraper").call(
            run_input={
                "search":       query,
                "searchType":   "user",
                "searchLimit":  max_per_query,
                "resultsType":  "details",
                "proxy":        {"useApifyProxy": True},
            }
        )
        items = list(client.dataset(run.default_dataset_id).iterate_items())
        print(f"      -> {len(items)} perfiles")
        todos.extend(items)

    return todos


# ──────────────────────────────────────────────
#  FASE 3 - DETALLES DE PERFILES (para menciones)
# ──────────────────────────────────────────────

def scrape_profiles(client, perfil_list, max_profiles):
    """Scrapea detalles completos de los perfiles de las menciones."""
    to_scrape    = perfil_list[:max_profiles]
    profile_urls = [f"https://www.instagram.com/{p['username']}/" for p in to_scrape]

    print(f"  Scrapeando detalles de {len(profile_urls)} perfiles (menciones)...")

    run = client.actor("apify/instagram-scraper").call(
        run_input={
            "directUrls":   profile_urls,
            "resultsType":  "details",
            "resultsLimit": 1,
            "proxy":        {"useApifyProxy": True},
        }
    )

    items = list(client.dataset(run.default_dataset_id).iterate_items())
    print(f"    -> {len(items)} perfiles obtenidos")
    return items


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


def _formatear_fecha(ts):
    if not ts:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return ts[:10]


def _es_argentina(bio, username):
    """Heuristica: la cuenta parece ser argentina."""
    texto = (bio + " " + username).lower()
    return any(w in texto for w in PALABRAS_AR)


# ──────────────────────────────────────────────
#  PROCESAMIENTO
# ──────────────────────────────────────────────

def normalizar_perfil(item, ts_map=None, fuente="busqueda"):
    """Convierte un item de Apify en un registro limpio."""
    username  = (item.get("username") or "").strip()
    if not username:
        return None

    bio       = (item.get("biography")            or "").strip()
    full_name = (item.get("fullName")              or "").strip()
    followers = int(item.get("followersCount")     or 0)
    email     = (item.get("businessEmail")         or "").strip()
    phone     = (item.get("businessPhoneNumber")   or "").strip()
    website   = (item.get("externalUrl")           or "").strip()

    ts_raw = ""
    if ts_map:
        ts_raw = ts_map.get(username, "")
    elif item.get("latestPosts"):
        ts_raw = (item["latestPosts"][0].get("timestamp") or "")

    return {
        "Negocio":           full_name or username,
        "Username":          username,
        "Seguidores":        followers,
        "Bio":               bio,
        "Telefono":          phone,
        "Email":             email,
        "Sitio_web":         website,
        "Ultimo_post":       _formatear_fecha(ts_raw),
        "Foco_Apple":        _foco_apple(bio, username),
        "Revisar_mayorista": _revisar_mayorista(bio),
        "Tipo_contacto":     _tipo_contacto(email, phone, website),
        "Estado":            "",
        "Instagram_URL":     f"https://www.instagram.com/{username}/",
    }


def construir_dataframe(mention_profiles, search_profiles, ts_map):
    registros = []

    for item in mention_profiles:
        r = normalizar_perfil(item, ts_map=ts_map, fuente="mencion")
        if r:
            registros.append(r)

    for item in search_profiles:
        r = normalizar_perfil(item, fuente="busqueda")
        if r:
            registros.append(r)

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
    parser = argparse.ArgumentParser(description="FixLab Instagram Lead Scraper")
    parser.add_argument("--accounts", type=int, default=None,
                        help="Cuantas distribuidoras usar para menciones")
    parser.add_argument("--mentions", type=int, default=MAX_MENTIONS_PER_ACCOUNT,
                        help="Menciones maximas por distribuidora")
    parser.add_argument("--categoria", default="repuestos",
                        choices=list(CATEGORIAS_IG.keys()),
                        help="Categoria: repuestos, fundas, telefonos")
    parser.add_argument("--test", action="store_true",
                        help="Modo prueba: 2 cuentas x 10 menciones + 1 busqueda")
    args = parser.parse_args()

    # Configurar globals segun categoria
    global SHEET_TAB_NAME, DISTRIBUTOR_ACCOUNTS, SEARCH_QUERIES
    cfg_ig = CATEGORIAS_IG[args.categoria]
    SHEET_TAB_NAME       = cfg_ig["sheet_tab"]
    DISTRIBUTOR_ACCOUNTS = cfg_ig["distributor_accounts"]
    SEARCH_QUERIES       = cfg_ig["search_queries"]

    print(f"\n=== FixLab Instagram Scraper — {args.categoria.upper()} ===")

    default_accounts = len(DISTRIBUTOR_ACCOUNTS) if DISTRIBUTOR_ACCOUNTS else 0

    if args.test:
        print("MODO PRUEBA - 2 cuentas x 10 menciones + 1 busqueda")
        n_accounts   = min(2, default_accounts)
        max_mentions = 10
        max_search   = 5
        n_queries    = 1
        max_profiles = 15
    else:
        n_accounts   = min(args.accounts or default_accounts, default_accounts)
        max_mentions = args.mentions
        max_search   = MAX_SEARCH_RESULTS
        n_queries    = len(SEARCH_QUERIES)
        max_profiles = MAX_PROFILES_TO_SCRAPE

    distributor_urls = [
        f"https://www.instagram.com/{u}/"
        for u in DISTRIBUTOR_ACCOUNTS[:n_accounts]
    ]
    queries_a_usar = SEARCH_QUERIES[:n_queries]

    costo_est = (
        n_accounts * max_mentions * 0.0027 +   # menciones
        n_queries  * max_search   * 0.0027 +   # busqueda
        max_profiles              * 0.0027      # perfiles detalle
    )
    print(f"Distribuidoras: {n_accounts} | Menciones: {max_mentions} | Busquedas: {n_queries}")
    print(f"Costo estimado maximo: ~${costo_est:.2f} USD")
    print()

    print("[0/5] Validando configuracion...")
    validar_configuracion()

    print("\n[PRE] Verificando conexion con Google Sheets...")
    ws, df_existentes = conectar_sheets()
    print("  [OK] Todo listo. Iniciando scraping...\n")

    client = ApifyClient(APIFY_API_TOKEN)

    # FASE 1: Menciones de distribuidoras
    print("[1/5] Fase 1 - Buscando menciones de distribuidoras...")
    perfiles_basicos = scrape_mentions(client, distributor_urls, max_mentions)

    # FASE 2: Busqueda por keyword
    print(f"\n[2/5] Fase 2 - Busqueda de usuarios por keyword...")
    search_profiles = scrape_user_search(client, queries_a_usar, max_search)
    print(f"  Total de busquedas: {len(search_profiles)} perfiles")

    # FASE 3: Detalles de los perfiles de menciones
    mention_profiles = []
    if perfiles_basicos:
        print(f"\n[3/5] Fase 3 - Obteniendo detalles de perfiles de menciones...")
        ts_map = {p["username"]: p.get("timestamp", "") for p in perfiles_basicos}
        mention_profiles = scrape_profiles(client, perfiles_basicos, max_profiles)
    else:
        ts_map = {}
        print("[3/5] Sin menciones encontradas, saltando fase 3.")

    bruto = len(mention_profiles) + len(search_profiles)
    print(f"\n  Total bruto: {bruto} perfiles\n")

    # PROCESO
    print("[4/5] Procesando y clasificando...")
    df = construir_dataframe(mention_profiles, search_profiles, ts_map)
    print(f"  Despues de limpieza: {len(df)} cuentas unicas")

    if not df.empty:
        apple_c     = (df["Foco_Apple"] == "Si").sum()
        mayorista_c = (df["Revisar_mayorista"] == "Si").sum()
        print(f"  Foco Apple: {apple_c} | Posible mayorista: {mayorista_c}")
    print()

    # SHEETS
    print("[5/5] Comparando con Google Sheets...")
    print(f"  Cuentas ya en planilla: {len(df_existentes)}")
    df_nuevos = filtrar_nuevos(df, df_existentes)
    print(f"  Cuentas nuevas encontradas: {len(df_nuevos)}")
    volcar_a_sheets(ws, df_nuevos)

    costo_real = (
        n_accounts * max_mentions                              * 0.0027 +
        n_queries  * max_search                               * 0.0027 +
        min(len(perfiles_basicos), max_profiles)              * 0.0027
    )
    print(f"  Costo real: ~${costo_real:.3f} USD")

    if not df_nuevos.empty:
        cols = ["Negocio", "Username", "Seguidores", "Foco_Apple", "Tipo_contacto", "Instagram_URL"]
        leads_out = df_nuevos[[c for c in cols if c in df_nuevos.columns]].fillna("").to_dict(orient="records")
        print(f"LEADS_JSON:{_json.dumps(leads_out, ensure_ascii=False)}")

    print("\n=== Listo ===\n")


if __name__ == "__main__":
    main()
