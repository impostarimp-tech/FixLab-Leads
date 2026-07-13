# Backfill de geocoding vía Apify — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recuperar los 728 leads con `geocode_source = 'fallido'` buscándolos en Google Maps vía Apify (Place_ID directo cuando existe, nombre+verificación cuando no), y rellenar la columna `Direccion` del Sheet para los que no tenían ninguna.

**Architecture:** Dos módulos puros y testeables (`routes_apify_geocoding.py` para matching/verificación, `routes_apify_sheet_writeback.py` para ubicar/escribir filas del Sheet) más un script orquestador (`backfill_apify_geocoding.py`) que los conecta con `ApifyClient` y `gspread`. Sin cambios a `routes_geocoding.py`, `routes_db.py` (salvo nuevos valores de string en una columna existente) ni `routes_sheet_sync.py`.

**Tech Stack:** Python, `apify-client` (ya en requirements.txt), `gspread` (ya en requirements.txt), `pytest` + `unittest.mock`.

**Spec:** [docs/superpowers/specs/2026-07-13-apify-geocoding-backfill-design.md](../specs/2026-07-13-apify-geocoding-backfill-design.md)

---

## Contexto técnico confirmado antes de planear

El actor `compass/crawler-google-places` (mismo que usa `prospector.py`) soporta:
- Input `placeIds: string[]` para lookup directo por Place_ID real.
- Input `searchStringsArray: string[]` + `locationQuery: string` para búsqueda por texto, con un ítem de resultado por cada string de búsqueda.
- Cada ítem del dataset resultante trae `searchString` (el string que lo originó), `placeId`, `title`, `address`, y `location: {lat, lng}` — confirmado vía `fetch-actor-details` y la documentación del actor.

---

### Task 1: routes_apify_geocoding.py — matching y verificación

**Goal:** Módulo puro (sin red) con toda la lógica de matching/verificación/batching.

**Files:**
- Create: `routes_apify_geocoding.py`
- Test: `tests/test_routes_apify_geocoding.py`

**Acceptance Criteria:**
- [ ] `is_real_place_id` distingue Place_ID real de clave sintética `NOID:`
- [ ] `name_similarity` compara ignorando mayúsculas/acentos
- [ ] `verify_placeid_match` / `verify_name_match` aplican el bounding box AMBA (y similitud de nombre para el segundo)
- [ ] `chunk` divide listas en lotes del tamaño pedido
- [ ] `build_placeid_run_input` / `build_search_run_input` arman el input correcto para el actor
- [ ] `group_results_by_search_string` agrupa resultados de un lote por el nombre que los originó

**Verify:** `pytest tests/test_routes_apify_geocoding.py -v` → todos los tests en verde

**Steps:**

- [ ] **Step 1: Escribir los tests (deben fallar — el módulo no existe todavía)**

Crear `tests/test_routes_apify_geocoding.py`:

