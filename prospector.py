"""
FixLab Store - B2B Lead Prospector
Busca talleres de reparacion de celulares en Google Maps via Apify
y los vuelca en Google Sheets, sin pisar leads ya existentes.

Uso:
    python prospector.py                          # corrida completa CABA
    python prospector.py --test                   # prueba barata: 1 busqueda x 10 resultados (~$0.02)
    python prospector.py --zona "Quilmes, Buenos Aires, Argentina"
    python prospector.py --zona "Palermo, Buenos Aires, Argentina" --max 50
"""

import argparse
import json
import os
import sys
import time
import pickle

import pandas as pd
from apify_client import ApifyClient
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

# ──────────────────────────────────────────────
#  CONFIGURACION - edita solo esta seccion
# ──────────────────────────────────────────────

APIFY_API_TOKEN      = os.getenv("APIFY_API_TOKEN", "")
OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE           = "token.pickle"
SPREADSHEET_URL      = os.getenv("SPREADSHEET_URL", "")
ZONA_DEFAULT = "Ciudad Autonoma de Buenos Aires, Argentina"
MAX_PLACES_PER_SEARCH = 60

CATEGORIAS = {
    "repuestos": {
        "sheet_tab": "Leads FixLab - Talleres CABA (mayorista repuestos)",
        "search_terms": [
            "servicio tecnico celulares",
            "reparacion iphone",
            "repuestos celulares",
            "taller iphone",
            "repuestos iphone",
            "reparacion pantalla iphone",
        ],
    },
    "fundas": {
        "sheet_tab": "Leads Fundas - Maps",
        "search_terms": [
            "fundas iphone",
            "accesorios iphone",
            "funda celular",
            "distribuidor accesorios celular",
            "accesorios apple",
            "mayorista fundas celular",
        ],
    },
    "telefonos": {
        "sheet_tab": "Leads Telefonos - Maps",
        "search_terms": [
            "iphone usado",
            "compra venta iphone",
            "phone store",
            "celular usado",
            "compra celulares usados",
            "iphone outlet",
        ],
    },
}

# Se sobreescriben en main() segun --categoria
SHEET_TAB_NAME   = CATEGORIAS["repuestos"]["sheet_tab"]
SEARCH_TERMS     = CATEGORIAS["repuestos"]["search_terms"]
CATEGORIA_ACTUAL = "repuestos"

# ──────────────────────────────────────────────
#  CLASIFICACION
# ──────────────────────────────────────────────

# Categorias de Google Maps que SI son relevantes para cada categoria de busqueda
CATEGORIAS_MAPS_REPUESTOS = {
    "tienda de telefonia", "servicio tecnico de telefonos moviles",
    "tienda de telefonos moviles", "tienda de informatica",
    "reparacion de telefonos moviles", "tienda de electronica",
    "centro de reparacion", "taller de reparacion",
    "tienda de computadoras", "tienda de accesorios de telefono",
}
CATEGORIAS_MAPS_FUNDAS = {
    "tienda de accesorios de telefono", "tienda de telefonia",
    "tienda de telefonos moviles", "tienda de electronica",
    "tienda de accesorios moviles", "tienda de gadgets",
    "tienda de articulos electronicos",
}
CATEGORIAS_MAPS_TELEFONOS = {
    "tienda de telefonos moviles", "tienda de telefonia",
    "tienda de electronica", "tienda de articulos de segunda mano",
    "tienda de informatica", "tienda de accesorios de telefono",
}

# Palabras que SI deben aparecer en el nombre para ser relevantes
KEYWORDS_NOMBRE_REPUESTOS = {
    "celular", "phone", "iphone", "apple", "mac", "tech", "fix", "repair",
    "service", "servicio", "reparacion", "taller", "repuesto", "pantalla",
    "movil", "gsm", "lab", "cell", "electronica", "samsung", "android",
    "informatica", "computacion", "digital",
}
KEYWORDS_NOMBRE_FUNDAS = {
    "celular", "phone", "iphone", "apple", "tech", "movil", "cell",
    "accesorios", "funda", "carcasa", "cover", "case", "store",
    "electronica", "digital", "gadget", "smart",
}
KEYWORDS_NOMBRE_TELEFONOS = {
    "celular", "phone", "iphone", "apple", "movil", "cell",
    "electronica", "digital", "samsung", "store", "tech",
}

