# Generador de Rutas Comerciales Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a route-generation blueprint to the existing `fixlab-leads` Flask app that reads leads from the 3 Google Sheet tabs, geocodes them, and produces geographically-ordered batches of Google Maps links ready to send to the vendor via WhatsApp.

**Architecture:** New flat Python modules alongside the existing `app.py`/`prospector.py` (no package structure, matching the existing project). State (geocoding cache, lote/sub-lote history) lives in a new SQLite database (`leads_routes.db`); the Google Sheet is read-only from this feature and is never written to. A Flask Blueprint (`routes_app.py`) is registered onto the existing `app` instance in `app.py`.

**Tech Stack:** Python 3.12, Flask (existing), gspread + google-auth-oauthlib (existing, reused auth pattern), `requests` (Nominatim HTTP calls), `sqlite3` (standard library), `pytest` for tests.

**Spec:** `docs/superpowers/specs/2026-07-13-rutas-comerciales-design.md`

---

### Task 1: Test setup + SQLite schema & data access layer

**Goal:** Establish pytest configuration and a fully-tested `routes_db.py` module providing the schema and all CRUD operations the rest of the feature needs.

**Files:**
- Create: `pytest.ini`
- Create: `routes_db.py`
- Test: `tests/test_routes_db.py`

**Acceptance Criteria:**
- [ ] `init_db()` creates all 4 tables (`leads_cache`, `lotes`, `sublotes`, `sublote_leads`)
- [ ] `upsert_lead` inserts new leads and is idempotent by `place_id` (never overwrites an existing row)
- [ ] `set_geocode_result` updates lat/lng/source
- [ ] `get_pending_geocode` returns rows with `geocode_source` in `('pendiente', 'fallido')`
- [ ] `get_candidate_pool` excludes leads shared within the last 30 days and includes everything else
- [ ] `create_lote`/`create_sublote` persist the lote → sub-lote → lead relationships correctly
- [ ] `mark_lote_compartido` marks every sub-lote of that lote as shared

**Verify:** `pytest tests/test_routes_db.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Create pytest config so flat top-level modules are importable from `tests/`**

```ini
[pytest]
pythonpath = .
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_routes_db.py
from datetime import datetime, timedelta

import pytest

import routes_db as db


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "test_leads_routes.db")
    db.init_db(db_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_init_db_creates_all_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"leads_cache", "lotes", "sublotes", "sublote_leads"} <= tables


def test_upsert_lead_inserts_new_lead(conn):
    lead_id = db.upsert_lead(
        conn, "P1", "Repuestos", "Taller X", "Av. Rivadavia 100",
        "https://maps.google.com/@-34.6,-58.4,17z",
    )
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["negocio"] == "Taller X"
    assert row["geocode_source"] == "pendiente"


def test_upsert_lead_is_idempotent_by_place_id(conn):
    first_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    second_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X renamed", "Dir 1", "")
    assert first_id == second_id
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (first_id,)).fetchone()
    assert row["negocio"] == "Taller X"  # not overwritten


def test_set_geocode_result_updates_lat_lng_and_source(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    db.set_geocode_result(conn, lead_id, -34.6, -58.4, "direccion")
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["lat"] == -34.6
    assert row["lng"] == -58.4
    assert row["geocode_source"] == "direccion"


def test_get_pending_geocode_returns_pendiente_and_fallido(conn):
    ok_id = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, ok_id, -34.6, -58.4, "direccion")
    pending_id = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    failed_id = db.upsert_lead(conn, "P3", "Repuestos", "C", "Dir C", "")
    db.set_geocode_result(conn, failed_id, None, None, "fallido")

    pending_ids = {row["id"] for row in db.get_pending_geocode(conn)}
    assert pending_ids == {pending_id, failed_id}


def test_get_candidate_pool_excludes_recently_shared(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_geocode_result(conn, lead_b, -34.61, -58.41, "direccion")

    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 2, 2)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [lead_a])
    db.mark_sublote_compartido(conn, sublote_id)

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn)}
    assert lead_a not in pool_ids
    assert lead_b in pool_ids


def test_get_candidate_pool_includes_leads_shared_over_30_days_ago(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")

    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 1, 1)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [lead_a])
    old_date = (datetime.utcnow() - timedelta(days=45)).isoformat()
    conn.execute("UPDATE sublotes SET compartido_en = ? WHERE id = ?", (old_date, sublote_id))
    conn.commit()

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn)}
    assert lead_a in pool_ids


def test_create_lote_and_sublote_persist_relationships(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")

    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 1, 1)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [lead_a])

    sublotes = db.get_sublotes_for_lote(conn, lote_id)
    assert len(sublotes) == 1
    assert sublotes[0]["id"] == sublote_id

    leads_in_sublote = conn.execute(
        "SELECT lead_id FROM sublote_leads WHERE sublote_id = ? ORDER BY orden_en_ruta",
        (sublote_id,),
    ).fetchall()
    assert [row["lead_id"] for row in leads_in_sublote] == [lead_a]


