"""SQLite schema and data access for the commercial-routes feature.

The Google Sheet is never written to by this feature — all route/lote state
lives in this local database.
"""
from __future__ import annotations

import math
import os
import sqlite3
from datetime import datetime, timedelta

# DB_PATH env var lets a hosted deployment point this at a mounted persistent
# volume (e.g. Railway) instead of the local desktop-app file next to this script.
DB_PATH = os.getenv("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads_routes.db")

KM_PER_DEGREE_LAT = 111.32
DEFAULT_SEARCH_RADIUS_KM = 60.0  # generously covers all of AMBA from any point in it;
# becomes load-bearing once leads outside AMBA (other provinces) get added, so a
# route generated in one city doesn't have to distance-check candidates nationwide

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT UNIQUE NOT NULL,
    categoria TEXT NOT NULL,
    negocio TEXT NOT NULL,
    direccion TEXT,
    maps_url TEXT,
    lat REAL,
    lng REAL,
    geocode_source TEXT NOT NULL DEFAULT 'pendiente',
    last_synced_at TEXT NOT NULL,
    telefono TEXT,
    outreach_status TEXT NOT NULL DEFAULT 'sin_contactar',
    reviews_count INTEGER,
    rating REAL
);

CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_generado TEXT NOT NULL,
    origen_lat REAL NOT NULL,
    origen_lng REAL NOT NULL,
    origen_texto TEXT NOT NULL,
    tamano_solicitado INTEGER NOT NULL,
    tamano_real INTEGER NOT NULL,
    categoria TEXT
);

CREATE TABLE IF NOT EXISTS sublotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id INTEGER NOT NULL REFERENCES lotes(id),
    orden INTEGER NOT NULL,
    maps_link TEXT NOT NULL,
    compartido_en TEXT
);

CREATE TABLE IF NOT EXISTS sublote_leads (
    sublote_id INTEGER NOT NULL REFERENCES sublotes(id),
    lead_id INTEGER NOT NULL REFERENCES leads_cache(id),
    orden_en_ruta INTEGER NOT NULL,
    PRIMARY KEY (sublote_id, lead_id)
);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Adds columns introduced after the original schema, for databases created
    before they existed. No-op (and safe to call) once a column already exists."""
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(leads_cache)")}
    if "telefono" not in existing_cols:
        conn.execute("ALTER TABLE leads_cache ADD COLUMN telefono TEXT")
    if "outreach_status" not in existing_cols:
        conn.execute(
            "ALTER TABLE leads_cache ADD COLUMN outreach_status TEXT NOT NULL DEFAULT 'sin_contactar'"
        )
    if "reviews_count" not in existing_cols:
        conn.execute("ALTER TABLE leads_cache ADD COLUMN reviews_count INTEGER")
    if "rating" not in existing_cols:
        conn.execute("ALTER TABLE leads_cache ADD COLUMN rating REAL")

    lotes_cols = {row["name"] for row in conn.execute("PRAGMA table_info(lotes)")}
    if "categoria" not in lotes_cols:
        conn.execute("ALTER TABLE lotes ADD COLUMN categoria TEXT")


def upsert_lead(
    conn: sqlite3.Connection,
    place_id: str,
    categoria: str,
    negocio: str,
    direccion: str,
    maps_url: str,
    telefono: str = "",
    reviews_count: int | None = None,
    rating: float | None = None,
) -> int:
    """Inserts a lead if place_id is new; returns its id either way.
    Never overwrites an existing row (the Sheet is the source of truth for
    business data, but a lead already in cache keeps its geocode state)."""
    row = conn.execute("SELECT id FROM leads_cache WHERE place_id = ?", (place_id,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        """INSERT INTO leads_cache
           (place_id, categoria, negocio, direccion, maps_url, telefono, reviews_count, rating,
            geocode_source, last_synced_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)""",
        (place_id, categoria, negocio, direccion, maps_url, telefono, reviews_count, rating,
         datetime.utcnow().isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def set_telefono(conn: sqlite3.Connection, lead_id: int, telefono: str) -> None:
    conn.execute("UPDATE leads_cache SET telefono = ? WHERE id = ?", (telefono, lead_id))
    conn.commit()


def set_reviews_rating(
    conn: sqlite3.Connection, lead_id: int, reviews_count: int | None, rating: float | None
) -> None:
    """Refreshes review stats — unlike telefono, these change over time, so every
    sync overwrites them rather than only backfilling when empty."""
    conn.execute(
        "UPDATE leads_cache SET reviews_count = ?, rating = ? WHERE id = ?",
        (reviews_count, rating, lead_id),
    )
    conn.commit()


def set_geocode_result(
    conn: sqlite3.Connection, lead_id: int, lat: float | None, lng: float | None, source: str
) -> None:
    conn.execute(
        "UPDATE leads_cache SET lat = ?, lng = ?, geocode_source = ? WHERE id = ?",
        (lat, lng, source, lead_id),
    )
    conn.commit()


def get_pending_geocode(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Pendiente leads (never attempted) sort before fallido (previously failed) --
    hosted deployments with a request-time limit can get cut off mid-batch, and
    fresh leads should never be starved behind endlessly-retried failures."""
    return conn.execute(
        "SELECT * FROM leads_cache WHERE geocode_source IN ('pendiente', 'fallido') "
        "ORDER BY CASE geocode_source WHEN 'pendiente' THEN 0 ELSE 1 END"
    ).fetchall()