CADENAS_CONOCIDAS = {
    "gofix", "ifixcenter", "fix station", "case store fix",
    "orduna smartfix", "machelp", "tecnoland", "macstation",
    "appledoctor", "apple kingdom", "imark store", "megastation",
    "view phone", "oncelular", "grupo gb", "celtec",
}

PALABRAS_MAYORISTA = {"repuestos", "insumos", "mayorista", "distribuidora"}

MARCAS_EXCLUIR = {
    "samsung store", "motorola store", "xiaomi store", "huawei store",
    "apple store", "authorized reseller", "premium reseller",
}

# ──────────────────────────────────────────────
#  PASO 0 - VALIDACION (antes de gastar credito)
# ──────────────────────────────────────────────

def validar_configuracion():
    """Verifica todo antes de hacer cualquier llamada a Apify."""
    errores = []

    if not APIFY_API_TOKEN:
        errores.append("APIFY_API_TOKEN no esta configurado.")

    if not SPREADSHEET_URL:
        errores.append("SPREADSHEET_URL no esta configurado.")

    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        errores.append(f"No se encontro '{OAUTH_CREDENTIALS_FILE}'. Descargalo de Google Cloud.")

    if errores:
        print("\nERROR - Faltan configuraciones:")
        for e in errores:
            print(f"  - {e}")
        sys.exit(1)

    print("  [OK] APIFY_API_TOKEN presente")
    print("  [OK] SPREADSHEET_URL presente")
    print("  [OK] oauth_credentials.json presente")


def validar_sheets():
    """Intenta conectar a Google Sheets y verifica que la hoja existe."""
    print("\n[PRE] Verificando conexion con Google Sheets...")
    ws, df = cargar_sheets()
    print(f"  [OK] Hoja encontrada: '{SHEET_TAB_NAME}'")
    print(f"  [OK] Filas actuales en la planilla: {len(df)}")
    return ws, df


# ──────────────────────────────────────────────
#  PASO 1 - APIFY
# ──────────────────────────────────────────────

def buscar_en_apify(zona: str, max_por_busqueda: int, terminos: list) -> list[dict]:
    """Lanza el actor de Google Places en Apify y devuelve los resultados crudos."""
    client = ApifyClient(APIFY_API_TOKEN)
    todos = []

    for termino in terminos:
        print(f"  Buscando: '{termino}' en '{zona}' ...")
        try:
            run = client.actor("compass/crawler-google-places").call(
                run_input={
                    "searchStringsArray": [termino],
                    "locationQuery": zona,
                    "maxCrawledPlacesPerSearch": max_por_busqueda,
                    "language": "es",
                    "includeHistogram": False,
                    "includeOpeningHours": False,
                    "includePeopleAlsoSearch": False,
                }
            )
            dataset_id = run.default_dataset_id
            items = list(client.dataset(dataset_id).iterate_items())
            print(f"    -> {len(items)} resultados")
            todos.extend(items)
        except Exception as e:
            print(f"    WARN: fallo el termino '{termino}': {e}. Continuando con el siguiente.")

    return todos


# ──────────────────────────────────────────────
#  PASO 2 - LIMPIEZA
# ──────────────────────────────────────────────

def es_relevante(nombre: str, categoria_maps: str, categoria: str) -> bool:
    """Descarta resultados claramente irrelevantes segun categoria Maps y nombre."""
    nombre_lower     = nombre.lower()
    categoria_lower  = categoria_maps.lower()

    if categoria == "repuestos":
        keywords = KEYWORDS_NOMBRE_REPUESTOS
        cats_ok  = CATEGORIAS_MAPS_REPUESTOS
    elif categoria == "fundas":
        keywords = KEYWORDS_NOMBRE_FUNDAS
        cats_ok  = CATEGORIAS_MAPS_FUNDAS
    else:
        keywords = KEYWORDS_NOMBRE_TELEFONOS
        cats_ok  = CATEGORIAS_MAPS_TELEFONOS

    # Pasa si la categoria de Maps es relevante
    if any(c in categoria_lower for c in cats_ok):
        return True
    # Pasa si el nombre contiene keyword del rubro
    if any(k in nombre_lower for k in keywords):
        return True
    return False