def test_mark_lote_compartido_marks_all_its_sublotes(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")
    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 1, 1)
    db.create_sublote(conn, lote_id, 1, "https://maps.example", [lead_a])

    db.mark_lote_compartido(conn, lote_id)

    sublote = db.get_sublotes_for_lote(conn, lote_id)[0]
    assert sublote["compartido_en"] is not None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_routes_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'routes_db'`

- [ ] **Step 4: Write the implementation**

```python
# routes_db.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_routes_db.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add pytest.ini routes_db.py tests/test_routes_db.py
git commit -m "feat: add SQLite schema and data access layer for routes feature"
```

---

### Task 2: Maps_URL coordinate parsing

**Goal:** Extract lat/lng directly from a Google Maps URL when present, avoiding a geocoding call entirely for the common case.

**Files:**
- Create: `routes_geocoding.py`
- Test: `tests/test_routes_geocoding_parse.py`

**Acceptance Criteria:**
- [ ] Parses `@lat,lng` from a standard Google Maps URL
- [ ] Returns `None` when the URL has no coordinate segment
- [ ] Returns `None` for empty/missing input
- [ ] Handles positive and negative coordinates

**Verify:** `pytest tests/test_routes_geocoding_parse.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_geocoding_parse.py
import routes_geocoding as geo


def test_parses_coords_from_standard_maps_url():
    url = "https://www.google.com/maps/place/Taller+X/@-34.608300,-58.371200,17z/data=!4m5"
    assert geo.parse_coords_from_maps_url(url) == (-34.6083, -58.3712)


def test_returns_none_when_no_coords_in_url():
    url = "https://www.google.com/maps/place/Taller+X/data=!4m5!3m4"
    assert geo.parse_coords_from_maps_url(url) is None


def test_returns_none_for_empty_or_missing_url():
    assert geo.parse_coords_from_maps_url("") is None
    assert geo.parse_coords_from_maps_url(None) is None


def test_parses_coords_with_positive_latitude_and_longitude():
    url = "https://www.google.com/maps/@40.7128,74.0060,15z"
    assert geo.parse_coords_from_maps_url(url) == (40.7128, 74.0060)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_geocoding_parse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'routes_geocoding'`

- [ ] **Step 3: Write the implementation**

```python
# routes_geocoding.py
"""Geocoding fallback chain for leads: Maps_URL coordinate extraction, then
Nominatim by address, then Nominatim by business name."""
from __future__ import annotations

import re

_MAPS_URL_COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")


def parse_coords_from_maps_url(maps_url: str | None) -> tuple[float, float] | None:
    """Extracts (lat, lng) from a Google Maps URL if it contains an @lat,lng segment."""
    if not maps_url:
        return None
    match = _MAPS_URL_COORD_RE.search(maps_url)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_geocoding_parse.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_geocoding.py tests/test_routes_geocoding_parse.py
git commit -m "feat: parse coordinates from Google Maps URLs"
```

---

### Task 3: Nominatim geocoding + fallback chain

**Goal:** Add rate-limited Nominatim geocoding with retries, and the full per-lead fallback chain (URL → address → business name → failed), plus a free-text geocoder for manually-typed origins.

**Files:**
- Modify: `routes_geocoding.py` (append to the file from Task 2)
- Modify: `requirements.txt`
- Test: `tests/test_routes_geocoding_chain.py`

**Acceptance Criteria:**
- [ ] `nominatim_geocode` calls the public API respecting a 1 req/sec rate limit, retries transient failures, and returns `None` after retries are exhausted
- [ ] `geocode_lead` tries Maps_URL first, then `Direccion`, then `Negocio`, returning `(coords, source)` or `(None, "fallido")`
- [ ] `geocode_free_text` geocodes an arbitrary manually-typed query (used for the route origin)
- [ ] No test makes a real network call

**Verify:** `pytest tests/test_routes_geocoding_chain.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Add `requests` to requirements**