```python
import routes_apify_geocoding as apigeo


def test_is_real_place_id_true_for_google_place_id():
    assert apigeo.is_real_place_id("ChIJreV9aqYWdkgROM_boL6YbwA") is True


def test_is_real_place_id_false_for_synthetic_noid_key():
    assert apigeo.is_real_place_id("NOID:Repuestos:taller z|calle 123") is False


def test_name_similarity_is_high_for_identical_names():
    assert apigeo.name_similarity("Taller Diaz", "Taller Diaz") == 1.0


def test_name_similarity_ignores_case_and_accents():
    assert apigeo.name_similarity("Taller Díaz", "TALLER DIAZ") == 1.0


def test_name_similarity_is_low_for_unrelated_names():
    assert apigeo.name_similarity("Taller Diaz", "Kiosco El Sol") < 0.4


def test_verify_placeid_match_accepts_coords_inside_amba():
    assert apigeo.verify_placeid_match(-34.6083, -58.3712) is True


def test_verify_placeid_match_rejects_coords_outside_amba():
    assert apigeo.verify_placeid_match(-36.0158034, -59.0941764) is False


def test_verify_name_match_accepts_similar_name_inside_amba():
    assert apigeo.verify_name_match("Taller Diaz", "Taller Diaz SRL", -34.6083, -58.3712) is True


def test_verify_name_match_rejects_dissimilar_name_inside_amba():
    assert apigeo.verify_name_match("Taller Diaz", "Kiosco El Sol", -34.6083, -58.3712) is False


def test_verify_name_match_rejects_similar_name_outside_amba():
    assert apigeo.verify_name_match("Taller Diaz", "Taller Diaz SRL", -36.0158034, -59.0941764) is False


def test_chunk_splits_into_groups_of_requested_size():
    assert apigeo.chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_chunk_returns_single_chunk_when_smaller_than_size():
    assert apigeo.chunk([1, 2], 10) == [[1, 2]]


def test_chunk_returns_empty_list_for_empty_input():
    assert apigeo.chunk([], 5) == []


def test_build_placeid_run_input_wraps_ids():
    assert apigeo.build_placeid_run_input(["A", "B"]) == {"placeIds": ["A", "B"]}


def test_build_search_run_input_uses_default_location_and_top_result_only():
    result = apigeo.build_search_run_input(["Taller A", "Taller B"])
    assert result == {
        "searchStringsArray": ["Taller A", "Taller B"],
        "locationQuery": apigeo.DEFAULT_LOCATION_QUERY,
        "maxCrawledPlacesPerSearch": 1,
        "language": "es",
    }


def test_group_results_by_search_string_groups_matching_items():
    results = [
        {"searchString": "Taller A", "title": "Taller A SRL"},
        {"searchString": "Taller B", "title": "Taller B"},
        {"searchString": "Taller A", "title": "Otro resultado para A"},
    ]
    grouped = apigeo.group_results_by_search_string(results)
    assert [r["title"] for r in grouped["Taller A"]] == ["Taller A SRL", "Otro resultado para A"]
    assert [r["title"] for r in grouped["Taller B"]] == ["Taller B"]


def test_group_results_by_search_string_ignores_items_without_search_string():
    results = [{"title": "Sin searchString"}]
    grouped = apigeo.group_results_by_search_string(results)
    assert grouped == {"": [{"title": "Sin searchString"}]}
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `pytest tests/test_routes_apify_geocoding.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'routes_apify_geocoding'`

- [ ] **Step 3: Implementar el módulo**

Crear `routes_apify_geocoding.py`:

```python
"""Matching and verification logic for the Apify-based geocoding backfill of
leads that failed Nominatim geocoding. Reuses the AMBA bounding-box check from
routes_geocoding.py as the safety net against wrong-area matches."""
from __future__ import annotations

import difflib
import unicodedata

import routes_geocoding as geocoding

NAME_SIMILARITY_THRESHOLD = 0.6
DEFAULT_LOCATION_QUERY = "Ciudad Autonoma de Buenos Aires, Argentina"


def is_real_place_id(place_id: str) -> bool:
    """A real Google Place_ID never starts with 'NOID:' -- that prefix marks
    the synthetic key routes_sheet_sync.py builds when the Sheet had no
    Place_ID for a row (see _row_place_id)."""
    return not place_id.startswith("NOID:")


def _normalize_name(text: str) -> str:
    """Lowercases and strips accents so 'Taller Díaz' matches 'taller diaz'."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def name_similarity(a: str, b: str) -> float:
    """Text similarity ratio (0.0-1.0) between two business names, accent- and
    case-insensitive."""
    return difflib.SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def verify_placeid_match(lat: float, lng: float) -> bool:
    """A Place_ID lookup only needs the zone safety check -- the ID itself
    already identifies the exact business."""
    return geocoding._within_amba_bounds(lat, lng)


def verify_name_match(
    negocio: str, result_title: str, lat: float, lng: float,
    threshold: float = NAME_SIMILARITY_THRESHOLD,
) -> bool:
    """A name-search match needs both name similarity and zone to pass --
    accepting on zone alone risks matching the wrong business with a similar
    name; accepting on name alone risks matching a same-named business in the
    wrong city. This is the check that avoids repeating the direccion='-'
    false-match bug from the original geocoding pipeline."""
    return (
        name_similarity(negocio, result_title) >= threshold
        and geocoding._within_amba_bounds(lat, lng)
    )


def chunk(items: list, size: int) -> list[list]:
    """Splits items into consecutive chunks of at most `size`."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_placeid_run_input(place_ids: list[str]) -> dict:
    return {"placeIds": place_ids}


def build_search_run_input(negocios: list[str], location_query: str = DEFAULT_LOCATION_QUERY) -> dict:
    return {
        "searchStringsArray": negocios,
        "locationQuery": location_query,
        "maxCrawledPlacesPerSearch": 1,
        "language": "es",
    }


def group_results_by_search_string(results: list[dict]) -> dict[str, list[dict]]:
    """Groups a batched actor run's dataset items by the searchString that
    produced each one, since one run covers many business names at once."""
    grouped: dict[str, list[dict]] = {}
    for item in results:
        key = item.get("searchString", "")
        grouped.setdefault(key, []).append(item)
    return grouped
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `pytest tests/test_routes_apify_geocoding.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_apify_geocoding.py tests/test_routes_apify_geocoding.py
git commit -m "feat: add matching/verification logic for Apify geocoding backfill"
```