def get_failed_leads(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM leads_cache WHERE geocode_source = 'fallido'").fetchall()


def find_lead_by_name(conn: sqlite3.Connection, negocio: str) -> sqlite3.Row | None:
    """Finds a geocoded lead by exact (case-insensitive) business name — used to
    let an origin be typed as it appears on the map instead of a street address."""
    return conn.execute(
        "SELECT * FROM leads_cache WHERE lat IS NOT NULL AND LOWER(negocio) = LOWER(?) LIMIT 1",
        (negocio,),
    ).fetchone()


def _merge_lead_rows(rows: list[sqlite3.Row], key_fn) -> list[dict]:
    """Groups lead rows by key_fn(row) and merges each group into a single stop:
    all their categorias and underlying lead_ids are combined, while the other
    scalar fields (direccion, telefono, lat/lng, etc.) come from whichever row
    in the group has the most reviews (the most reliable listing)."""
    groups: dict = {}
    order: list = []
    for row in rows:
        key = key_fn(row)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    merged = []
    for key in order:
        group = groups[key]
        representative = max(group, key=lambda r: (r["reviews_count"] or -1))
        merged.append({
            "id": representative["id"],
            "lead_ids": [r["id"] for r in group],
            "negocio": representative["negocio"],
            "categorias": sorted({r["categoria"] for r in group}),
            "direccion": representative["direccion"],
            "telefono": representative["telefono"],
            "reviews_count": representative["reviews_count"],
            "rating": representative["rating"],
            "outreach_status": representative["outreach_status"],
            "lat": representative["lat"],
            "lng": representative["lng"],
        })
    return merged


def get_candidate_pool(
    conn: sqlite3.Connection,
    reappear_after_days: int = 30,
    categoria: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    origin: tuple[float, float] | None = None,
    max_radius_km: float | None = DEFAULT_SEARCH_RADIUS_KM,
) -> list[dict]:
    """Leads that are geocoded and either never shared, or shared 30+ days ago,
    optionally restricted to a single categoria and/or a minimum review count/rating.
    The same physical business listed under multiple category tabs is merged into
    a single stop (see _merge_lead_rows) so a route visits it once, not once per
    category it's listed in.

    When origin is given, a cheap bounding-box pre-filter (plain lat/lng range
    checks, no haversine) restricts candidates to within roughly max_radius_km
    of it before the exact distance-based selection/ordering algorithm runs.
    This has no effect today (everything is within AMBA, well under the
    default radius) but keeps route generation fast once leads from other
    provinces are added — a route requested in one city won't have to
    distance-check candidates on the other side of the country."""
    cutoff = (datetime.utcnow() - timedelta(days=reappear_after_days)).isoformat()
    query = """
        SELECT lc.* FROM leads_cache lc
        WHERE lc.geocode_source != 'fallido' AND lc.lat IS NOT NULL
        AND lc.id NOT IN (
            SELECT sl.lead_id
            FROM sublote_leads sl
            JOIN sublotes sb ON sb.id = sl.sublote_id
            WHERE sb.compartido_en IS NOT NULL AND sb.compartido_en > ?
        )
        """
    params: list = [cutoff]
    if categoria:
        query += " AND lc.categoria = ?"
        params.append(categoria)
    if min_reviews is not None:
        query += " AND lc.reviews_count >= ?"
        params.append(min_reviews)
    if min_rating is not None:
        query += " AND lc.rating >= ?"
        params.append(min_rating)
    if origin is not None and max_radius_km is not None:
        origin_lat, origin_lng = origin
        lat_delta = max_radius_km / KM_PER_DEGREE_LAT
        km_per_degree_lng = KM_PER_DEGREE_LAT * math.cos(math.radians(origin_lat))
        lng_delta = max_radius_km / km_per_degree_lng if km_per_degree_lng > 0 else 180.0
        query += " AND lc.lat BETWEEN ? AND ? AND lc.lng BETWEEN ? AND ?"
        params.extend([
            origin_lat - lat_delta, origin_lat + lat_delta,
            origin_lng - lng_delta, origin_lng + lng_delta,
        ])
    rows = conn.execute(query, params).fetchall()
    return _merge_lead_rows(rows, key_fn=lambda r: r["negocio"].strip().lower())


def create_lote(
    conn: sqlite3.Connection,
    origen_lat: float,
    origen_lng: float,
    origen_texto: str,
    tamano_solicitado: int,
    tamano_real: int,
    categoria: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO lotes
           (fecha_generado, origen_lat, origen_lng, origen_texto, tamano_solicitado, tamano_real, categoria)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (datetime.utcnow().isoformat(), origen_lat, origen_lng, origen_texto,
         tamano_solicitado, tamano_real, categoria),
    )
    conn.commit()
    return cur.lastrowid


def get_lote(conn: sqlite3.Connection, lote_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()


def get_sublote_stops(conn: sqlite3.Connection, sublote_id: int) -> list[dict]:
    """Ordered stops belonging to one sublote — used to re-display a past lote's
    detail. Leads that were merged into a single stop at generation time (same
    business, multiple category tabs) share an orden_en_ruta and are re-grouped
    here back into one entry with all their categorias."""
    rows = conn.execute(
        """
        SELECT lc.*, sl.orden_en_ruta FROM sublote_leads sl
        JOIN leads_cache lc ON lc.id = sl.lead_id
        WHERE sl.sublote_id = ?
        ORDER BY sl.orden_en_ruta, lc.id
        """,
        (sublote_id,),
    ).fetchall()
    return _merge_lead_rows(rows, key_fn=lambda r: r["orden_en_ruta"])


def create_sublote(
    conn: sqlite3.Connection, lote_id: int, orden: int, maps_link: str, lead_id_groups: list[list[int]]
) -> int:
    """lead_id_groups: one inner list per physical stop — usually a single lead_id,
    but multiple when the same business was merged from several category tabs."""
    cur = conn.execute(
        "INSERT INTO sublotes (lote_id, orden, maps_link) VALUES (?, ?, ?)",
        (lote_id, orden, maps_link),
    )
    sublote_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO sublote_leads (sublote_id, lead_id, orden_en_ruta) VALUES (?, ?, ?)",
        [
            (sublote_id, lead_id, i)
            for i, group in enumerate(lead_id_groups)
            for lead_id in group
        ],
    )
    conn.commit()
    return sublote_id


def mark_sublote_compartido(conn: sqlite3.Connection, sublote_id: int) -> None:
    conn.execute(
        "UPDATE sublotes SET compartido_en = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), sublote_id),
    )
    conn.commit()


def mark_lote_compartido(conn: sqlite3.Connection, lote_id: int) -> None:
    conn.execute(
        "UPDATE sublotes SET compartido_en = ? WHERE lote_id = ? AND compartido_en IS NULL",
        (datetime.utcnow().isoformat(), lote_id),
    )
    conn.commit()


def get_lote_history(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM lotes ORDER BY fecha_generado DESC").fetchall()


def get_sublotes_for_lote(conn: sqlite3.Connection, lote_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sublotes WHERE lote_id = ? ORDER BY orden", (lote_id,)
    ).fetchall()


def get_recent_origenes(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    """Distinct origins used in past lotes, most recently used first — already
    geocoded, so picking one skips geocoding entirely (zero risk of failure)."""
    return conn.execute(
        """
        SELECT origen_texto, origen_lat, origen_lng, MAX(fecha_generado) AS ultima_fecha
        FROM lotes
        GROUP BY origen_texto, origen_lat, origen_lng
        ORDER BY ultima_fecha DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


OUTREACH_STATUSES = ["sin_contactar", "contactado", "respondio", "convertido"]


CRM_PAGE_SIZE = 100


def _crm_filters_clause(
    categoria: str | None,
    outreach_status: str | None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    clause = ""
    params: list = []
    if categoria:
        clause += " AND categoria = ?"
        params.append(categoria)
    if outreach_status:
        clause += " AND outreach_status = ?"
        params.append(outreach_status)
    if min_reviews is not None:
        clause += " AND reviews_count >= ?"
        params.append(min_reviews)
    if min_rating is not None:
        clause += " AND rating >= ?"
        params.append(min_rating)
    if q:
        clause += " AND (negocio LIKE ? OR direccion LIKE ? OR telefono LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    return clause, params


def get_crm_leads(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    outreach_status: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = CRM_PAGE_SIZE,
) -> list[sqlite3.Row]:
    """One page of leads across the 3 categories for the consolidated CRM view,
    optionally filtered by categoria, outreach_status, min_reviews, min_rating and/or q."""
    clause, params = _crm_filters_clause(categoria, outreach_status, min_reviews, min_rating, q)
    query = "SELECT * FROM leads_cache WHERE 1=1" + clause + " ORDER BY negocio LIMIT ? OFFSET ?"
    offset = (page - 1) * page_size
    return conn.execute(query, [*params, page_size, offset]).fetchall()


def count_crm_leads(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    outreach_status: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
) -> int:
    clause, params = _crm_filters_clause(categoria, outreach_status, min_reviews, min_rating, q)
    query = "SELECT COUNT(*) AS c FROM leads_cache WHERE 1=1" + clause
    return conn.execute(query, params).fetchone()["c"]


def get_crm_leads_all(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    outreach_status: str | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    q: str | None = None,
) -> list[sqlite3.Row]:
    """Every matching lead, unpaginated — used for CSV export."""
    clause, params = _crm_filters_clause(categoria, outreach_status, min_reviews, min_rating, q)
    query = "SELECT * FROM leads_cache WHERE 1=1" + clause + " ORDER BY negocio"
    return conn.execute(query, params).fetchall()


def set_outreach_status(conn: sqlite3.Connection, lead_id: int, status: str) -> None:
    conn.execute("UPDATE leads_cache SET outreach_status = ? WHERE id = ?", (status, lead_id))
    conn.commit()


def get_all_geocoded_leads(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All leads with usable coordinates, regardless of sharing status — used for
    the "every lead" base layer of the map view."""
    return conn.execute(
        "SELECT id, negocio, categoria, direccion, telefono, outreach_status, reviews_count, rating, lat, lng"
        " FROM leads_cache WHERE geocode_source != 'fallido' AND lat IS NOT NULL"
    ).fetchall()


def get_lote_route_points(conn: sqlite3.Connection, lote_id: int) -> list[dict]:
    """Returns the full visiting order for a lote as a flat list of points:
    the origin first, then every stop across its sub-lotes in chained order.
    Leads merged into one stop at generation time (same business, multiple
    category tabs) are re-grouped here too, so the map shows one marker per
    physical stop instead of overlapping duplicates."""
    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
    if lote is None:
        return []

    points = [{"id": None, "lat": lote["origen_lat"], "lng": lote["origen_lng"], "negocio": "Origen"}]
    rows = conn.execute(
        """
        SELECT lc.*, sb.orden AS sublote_orden, sl.orden_en_ruta
        FROM sublote_leads sl
        JOIN sublotes sb ON sb.id = sl.sublote_id
        JOIN leads_cache lc ON lc.id = sl.lead_id
        WHERE sb.lote_id = ?
        ORDER BY sb.orden, sl.orden_en_ruta, lc.id
        """,
        (lote_id,),
    ).fetchall()
    points.extend(_merge_lead_rows(rows, key_fn=lambda r: (r["sublote_orden"], r["orden_en_ruta"])))
    return points