```
# requirements.txt (append)
requests>=2.31.0
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_routes_geocoding_chain.py
from unittest.mock import MagicMock, patch

import routes_geocoding as geo


def _fake_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get")
def test_nominatim_geocode_returns_coords_on_success(mock_get, _mock_sleep):
    mock_get.return_value = _fake_response([{"lat": "-34.6083", "lon": "-58.3712"}])
    result = geo.nominatim_geocode("Av. Rivadavia 100, Buenos Aires, Argentina")
    assert result == (-34.6083, -58.3712)


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get")
def test_nominatim_geocode_returns_none_on_empty_results(mock_get, _mock_sleep):
    mock_get.return_value = _fake_response([])
    assert geo.nominatim_geocode("direccion inexistente") is None


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get", side_effect=Exception("network down"))
def test_nominatim_geocode_returns_none_after_retries_exhausted(mock_get, _mock_sleep):
    assert geo.nominatim_geocode("cualquier direccion", max_retries=2) is None
    assert mock_get.call_count == 3  # initial attempt + 2 retries


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_prefers_maps_url_over_nominatim(mock_nominatim):
    coords, source = geo.geocode_lead(
        negocio="Taller X", direccion="Dir X",
        maps_url="https://maps.google.com/@-34.6,-58.4,15z",
    )
    assert coords == (-34.6, -58.4)
    assert source == "maps_url"
    mock_nominatim.assert_not_called()


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_falls_back_to_direccion(mock_nominatim):
    mock_nominatim.return_value = (-34.7, -58.5)
    coords, source = geo.geocode_lead(negocio="Taller X", direccion="Dir X", maps_url=None)
    assert coords == (-34.7, -58.5)
    assert source == "direccion"
    mock_nominatim.assert_called_once_with("Dir X, Buenos Aires, Argentina")


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_falls_back_to_negocio_when_direccion_fails(mock_nominatim):
    mock_nominatim.side_effect = [None, (-34.8, -58.6)]
    coords, source = geo.geocode_lead(negocio="Taller X", direccion="Dir X", maps_url=None)
    assert coords == (-34.8, -58.6)
    assert source == "negocio"


@patch("routes_geocoding.nominatim_geocode", return_value=None)
def test_geocode_lead_returns_fallido_when_all_fail(mock_nominatim):
    coords, source = geo.geocode_lead(negocio="Taller X", direccion="Dir X", maps_url=None)
    assert coords is None
    assert source == "fallido"


def test_geocode_lead_skips_direccion_when_blank():
    with patch("routes_geocoding.nominatim_geocode", return_value=(-34.9, -58.7)) as mock_nominatim:
        coords, source = geo.geocode_lead(negocio="Taller X", direccion="", maps_url=None)
        mock_nominatim.assert_called_once_with("Taller X, Buenos Aires, Argentina")
        assert source == "negocio"


def test_geocode_free_text_appends_city_and_country():
    with patch("routes_geocoding.nominatim_geocode", return_value=(-34.6, -58.4)) as mock_nominatim:
        result = geo.geocode_free_text("Av. Corrientes 1000")
        mock_nominatim.assert_called_once_with("Av. Corrientes 1000, Buenos Aires, Argentina")
        assert result == (-34.6, -58.4)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_routes_geocoding_chain.py -v`
Expected: FAIL — `nominatim_geocode`/`geocode_lead`/`geocode_free_text` not defined

- [ ] **Step 4: Append the implementation to `routes_geocoding.py`**

```python
# routes_geocoding.py (append below parse_coords_from_maps_url)
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "fixlab-leads-routes/1.0 (uso interno)"
MIN_SECONDS_BETWEEN_REQUESTS = 1.0

_last_request_time: float = 0.0


def _respect_rate_limit() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
        time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
    _last_request_time = time.monotonic()


def nominatim_geocode(query: str, max_retries: int = 2) -> tuple[float, float] | None:
    """Geocodes free text via the public Nominatim API. Returns None on failure
    (empty results, HTTP error, or malformed response) after exhausting retries."""
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": NOMINATIM_USER_AGENT}

    for attempt in range(max_retries + 1):
        _respect_rate_limit()
        try:
            response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            results = response.json()
            if not results:
                return None
            return float(results[0]["lat"]), float(results[0]["lon"])
        except (requests.RequestException, ValueError, KeyError, IndexError):
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def geocode_lead(
    negocio: str, direccion: str | None, maps_url: str | None
) -> tuple[tuple[float, float] | None, str]:
    """Runs the fallback chain for one lead: Maps_URL -> Direccion -> Negocio.
    Returns ((lat, lng), source) or (None, 'fallido')."""
    coords = parse_coords_from_maps_url(maps_url)
    if coords:
        return coords, "maps_url"

    if direccion:
        coords = nominatim_geocode(f"{direccion}, Buenos Aires, Argentina")
        if coords:
            return coords, "direccion"

    coords = nominatim_geocode(f"{negocio}, Buenos Aires, Argentina")
    if coords:
        return coords, "negocio"

    return None, "fallido"


def geocode_free_text(query: str) -> tuple[float, float] | None:
    """Geocodes an arbitrary manually-typed query (e.g. a route origin address)."""
    return nominatim_geocode(f"{query}, Buenos Aires, Argentina")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_routes_geocoding_chain.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add routes_geocoding.py requirements.txt tests/test_routes_geocoding_chain.py
git commit -m "feat: add Nominatim geocoding with rate limiting and lead fallback chain"
```

---

### Task 4: Route ordering algorithm

**Goal:** Pure geographic functions to pick the N nearest candidates to an origin, order them into a continuous route, and chunk that route into sub-groups of at most 9.

**Files:**
- Create: `routes_algorithm.py`
- Test: `tests/test_routes_algorithm_ordering.py`

**Acceptance Criteria:**
- [ ] `haversine_meters` returns 0 for identical points and a realistic distance for two known CABA points
- [ ] `select_n_nearest` returns the closest N candidates sorted by distance, capped at however many are available
- [ ] `order_nearest_neighbor` always visits the closest remaining unvisited point
- [ ] `chunk_into_sublotes` splits an ordered sequence into chunks of at most 9, preserving order