---

### Task 2: routes_apify_sheet_writeback.py — escritura acotada al Sheet

**Goal:** Módulo con la lógica de ubicar filas en el Sheet (por Place_ID o por Negocio) y escribir la columna Direccion en batch.

**Files:**
- Create: `routes_apify_sheet_writeback.py`
- Test: `tests/test_routes_apify_sheet_writeback.py`

**Acceptance Criteria:**
- [ ] `is_direccion_placeholder` detecta vacío/"-"
- [ ] `build_row_index` indexa una pestaña una sola vez por Place_ID y por Negocio (case-insensitive)
- [ ] `find_row` prioriza Place_ID, cae a Negocio, devuelve None si no hay match
- [ ] `direccion_column_index` ubica la columna por header
- [ ] `apply_direccion_updates` escribe en un único `update_cells` por pestaña, no-op si no hay updates

**Verify:** `pytest tests/test_routes_apify_sheet_writeback.py -v` → todos los tests en verde

**Steps:**

- [ ] **Step 1: Escribir los tests (deben fallar — el módulo no existe todavía)**

Crear `tests/test_routes_apify_sheet_writeback.py`:

```python
from unittest.mock import MagicMock

import routes_apify_sheet_writeback as sheetwb


def _fake_worksheet(records, headers):
    ws = MagicMock()
    ws.get_all_records.return_value = records
    ws.row_values.return_value = headers
    return ws


def test_is_direccion_placeholder_true_for_empty_and_dash():
    assert sheetwb.is_direccion_placeholder("") is True
    assert sheetwb.is_direccion_placeholder("-") is True
    assert sheetwb.is_direccion_placeholder(None) is True


def test_is_direccion_placeholder_false_for_real_address():
    assert sheetwb.is_direccion_placeholder("Av. Rivadavia 100") is False


def test_build_row_index_indexes_by_place_id_and_negocio():
    records = [
        {"Negocio": "Taller A", "Place_ID": "PA"},
        {"Negocio": "Taller B", "Place_ID": ""},
    ]
    ws = _fake_worksheet(records, ["Negocio", "Direccion", "Place_ID"])
    index = sheetwb.build_row_index(ws)
    assert index["by_place_id"] == {"PA": 2}
    assert index["by_negocio"] == {"taller a": 2, "taller b": 3}


def test_find_row_prefers_place_id_match():
    index = {"by_place_id": {"PA": 2}, "by_negocio": {"taller a": 5}}
    assert sheetwb.find_row(index, "PA", "Taller A") == 2


def test_find_row_falls_back_to_negocio_when_place_id_not_found():
    index = {"by_place_id": {}, "by_negocio": {"taller a": 5}}
    assert sheetwb.find_row(index, "NOID:Repuestos:taller a|-", "Taller A") == 5


def test_find_row_returns_none_when_nothing_matches():
    index = {"by_place_id": {}, "by_negocio": {}}
    assert sheetwb.find_row(index, "PX", "Desconocido") is None


def test_direccion_column_index_finds_header_position():
    ws = _fake_worksheet([], ["Zona", "Negocio", "Direccion", "Place_ID"])
    assert sheetwb.direccion_column_index(ws) == 3


def test_apply_direccion_updates_writes_single_batch_call():
    ws = _fake_worksheet([], ["Negocio", "Direccion"])
    sheetwb.apply_direccion_updates(ws, {5: "Av. Rivadavia 100", 8: "Av. Corrientes 200"})

    ws.update_cells.assert_called_once()
    cells = ws.update_cells.call_args[0][0]
    assert {(c.row, c.col, c.value) for c in cells} == {
        (5, 2, "Av. Rivadavia 100"), (8, 2, "Av. Corrientes 200"),
    }


def test_apply_direccion_updates_does_nothing_for_empty_updates():
    ws = _fake_worksheet([], ["Negocio", "Direccion"])
    sheetwb.apply_direccion_updates(ws, {})
    ws.update_cells.assert_not_called()
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `pytest tests/test_routes_apify_sheet_writeback.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'routes_apify_sheet_writeback'`

- [ ] **Step 3: Implementar el módulo**

Crear `routes_apify_sheet_writeback.py`:

```python
"""Writes Apify-resolved addresses back into the Google Sheet's Direccion
column -- the one deliberate exception to routes_db.py's "the Sheet is never
written to" rule, scoped to leads whose Direccion was empty or a placeholder
(see docs/superpowers/specs/2026-07-13-apify-geocoding-backfill-design.md)."""
from __future__ import annotations