def limpiar(raw: list[dict], zona: str, categoria: str) -> pd.DataFrame:
    """Normaliza campos, elimina duplicados y filtra ruido."""
    registros = []
    for item in raw:
        nombre = (item.get("title") or "").strip()
        if not nombre:
            continue

        telefono    = (item.get("phone") or "").strip().lstrip("+")
        cat_maps    = (item.get("categoryName") or "").strip()
        direccion   = (item.get("address") or "").strip()
        sitio_web   = (item.get("website") or "").strip()
        resenas     = int(item.get("reviewsCount") or 0)
        rating      = float(item.get("totalScore") or 0)
        maps_url    = (item.get("url") or "").strip()
        place_id    = (item.get("placeId") or "").strip()

        nombre_lower = nombre.lower()
        if any(marca in nombre_lower for marca in MARCAS_EXCLUIR):
            continue
        if not es_relevante(nombre, cat_maps, categoria):
            continue

        zona_keywords = [w.lower() for w in zona.replace(",", " ").split() if len(w) > 3]
        en_zona = any(kw in direccion.lower() for kw in zona_keywords)

        registros.append({
            "Zona":      zona,
            "Negocio":   nombre,
            "Telefono":  telefono,
            "Direccion": direccion,
            "Categoria": cat_maps,
            "Resenas":   resenas,
            "Rating":    rating,
            "Sitio_web": sitio_web,
            "Maps_URL":  maps_url,
            "Place_ID":  place_id,
            "_en_zona":  en_zona,
        })

    df = pd.DataFrame(registros)
    if df.empty:
        return df

    df["_key"] = df["Negocio"].str.lower().str.strip() + "|" + df["Telefono"].str.strip()
    df = df.drop_duplicates(subset="_key").drop(columns="_key")
    df = df[~((df["Place_ID"] != "") & df["Place_ID"].duplicated(keep="first"))]

    fuera = df[~df["_en_zona"]]["Negocio"].tolist()
    if fuera:
        print(f"  AVISO: {len(fuera)} resultados podrian estar fuera de zona (se conservan)")
        for n in fuera[:5]:
            print(f"    - {n}")

    df = df.drop(columns="_en_zona")
    return df.reset_index(drop=True)


# ──────────────────────────────────────────────
#  PASO 3 - CLASIFICACION
# ──────────────────────────────────────────────

def clasificar(df: pd.DataFrame) -> pd.DataFrame:
    def tipo(row):
        nombre_lower = row["Negocio"].lower()
        if any(cadena in nombre_lower for cadena in CADENAS_CONOCIDAS):
            return "Cadena"
        if row["Resenas"] >= 300:
            return "Independiente - alto volumen"
        return "Independiente - chico/mediano"

    def foco_apple(row):
        nombre_lower = row["Negocio"].lower()
        if any(w in nombre_lower for w in ("apple", "iphone", "mac")):
            return "Si"
        return "Multimarca"

    def revisar_mayorista(row):
        nombre_lower = row["Negocio"].lower()
        cat_lower    = row["Categoria"].lower()
        if "mayorista" in cat_lower:
            return "Si"
        if any(p in nombre_lower for p in PALABRAS_MAYORISTA):
            return "Si"
        return "No"

    df["Tipo"]              = df.apply(tipo, axis=1)
    df["Foco_Apple"]        = df.apply(foco_apple, axis=1)
    df["Revisar_mayorista"] = df.apply(revisar_mayorista, axis=1)
    return df


# ──────────────────────────────────────────────
#  PASO 4 - GOOGLE SHEETS
# ──────────────────────────────────────────────