**Verify:** `pytest tests/test_routes_algorithm_ordering.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_algorithm_ordering.py
import routes_algorithm as algo


def test_haversine_zero_for_same_point():
    assert algo.haversine_meters(-34.6, -58.4, -34.6, -58.4) == 0


def test_haversine_known_distance_buenos_aires_points():
    # Obelisco (-34.6037,-58.3816) to Congreso (-34.6095,-58.3925), roughly 1.1km apart
    d = algo.haversine_meters(-34.6037, -58.3816, -34.6095, -58.3925)
    assert 900 < d < 1300


def test_select_n_nearest_returns_closest_sorted_by_distance():
    origin = (-34.60, -58.38)
    candidates = [
        {"id": 1, "lat": -34.61, "lng": -58.39},    # farther
        {"id": 2, "lat": -34.601, "lng": -58.381},  # closest
        {"id": 3, "lat": -34.605, "lng": -58.385},  # middle
    ]
    result = algo.select_n_nearest(origin, candidates, n=2)
    assert [c["id"] for c in result] == [2, 3]


def test_select_n_nearest_caps_at_available_candidates():
    origin = (-34.60, -58.38)
    candidates = [{"id": 1, "lat": -34.601, "lng": -58.381}]
    result = algo.select_n_nearest(origin, candidates, n=5)
    assert len(result) == 1


def test_order_nearest_neighbor_visits_closest_unvisited_each_step():
    origin = (0.0, 0.0)
    points = [
        {"id": "far", "lat": 0.03, "lng": 0.0},
        {"id": "near", "lat": 0.01, "lng": 0.0},
        {"id": "mid", "lat": 0.02, "lng": 0.0},
    ]
    ordered = algo.order_nearest_neighbor(origin, points)
    assert [p["id"] for p in ordered] == ["near", "mid", "far"]


def test_chunk_into_sublotes_splits_preserving_order():
    points = [{"id": i} for i in range(20)]
    chunks = algo.chunk_into_sublotes(points, max_size=9)
    assert [len(c) for c in chunks] == [9, 9, 2]
    assert [p["id"] for p in chunks[0]] == list(range(9))
    assert [p["id"] for p in chunks[2]] == [18, 19]


def test_chunk_into_sublotes_handles_exact_multiple():
    points = [{"id": i} for i in range(18)]
    chunks = algo.chunk_into_sublotes(points, max_size=9)
    assert len(chunks) == 2
    assert all(len(c) == 9 for c in chunks)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_algorithm_ordering.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'routes_algorithm'`

- [ ] **Step 3: Write the implementation**

```python
# routes_algorithm.py
"""Pure geographic algorithms: nearest-neighbor route ordering and sub-lote
chunking. No external services, no I/O."""
from __future__ import annotations

import math

EARTH_RADIUS_METERS = 6371000
MAX_STOPS_PER_SUBLOTE = 9


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def select_n_nearest(origin: tuple[float, float], candidates: list[dict], n: int) -> list[dict]:
    """Returns up to n candidates closest to origin, sorted by distance ascending.
    Each candidate dict must have 'lat' and 'lng' keys."""
    origin_lat, origin_lng = origin
    scored = sorted(
        candidates,
        key=lambda c: haversine_meters(origin_lat, origin_lng, c["lat"], c["lng"]),
    )
    return scored[:n]


def order_nearest_neighbor(origin: tuple[float, float], points: list[dict]) -> list[dict]:
    """Orders points into a route starting at origin: repeatedly visits the closest
    unvisited point. Does not include the origin itself in the result."""
    remaining = list(points)
    ordered: list[dict] = []
    current_lat, current_lng = origin

    while remaining:
        nearest = min(
            remaining,
            key=lambda p: haversine_meters(current_lat, current_lng, p["lat"], p["lng"]),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current_lat, current_lng = nearest["lat"], nearest["lng"]

    return ordered


def chunk_into_sublotes(ordered_points: list[dict], max_size: int = MAX_STOPS_PER_SUBLOTE) -> list[list[dict]]:
    """Splits an already-ordered sequence into consecutive chunks of up to max_size,
    preserving order so each chunk continues geographically from the previous one."""
    return [ordered_points[i : i + max_size] for i in range(0, len(ordered_points), max_size)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_algorithm_ordering.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_algorithm.py tests/test_routes_algorithm_ordering.py
git commit -m "feat: add nearest-neighbor route ordering and sub-lote chunking"
```

---

### Task 5: Google Maps link builder

**Goal:** Generate a valid Google Maps directions URL (origin + up to 8 waypoints + destination) for a sub-lote.

**Files:**
- Modify: `routes_algorithm.py` (append to the file from Task 4)
- Test: `tests/test_routes_algorithm_maps_link.py`

**Acceptance Criteria:**
- [ ] Single-stop sub-lote produces a link with no `waypoints` param
- [ ] Multi-stop sub-lote includes all intermediate stops as `waypoints`, last stop as `destination`
- [ ] Raises `ValueError` for empty stops or more than 9 stops