import gspread

DIRECCION_PLACEHOLDERS = {"", "-"}


def is_direccion_placeholder(direccion: str | None) -> bool:
    return (direccion or "").strip() in DIRECCION_PLACEHOLDERS


def build_row_index(ws: gspread.Worksheet) -> dict:
    """Reads the tab once and indexes rows by Place_ID and by lowercased
    Negocio, so many lookups against the same tab don't re-fetch it."""
    records = ws.get_all_records()
    by_place_id: dict[str, int] = {}
    by_negocio: dict[str, int] = {}
    for i, row in enumerate(records, start=2):  # row 1 is the header
        place_id = (row.get("Place_ID") or "").strip()
        if place_id:
            by_place_id[place_id] = i
        negocio = (row.get("Negocio") or "").strip().lower()
        if negocio:
            by_negocio.setdefault(negocio, i)
    return {"by_place_id": by_place_id, "by_negocio": by_negocio}


def find_row(index: dict, place_id: str, negocio: str) -> int | None:
    """Prefers an exact Place_ID match; falls back to Negocio for leads whose
    synthetic (NOID:) place_id has no corresponding Sheet cell."""
    row = index["by_place_id"].get(place_id)
    if row is not None:
        return row
    return index["by_negocio"].get(negocio.strip().lower())


def direccion_column_index(ws: gspread.Worksheet) -> int:
    """1-indexed column position of the 'Direccion' header."""
    headers = ws.row_values(1)
    return headers.index("Direccion") + 1


def apply_direccion_updates(ws: gspread.Worksheet, updates: dict[int, str]) -> None:
    """Writes {row: direccion} in a single batch call per worksheet."""
    if not updates:
        return
    col = direccion_column_index(ws)
    cell_list = [gspread.Cell(row, col, value) for row, value in updates.items()]
    ws.update_cells(cell_list)
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `pytest tests/test_routes_apify_sheet_writeback.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add routes_apify_sheet_writeback.py tests/test_routes_apify_sheet_writeback.py
git commit -m "feat: add Sheet row-lookup and batch Direccion writeback logic"
```

---

### Task 3: backfill_apify_geocoding.py — script orquestador

**Goal:** Script CLI que orquesta las dos fases de geocoding vía Apify y la escritura al Sheet, con modo `--dry-run`.

**Files:**
- Create: `backfill_apify_geocoding.py`
- Test: `tests/test_backfill_apify_geocoding.py`

**Acceptance Criteria:**
- [ ] Fase Place_ID: acepta dentro de AMBA, rechaza fuera, actualiza `leads_cache` con `apify_placeid`
- [ ] Fase nombre: lotea, mapea resultados por `searchString` a los leads correctos, actualiza con `apify_nombre`
- [ ] `--dry-run` gasta créditos de Apify pero no escribe en DB ni Sheet
- [ ] Escritura al Sheet solo para leads con direccion original vacía/"-" y resueltos por Apify
- [ ] Una corrida de Apify que falla no rompe el script
- [ ] Una pestaña de Sheet no encontrada no rompe el script

**Verify:** `pytest tests/test_backfill_apify_geocoding.py -v && pytest -v`

**Steps:**

- [ ] **Step 1: Escribir los tests (deben fallar — el módulo no existe todavía)**

Crear `tests/test_backfill_apify_geocoding.py`:

