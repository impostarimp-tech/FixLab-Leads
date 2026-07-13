"""SQLite schema and data access for the commercial-routes feature.

The Google Sheet is never written to by this feature — all route/lote state
lives in this local database.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads_routes.db")

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
    last_synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_generado TEXT NOT NULL,
    origen_lat REAL NOT NULL,
    origen_lng REAL NOT NULL,
    origen_texto TEXT NOT NULL,
    tamano_solicitado INTEGER NOT NULL,
    tamano_real INTEGER NOT NULL
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
        conn.commit()
    finally:
        conn.close()


def upsert_lead(
    conn: sqlite3.Connection,
    place_id: str,
    categoria: str,
    negocio: str,
    direccion: str,
    maps_url: str,
) -> int:
    """Inserts a lead if place_id is new; returns its id either way.
    Never overwrites an existing row (the Sheet is the source of truth for
    business data, but a lead already in cache keeps its geocode state)."""
    row = conn.execute("SELECT id FROM leads_cache WHERE place_id = ?", (place_id,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        """INSERT INTO leads_cache
           (place_id, categoria, negocio, direccion, maps_url, geocode_source, last_synced_at)
           VALUES (?, ?, ?, ?, ?, 'pendiente', ?)""",
        (place_id, categoria, negocio, direccion, maps_url, datetime.utcnow().isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def set_geocode_result(
    conn: sqlite3.Connection, lead_id: int, lat: float | None, lng: float | None, source: str
) -> None:
    conn.execute(
        "UPDATE leads_cache SET lat = ?, lng = ?, geocode_source = ? WHERE id = ?",
        (lat, lng, source, lead_id),
    )
    conn.commit()


def get_pending_geocode(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM leads_cache WHERE geocode_source IN ('pendiente', 'fallido')"
    ).fetchall()


def get_failed_leads(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM leads_cache WHERE geocode_source = 'fallido'").fetchall()


def get_candidate_pool(conn: sqlite3.Connection, reappear_after_days: int = 30) -> list[sqlite3.Row]:
    """Leads that are geocoded and either never shared, or shared 30+ days ago."""
    cutoff = (datetime.utcnow() - timedelta(days=reappear_after_days)).isoformat()
    return conn.execute(
        """
        SELECT lc.* FROM leads_cache lc
        WHERE lc.geocode_source != 'fallido' AND lc.lat IS NOT NULL
        AND lc.id NOT IN (
            SELECT sl.lead_id
            FROM sublote_leads sl
            JOIN sublotes sb ON sb.id = sl.sublote_id
            WHERE sb.compartido_en IS NOT NULL AND sb.compartido_en > ?
        )
        """,
        (cutoff,),
    ).fetchall()


def create_lote(
    conn: sqlite3.Connection,
    origen_lat: float,
    origen_lng: float,
    origen_texto: str,
    tamano_solicitado: int,
    tamano_real: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO lotes
           (fecha_generado, origen_lat, origen_lng, origen_texto, tamano_solicitado, tamano_real)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (datetime.utcnow().isoformat(), origen_lat, origen_lng, origen_texto,
         tamano_solicitado, tamano_real),
    )
    conn.commit()
    return cur.lastrowid


def create_sublote(
    conn: sqlite3.Connection, lote_id: int, orden: int, maps_link: str, lead_ids_in_order: list[int]
) -> int:
    cur = conn.execute(
        "INSERT INTO sublotes (lote_id, orden, maps_link) VALUES (?, ?, ?)",
        (lote_id, orden, maps_link),
    )
    sublote_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO sublote_leads (sublote_id, lead_id, orden_en_ruta) VALUES (?, ?, ?)",
        [(sublote_id, lead_id, i) for i, lead_id in enumerate(lead_ids_in_order)],
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


def get_all_geocoded_leads(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All leads with usable coordinates, regardless of sharing status — used for
    the "every lead" base layer of the map view."""
    return conn.execute(
        "SELECT id, negocio, categoria, lat, lng FROM leads_cache"
        " WHERE geocode_source != 'fallido' AND lat IS NOT NULL"
    ).fetchall()


def get_lote_route_points(conn: sqlite3.Connection, lote_id: int) -> list[dict]:
    """Returns the full visiting order for a lote as a flat list of points:
    the origin first, then every lead across its sub-lotes in chained order."""
    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
    if lote is None:
        return []

    points = [{"lat": lote["origen_lat"], "lng": lote["origen_lng"], "negocio": "Origen"}]
    rows = conn.execute(
        """
        SELECT lc.negocio, lc.lat, lc.lng
        FROM sublote_leads sl
        JOIN sublotes sb ON sb.id = sl.sublote_id
        JOIN leads_cache lc ON lc.id = sl.lead_id
        WHERE sb.lote_id = ?
        ORDER BY sb.orden, sl.orden_en_ruta
        """,
        (lote_id,),
    ).fetchall()
    points.extend({"lat": row["lat"], "lng": row["lng"], "negocio": row["negocio"]} for row in rows)
    return points