**Verify:** `pytest tests/test_routes_algorithm_maps_link.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_algorithm_maps_link.py
import pytest

import routes_algorithm as algo


def test_build_maps_link_single_stop_has_no_waypoints():
    origin = (-34.60, -58.38)
    stops = [{"lat": -34.61, "lng": -58.39}]
    link = algo.build_maps_link(origin, stops)
    assert link.startswith("https://www.google.com/maps/dir/?")
    assert "origin=-34.6%2C-58.38" in link
    assert "destination=-34.61%2C-58.39" in link
    assert "waypoints=" not in link


def test_build_maps_link_includes_waypoints_for_multiple_stops():
    origin = (-34.60, -58.38)
    stops = [
        {"lat": -34.601, "lng": -58.381},
        {"lat": -34.602, "lng": -58.382},
        {"lat": -34.603, "lng": -58.383},
    ]
    link = algo.build_maps_link(origin, stops)
    assert "destination=-34.603%2C-58.383" in link
    assert "waypoints=-34.601%2C-58.381%7C-34.602%2C-58.382" in link


def test_build_maps_link_rejects_empty_stops():
    with pytest.raises(ValueError):
        algo.build_maps_link((-34.6, -58.4), [])


def test_build_maps_link_rejects_more_than_nine_stops():
    stops = [{"lat": -34.6, "lng": -58.4} for _ in range(10)]
    with pytest.raises(ValueError):
        algo.build_maps_link((-34.6, -58.4), stops)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_algorithm_maps_link.py -v`
Expected: FAIL — `build_maps_link` not defined

- [ ] **Step 3: Append the implementation to `routes_algorithm.py`**

```python
# routes_algorithm.py (append)
from urllib.parse import urlencode


def build_maps_link(origin: tuple[float, float], stops: list[dict]) -> str:
    """Builds a Google Maps directions URL: origin -> up to 8 waypoints -> destination
    (the last stop). `stops` must have between 1 and 9 items."""
    if not stops:
        raise ValueError("stops must contain at least one point")
    if len(stops) > MAX_STOPS_PER_SUBLOTE:
        raise ValueError(f"stops must contain at most {MAX_STOPS_PER_SUBLOTE} points")

    waypoints = stops[:-1]
    destination = stops[-1]

    params = {
        "api": "1",
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination['lat']},{destination['lng']}",
    }
    if waypoints:
        params["waypoints"] = "|".join(f"{p['lat']},{p['lng']}" for p in waypoints)

    return "https://www.google.com/maps/dir/?" + urlencode(params)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_algorithm_maps_link.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_algorithm.py tests/test_routes_algorithm_maps_link.py
git commit -m "feat: build Google Maps directions links for sub-lotes"
```

---

### Task 6: Sheet sync

**Goal:** Read all 3 Google Sheet tabs, insert new leads into the local cache (deduplicated by `Place_ID`, or a synthetic key when missing), and geocode anything pending/failed.

**Files:**
- Create: `routes_sheet_sync.py`
- Test: `tests/test_routes_sheet_sync.py`

**Acceptance Criteria:**
- [ ] Reads all 3 tabs and inserts new rows into `leads_cache` with the correct `categoria`
- [ ] Rows already cached by `place_id` are skipped, not duplicated
- [ ] Rows with no `Negocio` are skipped entirely
- [ ] Rows without a real `Place_ID` get a synthetic key derived from category + name + address
- [ ] After sync, every pending/failed row has been run through `geocode_lead`

**Verify:** `pytest tests/test_routes_sheet_sync.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_sheet_sync.py
from unittest.mock import MagicMock

import routes_db as db
import routes_sheet_sync as sync


def _fake_client(tabs_data: dict):
    """tabs_data: {tab_name: [row_dict, ...]}"""
    client = MagicMock()
    sheet = MagicMock()

    def worksheet(name):
        ws = MagicMock()
        ws.get_all_records.return_value = tabs_data.get(name, [])
        return ws

    sheet.worksheet.side_effect = worksheet
    client.open_by_url.return_value = sheet
    return client


def test_sync_all_tabs_inserts_new_leads_from_each_category(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [
            {"Negocio": "Funda B", "Direccion": "Dir B", "Maps_URL": "", "Place_ID": "PB"},
        ],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    summary = sync.sync_all_tabs(conn, client)

    assert summary["nuevos"] == 2
    assert summary["geocodificados"] == 2
    rows = conn.execute("SELECT negocio, categoria FROM leads_cache ORDER BY negocio").fetchall()
    assert [(r["negocio"], r["categoria"]) for r in rows] == [
        ("Funda B", "Fundas"), ("Taller A", "Repuestos"),
    ]


def test_sync_all_tabs_skips_rows_already_cached_by_place_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    db.upsert_lead(conn, "PA", "Repuestos", "Taller A", "Dir A", "")

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)

    summary = sync.sync_all_tabs(conn, client)

    assert summary["nuevos"] == 0
    count = conn.execute("SELECT COUNT(*) AS c FROM leads_cache").fetchone()["c"]
    assert count == 1


def test_sync_all_tabs_skips_rows_without_negocio(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [{"Negocio": "", "Direccion": "Dir A", "Place_ID": ""}],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)

    summary = sync.sync_all_tabs(conn, client)
    assert summary["nuevos"] == 0


def test_row_place_id_falls_back_to_name_and_address_when_missing():
    row = {"Negocio": "Taller Z", "Direccion": "Calle 123", "Place_ID": ""}
    key = sync._row_place_id(row, "Repuestos")
    assert key == "NOID:Repuestos:taller z|calle 123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_sheet_sync.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'routes_sheet_sync'`