```python
from unittest.mock import MagicMock

import gspread

import backfill_apify_geocoding as backfill
import routes_db as db


def _fake_apify_client(dataset_by_call):
    """dataset_by_call: list of result-lists, one per expected client.actor(...).call(...)
    invocation, consumed in call order. Careful: the Place_ID phase makes ZERO
    calls when there are no leads with a real Place_ID (it returns early), so
    when a test only has leads without a Place_ID, dataset_by_call must have a
    single entry for the name-search call -- not a leading placeholder for a
    Place_ID call that never happens."""
    client = MagicMock()
    call_iter = iter(dataset_by_call)
    state = {}

    def call(run_input):
        state["items"] = next(call_iter)
        run = MagicMock()
        run.default_dataset_id = "ds"
        return run

    client.actor.return_value.call.side_effect = call
    client.dataset.return_value.iterate_items.side_effect = lambda: state["items"]
    return client


def _make_tab(records, headers):
    ws = MagicMock()
    ws.get_all_records.return_value = records
    ws.row_values.return_value = headers
    return {"ws": ws}


def _fake_sheets_client(tabs_data):
    """tabs_data: {tab_name: {"ws": MagicMock}}"""
    client = MagicMock()
    sheet = MagicMock()

    def worksheet(name):
        if name not in tabs_data:
            raise gspread.exceptions.WorksheetNotFound(name)
        return tabs_data[name]["ws"]

    sheet.worksheet.side_effect = worksheet
    client.open_by_url.return_value = sheet
    return client


def _seed_fallido(conn, place_id, categoria, negocio, direccion):
    lead_id = db.upsert_lead(conn, place_id, categoria, negocio, direccion, "")
    db.set_geocode_result(conn, lead_id, None, None, "fallido")
    return lead_id


def test_run_backfill_accepts_placeid_match_inside_amba(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = _seed_fallido(conn, "ChIJrealPlaceId", "Repuestos", "Taller A", "-")

    # sin_place_id is empty (this is the only lead, and it has a real
    # Place_ID), so the name-search phase never calls Apify -- this is the
    # only call made.
    apify_client = _fake_apify_client([
        [{"placeId": "ChIJrealPlaceId", "title": "Taller A",
          "address": "Av. Rivadavia 100", "location": {"lat": -34.6083, "lng": -58.3712}}],
    ])
    tab = _make_tab(
        [{"Negocio": "Taller A", "Direccion": "-", "Place_ID": "ChIJrealPlaceId"}],
        ["Negocio", "Direccion", "Place_ID"],
    )
    sheets_client = _fake_sheets_client({"Leads FixLab - Talleres CABA (mayorista repuestos)": tab})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    lead = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert lead["geocode_source"] == "apify_placeid"
    assert (lead["lat"], lead["lng"]) == (-34.6083, -58.3712)
    assert summary["resueltos_placeid"] == 1
    assert summary["direcciones_actualizadas_sheet"] == 1
    tab["ws"].update_cells.assert_called_once()


def test_run_backfill_rejects_placeid_match_outside_amba(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = _seed_fallido(conn, "ChIJrealPlaceId", "Repuestos", "Taller A", "-")

    apify_client = _fake_apify_client([
        [{"placeId": "ChIJrealPlaceId", "title": "Taller A",
          "address": "Rosario 100", "location": {"lat": -32.9, "lng": -60.6}}],
    ])
    sheets_client = _fake_sheets_client({})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    lead = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert lead["geocode_source"] == "fallido"
    assert lead["lat"] is None
    assert summary["resueltos_placeid"] == 0
    assert summary["siguen_fallidos"] == 1


def test_run_backfill_accepts_nombre_match_with_sufficient_similarity(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = _seed_fallido(conn, "NOID:Fundas:funda azul|-", "Fundas", "Funda Azul", "-")

    # con_place_id is empty for this lead (synthetic NOID: place_id), so the
    # Place_ID phase returns early without calling Apify at all -- the
    # name-search call below is the only (and therefore first) call made.
    apify_client = _fake_apify_client([
        [{"searchString": "Funda Azul", "title": "Funda Azul SRL",
          "address": "Av. Corrientes 500", "location": {"lat": -34.6, "lng": -58.45}}],
    ])
    tab = _make_tab(
        [{"Negocio": "Funda Azul", "Direccion": "-", "Place_ID": ""}],
        ["Negocio", "Direccion", "Place_ID"],
    )
    sheets_client = _fake_sheets_client({"Leads Fundas - Maps": tab})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    lead = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert lead["geocode_source"] == "apify_nombre"
    assert (lead["lat"], lead["lng"]) == (-34.6, -58.45)
    assert summary["resueltos_nombre"] == 1
    assert summary["direcciones_actualizadas_sheet"] == 1


def test_run_backfill_maps_batched_nombre_results_to_correct_leads(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_a = _seed_fallido(conn, "NOID:Fundas:funda azul|-", "Fundas", "Funda Azul", "-")
    lead_b = _seed_fallido(conn, "NOID:Fundas:funda roja|-", "Fundas", "Funda Roja", "-")

    # Both leads have synthetic NOID: place_ids, so the Place_ID phase makes
    # no calls -- this single name-search call (covering both business names
    # in one searchStringsArray) is the only call made.
    apify_client = _fake_apify_client([
        [
            {"searchString": "Funda Roja", "title": "Funda Roja",
             "address": "Calle Roja 2", "location": {"lat": -34.61, "lng": -58.46}},
            {"searchString": "Funda Azul", "title": "Funda Azul",
             "address": "Calle Azul 1", "location": {"lat": -34.6, "lng": -58.45}},
        ],
    ])
    tab = _make_tab(
        [
            {"Negocio": "Funda Azul", "Direccion": "-", "Place_ID": ""},
            {"Negocio": "Funda Roja", "Direccion": "-", "Place_ID": ""},
        ],
        ["Negocio", "Direccion", "Place_ID"],
    )
    sheets_client = _fake_sheets_client({"Leads Fundas - Maps": tab})

    backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    row_a = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_a,)).fetchone()
    row_b = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_b,)).fetchone()
    assert (row_a["lat"], row_a["lng"]) == (-34.6, -58.45)
    assert (row_b["lat"], row_b["lng"]) == (-34.61, -58.46)


def test_run_backfill_dry_run_does_not_write_db_or_sheet(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = _seed_fallido(conn, "ChIJrealPlaceId", "Repuestos", "Taller A", "-")

    apify_client = _fake_apify_client([
        [{"placeId": "ChIJrealPlaceId", "title": "Taller A",
          "address": "Av. Rivadavia 100", "location": {"lat": -34.6083, "lng": -58.3712}}],
    ])
    sheets_client = _fake_sheets_client({})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=True)

    lead = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert lead["geocode_source"] == "fallido"
    assert summary["resueltos_placeid"] == 1
    sheets_client.open_by_url.assert_not_called()


def test_run_backfill_warns_and_continues_when_apify_call_fails(tmp_path, capsys):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = _seed_fallido(conn, "ChIJrealPlaceId", "Repuestos", "Taller A", "-")

    apify_client = MagicMock()
    apify_client.actor.return_value.call.side_effect = RuntimeError("network down")
    sheets_client = _fake_sheets_client({})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    lead = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert lead["geocode_source"] == "fallido"
    assert summary["resueltos_placeid"] == 0
    assert "ADVERTENCIA" in capsys.readouterr().out


def test_run_backfill_warns_and_continues_when_sheet_tab_not_found(tmp_path, capsys):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    _seed_fallido(conn, "ChIJrealPlaceId", "Repuestos", "Taller A", "-")

    apify_client = _fake_apify_client([
        [{"placeId": "ChIJrealPlaceId", "title": "Taller A",
          "address": "Av. Rivadavia 100", "location": {"lat": -34.6083, "lng": -58.3712}}],
    ])
    sheets_client = _fake_sheets_client({})  # no hay pestañas configuradas

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    assert summary["direcciones_actualizadas_sheet"] == 0
    assert "no encontrada" in capsys.readouterr().out


def test_run_backfill_does_not_touch_sheet_for_leads_with_existing_direccion(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    _seed_fallido(conn, "ChIJrealPlaceId", "Repuestos", "Taller A", "Av. Rivadavia 100 (sin geocodificar)")

    apify_client = _fake_apify_client([
        [{"placeId": "ChIJrealPlaceId", "title": "Taller A",
          "address": "Av. Rivadavia 100", "location": {"lat": -34.6083, "lng": -58.3712}}],
    ])
    sheets_client = _fake_sheets_client({})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    assert summary["resueltos_placeid"] == 1
    assert summary["direcciones_actualizadas_sheet"] == 0
    sheets_client.open_by_url.assert_not_called()


def test_run_backfill_with_no_fallidos_makes_no_apify_calls(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    apify_client = MagicMock()
    sheets_client = _fake_sheets_client({})

    summary = backfill.run_backfill(conn, apify_client, sheets_client, dry_run=False)

    assert summary == {
        "resueltos_placeid": 0, "resueltos_nombre": 0, "rechazados": 0,
        "siguen_fallidos": 0, "direcciones_actualizadas_sheet": 0, "costo_estimado_usd": 0.0,
    }
    apify_client.actor.assert_not_called()
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `pytest tests/test_backfill_apify_geocoding.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backfill_apify_geocoding'`