def cargar_sheets():
    """Conecta a Google Sheets y devuelve worksheet + DataFrame con leads existentes."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

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
                print("  [AVISO] El token guardado expiro o fue revocado. Pidiendo login de nuevo...")
                os.remove(TOKEN_FILE)

        if necesita_login:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDENTIALS_FILE, scopes)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    gc = gspread.authorize(creds)
    sh = gc.open_by_url(SPREADSHEET_URL)

    try:
        ws = sh.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        columnas = [
            "Zona", "Negocio", "Telefono", "Direccion", "Categoria",
            "Tipo", "Foco_Apple", "Revisar_mayorista",
            "Resenas", "Rating", "Sitio_web", "Maps_URL", "Place_ID",
        ]
        ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=len(columnas))
        ws.append_row(columnas, value_input_option="USER_ENTERED")
        print(f"  [OK] Tab '{SHEET_TAB_NAME}' creada automaticamente.")

    datos = ws.get_all_records()
    df_existentes = pd.DataFrame(datos) if datos else pd.DataFrame()
    return ws, df_existentes


def filtrar_nuevos(df_nuevos: pd.DataFrame, df_existentes: pd.DataFrame) -> pd.DataFrame:
    if df_existentes.empty or "Negocio" not in df_existentes.columns:
        return df_nuevos

    nombres_existentes = set(df_existentes["Negocio"].str.lower().str.strip().tolist())

    place_ids_existentes = set()
    if "Place_ID" in df_existentes.columns:
        place_ids_existentes = set(
            df_existentes["Place_ID"].dropna().astype(str).tolist()
        ) - {""}

    telefonos_existentes = set()
    if "Telefono" in df_existentes.columns:
        telefonos_existentes = set(
            df_existentes["Telefono"].dropna().astype(str).str.strip().tolist()
        ) - {""}

    mask_nuevo = ~(
        df_nuevos["Negocio"].str.lower().str.strip().isin(nombres_existentes)
        | (df_nuevos["Place_ID"].isin(place_ids_existentes) & (df_nuevos["Place_ID"] != ""))
        | (df_nuevos["Telefono"].isin(telefonos_existentes) & (df_nuevos["Telefono"] != ""))
    )
    return df_nuevos[mask_nuevo].reset_index(drop=True)


def volcar_a_sheets(ws, df: pd.DataFrame, df_existentes: pd.DataFrame):
    if df.empty:
        print("  No hay leads nuevos para agregar.")
        return

    # Leer headers reales del sheet para escribir en el orden correcto
    # (el sheet puede tener columnas extra agregadas manualmente)
    headers_sheet = ws.row_values(1)
    cols_script = {
        "Zona", "Negocio", "Telefono", "Direccion", "Categoria",
        "Tipo", "Foco_Apple", "Revisar_mayorista",
        "Resenas", "Rating", "Sitio_web", "Maps_URL", "Place_ID",
    }
    # Mapea header del sheet → nombre de columna en el DataFrame.
    # Cubre tildes distintas (Reseñas→Resenas) y mayúsculas (DIRECCION→Direccion).
    cols_script_lower = {c.lower(): c for c in cols_script}
    header_alias = {"Reseñas": "Resenas", "Resenas": "Resenas"}

    filas = []
    for _, row in df.iterrows():
        fila = []
        for h in headers_sheet:
            h_clean = h.strip()
            # 1) alias explícito, 2) lookup case-insensitive contra cols_script
            df_col = header_alias.get(h_clean) or cols_script_lower.get(h_clean.lower(), h_clean)
            if df_col in cols_script and df_col in df.columns:
                fila.append(str(row[df_col]) if pd.notna(row[df_col]) else "")
            else:
                fila.append("")  # columna manual (Barrio, Estado, etc.) -> vacia
        filas.append(fila)

    # table_range="A1" fuerza deteccion desde A1 y evita que gspread expanda columnas
    ws.append_rows(filas, value_input_option="USER_ENTERED", table_range="A1")
    print(f"  [OK] {len(filas)} leads nuevos agregados a la planilla.")


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FixLab B2B Lead Prospector")
    parser.add_argument("--zona", default=ZONA_DEFAULT,
                        help='Zona geografica, ej: "Quilmes, Buenos Aires, Argentina"')
    parser.add_argument("--max", type=int, default=MAX_PLACES_PER_SEARCH,
                        help="Maximo de resultados por busqueda (default 150)")
    parser.add_argument("--terms", type=int, default=6,
                        help="Cantidad de terminos de busqueda a usar (1 al maximo)")
    parser.add_argument("--categoria", default="repuestos",
                        choices=list(CATEGORIAS.keys()),
                        help="Categoria de busqueda: repuestos, fundas, telefonos")
    parser.add_argument("--test", action="store_true",
                        help="Modo prueba: 1 busqueda x 10 resultados (~$0.02). Verifica todo el pipeline.")
    args = parser.parse_args()

    # Configurar globals segun categoria
    global SHEET_TAB_NAME, SEARCH_TERMS, CATEGORIA_ACTUAL
    cfg = CATEGORIAS[args.categoria]
    SHEET_TAB_NAME   = cfg["sheet_tab"]
    SEARCH_TERMS     = cfg["search_terms"]
    CATEGORIA_ACTUAL = args.categoria

    print(f"\n=== FixLab Lead Prospector — {args.categoria.upper()} ===")

    # Modo test sobreescribe todo
    if args.test:
        print("MODO PRUEBA - 1 busqueda x 10 resultados (~$0.02)")
        terminos_a_usar = [SEARCH_TERMS[0]]
        max_a_usar = 10
    else:
        n_terms = max(1, min(args.terms, len(SEARCH_TERMS)))
        terminos_a_usar = SEARCH_TERMS[:n_terms]
        max_a_usar = args.max

    print(f"Zona: {args.zona}")
    print(f"Busquedas: {len(terminos_a_usar)} terminos x {max_a_usar} resultados max")
    costo_estimado = len(terminos_a_usar) * max_a_usar * 0.002
    print(f"Costo estimado maximo: ~${costo_estimado:.2f} USD")
    print()

    # VALIDACION COMPLETA ANTES DE GASTAR CREDITO
    print("[0/4] Validando configuracion...")
    validar_configuracion()
    ws, df_existentes = validar_sheets()
    print("  [OK] Todo listo. Iniciando busqueda en Apify...\n")

    # APIFY
    print("[1/4] Buscando en Google Maps via Apify...")
    raw = buscar_en_apify(args.zona, max_a_usar, terminos_a_usar)
    print(f"  Total bruto: {len(raw)} registros\n")

    # LIMPIEZA
    print("[2/4] Limpiando y deduplicando...")
    df = limpiar(raw, args.zona, CATEGORIA_ACTUAL)
    print(f"  Despues de limpieza: {len(df)} registros\n")

    if df.empty:
        print("No se encontraron resultados. Fin.")
        return

    # CLASIFICACION
    print("[3/4] Clasificando...")
    df = clasificar(df)
    resumen = df["Tipo"].value_counts().to_dict()
    for k, v in resumen.items():
        print(f"  {k}: {v}")
    print()

    # SHEETS
    print("[4/4] Comparando con Google Sheets...")
    print(f"  Leads ya en planilla: {len(df_existentes)}")
    df_nuevos = filtrar_nuevos(df, df_existentes)
    dup_sheet = len(df) - len(df_nuevos)
    print(f"  Leads nuevos encontrados: {len(df_nuevos)}")
    print(f"  Duplicados vs planilla: {dup_sheet}")
    volcar_a_sheets(ws, df_nuevos, df_existentes)

    # Costo real calculado sobre resultados efectivamente obtenidos
    costo_real = len(raw) * 0.002
    print(f"  Costo real: ~${costo_real:.3f} USD ({len(raw)} resultados x $0.002)")
    # Metricas para la UI (unicos reales despues de dedup interna)
    print(f"  Total unicos: {len(df)} registros")

    # Emitir leads nuevos como JSON para que la interfaz los muestre
    if not df_nuevos.empty:
        cols = ["Negocio", "Telefono", "Direccion", "Tipo", "Foco_Apple", "Resenas", "Maps_URL"]
        leads_out = df_nuevos[[c for c in cols if c in df_nuevos.columns]].fillna("").to_dict(orient="records")
        print(f"LEADS_JSON:{json.dumps(leads_out, ensure_ascii=False)}")

    print("\n=== Listo ===\n")


if __name__ == "__main__":
    main()