- [ ] **Step 3: Write the implementation**

```python
# routes_sheet_sync.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_sheet_sync.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_sheet_sync.py tests/test_routes_sheet_sync.py
git commit -m "feat: sync leads from the 3 Sheet tabs into the local cache"
```

---

### Task 7: Batch generation orchestration

**Goal:** Tie together candidate selection, ordering, chunking, and persistence into a single `generate_lote` call that produces chained sub-lote links.

**Files:**
- Create: `routes_batch.py`
- Test: `tests/test_routes_batch.py`

**Acceptance Criteria:**
- [ ] Geocodes the origin; raises `ValueError` if it can't be geocoded
- [ ] Selects up to N nearest non-shared candidates and orders them into one continuous route
- [ ] Splits into sub-lotes of at most 9, where each sub-lote's Maps link originates from the last stop of the previous sub-lote (not the original origin)
- [ ] Persists the lote, sub-lotes, and sub-lote/lead relationships
- [ ] Works correctly when fewer than N candidates are available

**Verify:** `pytest tests/test_routes_batch.py -v` → all tests pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_batch.py
from unittest.mock import patch

import routes_batch as batch
import routes_db as db


def test_generate_lote_creates_lote_and_chained_sublotes(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    # 11 candidates in a straight line east of the origin, evenly spaced
    for i in range(11):
        lead_id = db.upsert_lead(conn, f"P{i}", "Repuestos", f"Negocio {i}", f"Dir {i}", "")
        db.set_geocode_result(conn, lead_id, -34.60, -58.40 + i * 0.001, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.60, -58.401)):
        result = batch.generate_lote(conn, origen_texto="Local FixLab", n=11)

    assert result["tamano_real"] == 11
    assert [len(s["leads"]) for s in result["sublotes"]] == [9, 2]

    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (result["lote_id"],)).fetchone()
    assert lote["origen_texto"] == "Local FixLab"

    # the second sub-lote's link must originate from the last stop of the first
    # sub-lote, not from the original origin
    first_last_lead = result["sublotes"][0]["leads"][-1]
    second_link = result["sublotes"][1]["maps_link"]
    expected_origin_param = f"origin={first_last_lead['lat']}%2C{first_last_lead['lng']}"
    assert expected_origin_param in second_link