- [ ] **Step 3: Implementar el script**

Crear `backfill_apify_geocoding.py`:

```python
"""One-off backfill: recovers leads that failed Nominatim geocoding by
searching Google Maps via Apify (compass/crawler-google-places), then writes
resolved addresses back into the Sheet for leads that had none. Manual,
standalone -- not part of the regular sync pipeline (see
docs/superpowers/specs/2026-07-13-apify-geocoding-backfill-design.md).

Uso:
    python backfill_apify_geocoding.py             # corrida real
    python backfill_apify_geocoding.py --dry-run    # gasta creditos de Apify pero no escribe nada
"""
from __future__ import annotations

import argparse
import os
import sqlite3

import gspread
from apify_client import ApifyClient

import routes_apify_geocoding as apigeo
import routes_apify_sheet_writeback as sheetwb
import routes_db as db
import routes_sheet_sync as sync

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_ID = "compass/crawler-google-places"
BATCH_SIZE = 75
COST_PER_RESULT_USD = 0.002


def _run_actor(client: ApifyClient, run_input: dict) -> list[dict]:
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    return list(client.dataset(run.default_dataset_id).iterate_items())


def _best_verified_match(negocio: str, candidates: list[dict]):
    """Returns (lat, lng, address) for the first candidate that passes
    verification, or None if none do."""
    for item in candidates:
        location = item.get("location") or {}
        lat, lng = location.get("lat"), location.get("lng")
        title = item.get("title") or ""
        if lat is not None and lng is not None and apigeo.verify_name_match(negocio, title, lat, lng):
            return lat, lng, (item.get("address") or "").strip()
    return None


def _process_placeid_group(conn, client, leads, dry_run):
    """leads: sqlite3.Row list with a real Place_ID. Returns
    (accepted_count, rejected_count, sheet_candidates)."""
    if not leads:
        return 0, 0, []

    place_ids = [lead["place_id"] for lead in leads]
    by_place_id = {lead["place_id"]: lead for lead in leads}

    try:
        results = _run_actor(client, apigeo.build_placeid_run_input(place_ids))
    except Exception as e:
        print(f"  ADVERTENCIA: fallo la corrida de Place_ID: {e}. Se saltean {len(leads)} leads.")
        return 0, len(leads), []

    accepted = 0
    sheet_candidates = []
    for item in results:
        place_id = (item.get("placeId") or "").strip()
        lead = by_place_id.get(place_id)
        if lead is None:
            continue
        location = item.get("location") or {}
        lat, lng = location.get("lat"), location.get("lng")
        if lat is None or lng is None or not apigeo.verify_placeid_match(lat, lng):
            continue
        accepted += 1
        if not dry_run:
            db.set_geocode_result(conn, lead["id"], lat, lng, "apify_placeid")
        if sheetwb.is_direccion_placeholder(lead["direccion"]):
            sheet_candidates.append({
                "categoria": lead["categoria"], "place_id": place_id,
                "negocio": lead["negocio"], "direccion_nueva": (item.get("address") or "").strip(),
            })

    rejected = len(leads) - accepted
    print(f"  Place_ID: {accepted} aceptados, {rejected} rechazados/no encontrados")
    return accepted, rejected, sheet_candidates


def _process_nombre_group(conn, client, leads, dry_run, batch_size=BATCH_SIZE):
    """leads: sqlite3.Row list without a real Place_ID. Returns
    (accepted_count, rejected_count, sheet_candidates)."""
    if not leads:
        return 0, 0, []

    accepted = 0
    rejected = 0
    sheet_candidates = []
    chunks = apigeo.chunk(leads, batch_size)
    for batch_num, batch_leads in enumerate(chunks, start=1):
        by_negocio: dict[str, list] = {}
        for lead in batch_leads:
            by_negocio.setdefault(lead["negocio"], []).append(lead)
        negocios = list(by_negocio.keys())

        try:
            results = _run_actor(client, apigeo.build_search_run_input(negocios))
        except Exception as e:
            print(f"  ADVERTENCIA: fallo el lote {batch_num}/{len(chunks)}: {e}. Se saltea.")
            rejected += len(batch_leads)
            continue

        grouped = apigeo.group_results_by_search_string(results)

        batch_accepted = 0
        batch_rejected = 0
        for negocio, matching_leads in by_negocio.items():
            match = _best_verified_match(negocio, grouped.get(negocio, []))
            if match is None:
                batch_rejected += len(matching_leads)
                continue
            lat, lng, address = match
            batch_accepted += len(matching_leads)
            for lead in matching_leads:
                if not dry_run:
                    db.set_geocode_result(conn, lead["id"], lat, lng, "apify_nombre")
                if sheetwb.is_direccion_placeholder(lead["direccion"]):
                    sheet_candidates.append({
                        "categoria": lead["categoria"], "place_id": lead["place_id"],
                        "negocio": lead["negocio"], "direccion_nueva": address,
                    })

        accepted += batch_accepted
        rejected += batch_rejected
        print(f"  Lote {batch_num}/{len(chunks)} ({len(negocios)} nombres): "
              f"{batch_accepted} aceptados, {batch_rejected} rechazados")

    return accepted, rejected, sheet_candidates


def _update_sheet_direcciones(sheets_client, updates: list[dict]) -> int:
    """Groups updates by category tab, builds a row index per tab, and writes
    Direccion values in a single batch call per tab. Returns the total count
    of cells written."""
    if not updates:
        return 0

    sh = sheets_client.open_by_url(sync.SPREADSHEET_URL)
    by_categoria: dict[str, list[dict]] = {}
    for update in updates:
        by_categoria.setdefault(update["categoria"], []).append(update)

    total_written = 0
    for categoria, categoria_updates in by_categoria.items():
        tab_name = sync.CATEGORIA_TABS[categoria]
        try:
            ws = sh.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"  ADVERTENCIA: pestaña '{tab_name}' no encontrada, "
                  f"se saltean {len(categoria_updates)} direcciones")
            continue

        index = sheetwb.build_row_index(ws)
        row_values: dict[int, str] = {}
        for update in categoria_updates:
            row = sheetwb.find_row(index, update["place_id"], update["negocio"])
            if row is None:
                print(f"  ADVERTENCIA: no se encontro en el Sheet: '{update['negocio']}' ({categoria})")
                continue
            row_values[row] = update["direccion_nueva"]

        sheetwb.apply_direccion_updates(ws, row_values)
        total_written += len(row_values)

    return total_written


def run_backfill(conn: sqlite3.Connection, apify_client: ApifyClient,
                  sheets_client, dry_run: bool = False) -> dict:
    """Orchestrates the full backfill: DB phase (placeId lookups, then name
    searches) followed by the Sheet write-back phase. Returns a summary dict."""
    fallidos = db.get_failed_leads(conn)
    con_place_id = [lead for lead in fallidos if apigeo.is_real_place_id(lead["place_id"])]
    sin_place_id = [lead for lead in fallidos if not apigeo.is_real_place_id(lead["place_id"])]

    print(f"Fallidos: {len(fallidos)} total ({len(con_place_id)} con Place_ID real, "
          f"{len(sin_place_id)} sin Place_ID)")

    print("\nFase 1: lookup por Place_ID")
    placeid_accepted, placeid_rejected, placeid_sheet = _process_placeid_group(
        conn, apify_client, con_place_id, dry_run
    )

    print("\nFase 2: busqueda por nombre")
    nombre_accepted, nombre_rejected, nombre_sheet = _process_nombre_group(
        conn, apify_client, sin_place_id, dry_run
    )

    resultados_totales = len(con_place_id) + len(sin_place_id)
    costo_estimado = round(resultados_totales * COST_PER_RESULT_USD, 2)

    summary = {
        "resueltos_placeid": placeid_accepted,
        "resueltos_nombre": nombre_accepted,
        "rechazados": placeid_rejected + nombre_rejected,
        "siguen_fallidos": len(fallidos) - placeid_accepted - nombre_accepted,
        "direcciones_actualizadas_sheet": 0,
        "costo_estimado_usd": costo_estimado,
    }

    if not dry_run:
        sheet_updates = placeid_sheet + nombre_sheet
        summary["direcciones_actualizadas_sheet"] = _update_sheet_direcciones(sheets_client, sheet_updates)

    print("\nResumen:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill de geocoding via Apify para leads fallidos")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Corre contra Apify de verdad (gasta creditos) pero no escribe en la DB ni en el Sheet",
    )
    args = parser.parse_args()

    if not APIFY_API_TOKEN:
        raise SystemExit("ERROR: APIFY_API_TOKEN no esta configurado.")

    db.init_db()
    conn = db.get_connection()
    apify_client = ApifyClient(APIFY_API_TOKEN)
    sheets_client = sync.get_sheets_client()

    run_backfill(conn, apify_client, sheets_client, dry_run=args.dry_run)
```

- [ ] **Step 4: Correr los tests del módulo, confirmar que pasan**

Run: `pytest tests/test_backfill_apify_geocoding.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Correr la suite completa, confirmar que no se rompió nada existente**

Run: `pytest -v`
Expected: PASS (todos los tests existentes + los nuevos de las 3 tareas)

- [ ] **Step 6: Commit**

```bash
git add backfill_apify_geocoding.py tests/test_backfill_apify_geocoding.py
git commit -m "feat: add Apify geocoding backfill orchestrator script"
```

---

## Notas para quien ejecute el plan

- Ningún test llama a la API real de Apify ni de Google Sheets — todo mockeado, igual que el resto de la suite.
- La corrida real (`python backfill_apify_geocoding.py`) requiere `APIFY_API_TOKEN` y `SPREADSHEET_URL` en el entorno (ya están en `launch.bat`) y `token.pickle` vigente (ya generado en sesiones anteriores del proyecto).
- Antes de correr el batch completo de ~621 nombres, conviene una corrida real chica de prueba (`--dry-run` con muy pocos leads, o revisar el log del primer lote) para confirmar que el campo `searchString` efectivamente vuelve poblado en resultados de un `searchStringsArray` con más de un elemento — es el único supuesto de este plan tomado de la documentación del actor y no de una llamada real de prueba.