def test_generate_lote_raises_when_origin_not_geocodable(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    with patch("routes_batch.geocoding.geocode_free_text", return_value=None):
        try:
            batch.generate_lote(conn, origen_texto="direccion inventada", n=10)
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_generate_lote_uses_fewer_than_n_when_pool_is_smaller(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Unico", "Dir", "")
    db.set_geocode_result(conn, lead_id, -34.60, -58.40, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.60, -58.401)):
        result = batch.generate_lote(conn, origen_texto="Local FixLab", n=40)

    assert result["tamano_real"] == 1
    assert result["tamano_solicitado"] == 40
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_batch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'routes_batch'`

- [ ] **Step 3: Write the implementation**

```python
# routes_batch.py
"""Orchestrates full lote generation: pool selection, ordering, chunking, and
persistence, chaining each sub-lote's origin from the previous sub-lote's last stop."""
from __future__ import annotations

import sqlite3

import routes_algorithm as algo
import routes_db as db
import routes_geocoding as geocoding


def generate_lote(conn: sqlite3.Connection, origen_texto: str, n: int) -> dict:
    """Geocodes the origin, selects up to n nearby non-shared candidates, orders them
    into a continuous route, splits into <=9-stop sub-lotes chained end-to-end, and
    persists everything. Returns a summary dict."""
    origin_coords = geocoding.geocode_free_text(origen_texto)
    if origin_coords is None:
        raise ValueError(f"No se pudo geocodificar el origen: {origen_texto}")

    pool = [dict(row) for row in db.get_candidate_pool(conn)]
    nearest = algo.select_n_nearest(origin_coords, pool, n)
    ordered = algo.order_nearest_neighbor(origin_coords, nearest)
    chunks = algo.chunk_into_sublotes(ordered)

    lote_id = db.create_lote(
        conn,
        origen_lat=origin_coords[0],
        origen_lng=origin_coords[1],
        origen_texto=origen_texto,
        tamano_solicitado=n,
        tamano_real=len(ordered),
    )

    sublotes_creados = []
    current_origin = origin_coords
    for i, chunk in enumerate(chunks, start=1):
        maps_link = algo.build_maps_link(current_origin, chunk)
        sublote_id = db.create_sublote(
            conn,
            lote_id=lote_id,
            orden=i,
            maps_link=maps_link,
            lead_ids_in_order=[c["id"] for c in chunk],
        )
        sublotes_creados.append({"id": sublote_id, "orden": i, "maps_link": maps_link, "leads": chunk})
        current_origin = (chunk[-1]["lat"], chunk[-1]["lng"])

    return {
        "lote_id": lote_id,
        "origen_texto": origen_texto,
        "tamano_solicitado": n,
        "tamano_real": len(ordered),
        "sublotes": sublotes_creados,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_batch.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_batch.py tests/test_routes_batch.py
git commit -m "feat: orchestrate lote generation with chained sub-lote origins"
```

---

### Task 8: Flask blueprint & UI

**Goal:** Expose the feature as a Flask Blueprint with pages to generate a lote, view/mark sub-lotes as shared, and review history/failed leads.

**Files:**
- Create: `routes_app.py`

**Acceptance Criteria:**
- [ ] `GET /rutas/` shows the generation form
- [ ] `POST /rutas/generar` calls `generate_lote` and shows the resulting sub-lotes with their Maps links, or a clear error if the origin isn't geocodable
- [ ] `POST /rutas/sincronizar` runs the Sheet sync and shows a summary
- [ ] `POST /rutas/sublotes/<id>/compartir` and `POST /rutas/lotes/<id>/compartir` mark sharing state
- [ ] `GET /rutas/fallidos` lists leads with `geocode_source = 'fallido'`
- [ ] `GET /rutas/historial` lists past lotes

**Verify:** Manual — this task has no automated Flask/UI tests, per the approved design (`docs/superpowers/specs/2026-07-13-rutas-comerciales-design.md`, section "Testing"). Verification happens end-to-end in Task 9.

**Steps:**

- [ ] **Step 1: Write the blueprint**

```python
# routes_app.py
"""Flask blueprint for the commercial-routes generator UI."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template_string, request, url_for

import routes_batch as batch
import routes_db as db
import routes_sheet_sync as sheet_sync

rutas_bp = Blueprint("rutas", __name__, url_prefix="/rutas")


def _conn():
    return db.get_connection(db.DB_PATH)


PAGE_HOME = """
<!doctype html>
<title>Rutas comerciales</title>
<h1>Generador de rutas comerciales</h1>
<form method="post" action="{{ url_for('rutas.generar') }}">
  <label>Origen: <input type="text" name="origen" required></label><br>
  <label>Cantidad de direcciones: <input type="number" name="n" value="40" min="1" required></label><br>
  <button type="submit">Generar lote</button>
</form>
<form method="post" action="{{ url_for('rutas.sincronizar') }}">
  <button type="submit">Sincronizar leads desde el Sheet</button>
</form>
{% if sync_summary %}
  <p>Sync: {{ sync_summary.nuevos }} nuevos, {{ sync_summary.geocodificados }} geocodificados,
     {{ sync_summary.fallidos }} fallidos.</p>
{% endif %}
<p><a href="{{ url_for('rutas.historial') }}">Ver historial de lotes</a> |
   <a href="{{ url_for('rutas.fallidos') }}">Ver leads no geocodificables</a></p>
"""

PAGE_RESULTADO = """
<!doctype html>
<title>Lote generado</title>
<h1>Lote #{{ resultado.lote_id }} — {{ resultado.tamano_real }}/{{ resultado.tamano_solicitado }} direcciones</h1>
<p><strong>Aviso:</strong> si el vendedor abre el link desde el navegador del celular
   (en vez de la app de Maps instalada), puede que solo se respeten 3 waypoints en vez de 9.
   Recomendale abrir con la app instalada.</p>
{% for sublote in resultado.sublotes %}
  <h2>Sub-lote {{ sublote.orden }} ({{ sublote.leads|length }} paradas)</h2>
  <p><a href="{{ sublote.maps_link }}" target="_blank">{{ sublote.maps_link }}</a></p>
  <ul>
    {% for lead in sublote.leads %}
      <li>{{ lead.negocio }} — {{ lead.direccion }}</li>
    {% endfor %}
  </ul>
  <form method="post" action="{{ url_for('rutas.compartir_sublote', sublote_id=sublote.id) }}">
    <button type="submit">Marcar este sub-lote como compartido</button>
  </form>
{% endfor %}
<form method="post" action="{{ url_for('rutas.compartir_lote', lote_id=resultado.lote_id) }}">
  <button type="submit">Marcar todo el lote como compartido</button>
</form>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_ERROR = """
<!doctype html>
<title>Error</title>
<p>Error: {{ error }}</p>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_FALLIDOS = """
<!doctype html>
<title>Leads no geocodificables</title>
<h1>Leads no geocodificables</h1>
<ul>
{% for lead in leads %}
  <li>[{{ lead.categoria }}] {{ lead.negocio }} — {{ lead.direccion }}</li>
{% else %}
  <li>Ninguno por ahora.</li>
{% endfor %}
</ul>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""

PAGE_HISTORIAL = """
<!doctype html>
<title>Historial de lotes</title>
<h1>Historial de lotes</h1>
<ul>
{% for lote in lotes %}
  <li>Lote #{{ lote.id }} — {{ lote.fecha_generado }} — origen: {{ lote.origen_texto }}
      — {{ lote.tamano_real }}/{{ lote.tamano_solicitado }} direcciones</li>
{% else %}
  <li>Todavia no generaste ningun lote.</li>
{% endfor %}
</ul>
<p><a href="{{ url_for('rutas.home') }}">Volver</a></p>
"""


@rutas_bp.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE_HOME, sync_summary=None)


@rutas_bp.route("/generar", methods=["POST"])
def generar():
    origen = request.form["origen"]
    n = int(request.form["n"])
    conn = _conn()
    try:
        resultado = batch.generate_lote(conn, origen, n)
    except ValueError as exc:
        return render_template_string(PAGE_ERROR, error=str(exc)), 400
    finally:
        conn.close()
    return render_template_string(PAGE_RESULTADO, resultado=resultado)


@rutas_bp.route("/sincronizar", methods=["POST"])
def sincronizar():
    conn = _conn()
    try:
        client = sheet_sync.get_sheets_client()
        summary = sheet_sync.sync_all_tabs(conn, client)
    except Exception as exc:
        return render_template_string(
            PAGE_ERROR, error=f"No se pudo sincronizar con el Sheet: {exc}"
        ), 502
    finally:
        conn.close()
    return render_template_string(PAGE_HOME, sync_summary=summary)


@rutas_bp.route("/sublotes/<int:sublote_id>/compartir", methods=["POST"])
def compartir_sublote(sublote_id: int):
    conn = _conn()
    try:
        db.mark_sublote_compartido(conn, sublote_id)
    finally:
        conn.close()
    return redirect(url_for("rutas.historial"))


@rutas_bp.route("/lotes/<int:lote_id>/compartir", methods=["POST"])
def compartir_lote(lote_id: int):
    conn = _conn()
    try:
        db.mark_lote_compartido(conn, lote_id)
    finally:
        conn.close()
    return redirect(url_for("rutas.historial"))


@rutas_bp.route("/fallidos", methods=["GET"])
def fallidos():
    conn = _conn()
    try:
        leads = db.get_failed_leads(conn)
    finally:
        conn.close()
    return render_template_string(PAGE_FALLIDOS, leads=leads)


@rutas_bp.route("/historial", methods=["GET"])
def historial():
    conn = _conn()
    try:
        lotes = db.get_lote_history(conn)
    finally:
        conn.close()
    return render_template_string(PAGE_HISTORIAL, lotes=lotes)
```

- [ ] **Step 2: Commit**

```bash
git add routes_app.py
git commit -m "feat: add Flask blueprint and UI for the routes generator"
```

---

### Task 9: Wire into `app.py` and smoke-test end-to-end

**Goal:** Register the new blueprint on the existing Flask app, initialize the SQLite database on startup, and manually verify the full flow.

**Files:**
- Modify: `app.py:14` (right after `app = Flask(__name__)`)

**Acceptance Criteria:**
- [ ] `python app.py` starts without errors
- [ ] `http://localhost:5000/rutas/` loads the generation form
- [ ] Existing routes (`/`, `/historial`, `/run`, etc.) still work unmodified

**Verify:** Manual smoke test (see Step 3) — this is a UI-wiring change with no new pure logic to unit test.

**Steps:**

- [ ] **Step 1: Register the blueprint**

In `app.py`, immediately after line 14 (`app = Flask(__name__)`), add:

```python
import routes_app
import routes_db

routes_db.init_db()
app.register_blueprint(routes_app.rutas_bp)
```

- [ ] **Step 2: Run the full test suite to make sure nothing broke**

Run: `pytest -v`
Expected: PASS (all tests from Tasks 1-7)

- [ ] **Step 3: Manual smoke test**

```bash
python app.py
```

Then in a browser:
1. Open `http://localhost:5000/` — confirm the existing scraper dashboard still loads.
2. Open `http://localhost:5000/rutas/` — confirm the generation form loads.
3. Click "Sincronizar leads desde el Sheet" — confirm it reads the 3 tabs (first run will trigger the OAuth browser flow if `token.pickle` isn't already valid) and shows a summary.
4. Enter an origin address and a small `n` (e.g. 5), click "Generar lote" — confirm sub-lotes with working Maps links appear.
5. Click a Maps link — confirm it opens Google Maps with the correct origin/waypoints/destination.
6. Click "Marcar este sub-lote como compartido" — confirm it redirects to `/rutas/historial` and the lote appears there.
7. Open `/rutas/fallidos` — confirm any leads that failed geocoding are listed.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: register routes blueprint and initialize routes database on startup"
```
