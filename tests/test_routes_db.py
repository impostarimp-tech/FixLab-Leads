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


def test_get_pending_geocode_sorts_pendiente_before_fallido(conn):
    failed_id = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, failed_id, None, None, "fallido")
    pending_id = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")

    ordered_ids = [row["id"] for row in db.get_pending_geocode(conn)]
    assert ordered_ids == [pending_id, failed_id]


def test_find_lead_by_name_matches_case_insensitively(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller Apple Fix", "Dir A", "")
    db.set_geocode_result(conn, lead_id, -34.6, -58.4, "direccion")

    found = db.find_lead_by_name(conn, "taller APPLE fix")

    assert found["id"] == lead_id


def test_find_lead_by_name_returns_none_when_not_geocoded(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "Taller Pendiente", "Dir A", "")

    assert db.find_lead_by_name(conn, "Taller Pendiente") is None


def test_find_lead_by_name_returns_none_when_no_match(conn):
    assert db.find_lead_by_name(conn, "No existe") is None


def test_get_candidate_pool_excludes_recently_shared(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_geocode_result(conn, lead_b, -34.61, -58.41, "direccion")

    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 2, 2)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a]])
    db.mark_sublote_compartido(conn, sublote_id)

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn)}
    assert lead_a not in pool_ids
    assert lead_b in pool_ids


def test_get_candidate_pool_includes_leads_shared_over_30_days_ago(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")

    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 1, 1)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a]])
    old_date = (datetime.utcnow() - timedelta(days=45)).isoformat()
    conn.execute("UPDATE sublotes SET compartido_en = ? WHERE id = ?", (old_date, sublote_id))
    conn.commit()

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn)}
    assert lead_a in pool_ids


def test_get_candidate_pool_filters_by_categoria(conn):
    repuestos_id = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, repuestos_id, -34.6, -58.4, "direccion")
    fundas_id = db.upsert_lead(conn, "P2", "Fundas", "B", "Dir B", "")
    db.set_geocode_result(conn, fundas_id, -34.61, -58.41, "direccion")

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn, categoria="Fundas")}

    assert pool_ids == {fundas_id}


def test_get_candidate_pool_filters_by_min_reviews(conn):
    low = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "", reviews_count=5)
    db.set_geocode_result(conn, low, -34.6, -58.4, "direccion")
    high = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "", reviews_count=50)
    db.set_geocode_result(conn, high, -34.61, -58.41, "direccion")

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn, min_reviews=20)}

    assert pool_ids == {high}


def test_get_candidate_pool_filters_by_min_rating(conn):
    low = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "", rating=3.0)
    db.set_geocode_result(conn, low, -34.6, -58.4, "direccion")
    high = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "", rating=4.8)
    db.set_geocode_result(conn, high, -34.61, -58.41, "direccion")

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn, min_rating=4.0)}

    assert pool_ids == {high}


def test_get_candidate_pool_excludes_null_reviews_when_min_reviews_given(conn):
    no_reviews = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, no_reviews, -34.6, -58.4, "direccion")

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn, min_reviews=1)}

    assert pool_ids == set()


def test_get_candidate_pool_applies_radius_filter_around_origin(conn):
    origin = (-34.60, -58.40)
    nearby = db.upsert_lead(conn, "P1", "Repuestos", "Cerca", "Dir A", "")
    db.set_geocode_result(conn, nearby, -34.61, -58.41, "direccion")  # ~1.5km away
    faraway = db.upsert_lead(conn, "P2", "Repuestos", "Lejos", "Dir B", "")
    db.set_geocode_result(conn, faraway, -31.4, -64.2, "direccion")  # Cordoba, ~650km away

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn, origin=origin, max_radius_km=60)}

    assert pool_ids == {nearby}


def test_get_candidate_pool_radius_filter_is_a_noop_without_origin(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_id, -31.4, -64.2, "direccion")  # Cordoba, far from AMBA

    # no origin given -> default max_radius_km is ignored, nothing is filtered out
    pool_ids = {row["id"] for row in db.get_candidate_pool(conn)}

    assert pool_ids == {lead_id}


def test_get_candidate_pool_max_radius_km_none_disables_filter_even_with_origin(conn):
    origin = (-34.60, -58.40)
    faraway = db.upsert_lead(conn, "P1", "Repuestos", "Lejos", "Dir B", "")
    db.set_geocode_result(conn, faraway, -31.4, -64.2, "direccion")

    pool_ids = {row["id"] for row in db.get_candidate_pool(conn, origin=origin, max_radius_km=None)}

    assert pool_ids == {faraway}


def test_get_candidate_pool_merges_same_business_across_categories(conn):
    repuestos_id = db.upsert_lead(
        conn, "P1", "Repuestos", "Mismo Negocio", "Dir X", "", reviews_count=10, rating=4.0
    )
    db.set_geocode_result(conn, repuestos_id, -34.6, -58.4, "direccion")
    fundas_id = db.upsert_lead(
        conn, "P2", "Fundas", "mismo negocio", "Dir X", "", reviews_count=50, rating=4.8
    )
    db.set_geocode_result(conn, fundas_id, -34.6, -58.4, "direccion")

    pool = db.get_candidate_pool(conn)

    assert len(pool) == 1
    stop = pool[0]
    assert sorted(stop["lead_ids"]) == sorted([repuestos_id, fundas_id])
    assert stop["categorias"] == ["Fundas", "Repuestos"]
    # representative fields come from the row with more reviews (Fundas)
    assert stop["reviews_count"] == 50
    assert stop["rating"] == 4.8


def test_get_candidate_pool_does_not_merge_different_businesses(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "Negocio A", "Dir A", "")
    db.set_geocode_result(conn, a, -34.6, -58.4, "direccion")
    b = db.upsert_lead(conn, "P2", "Fundas", "Negocio B", "Dir B", "")
    db.set_geocode_result(conn, b, -34.6, -58.4, "direccion")  # same coords, different business

    pool = db.get_candidate_pool(conn)

    assert len(pool) == 2


def test_create_lote_stores_categoria(conn):
    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 10, 5, categoria="Telefonos")
    lote = db.get_lote(conn, lote_id)
    assert lote["categoria"] == "Telefonos"


def test_create_lote_categoria_defaults_to_none(conn):
    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 10, 5)
    lote = db.get_lote(conn, lote_id)
    assert lote["categoria"] is None


def test_get_lote_returns_none_for_unknown_id(conn):
    assert db.get_lote(conn, 999) is None


def test_get_sublote_stops_returns_ordered_stops(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.61, -58.41, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_geocode_result(conn, lead_b, -34.62, -58.42, "direccion")

    lote_id = db.create_lote(conn, -34.60, -58.40, "Origen", 2, 2)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a], [lead_b]])

    stops = db.get_sublote_stops(conn, sublote_id)

    assert [stop["negocio"] for stop in stops] == ["A", "B"]


def test_get_sublote_stops_merges_grouped_lead_ids_into_one_stop(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "Mismo Negocio", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.61, -58.41, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Fundas", "Mismo Negocio", "Dir A", "")
    db.set_geocode_result(conn, lead_b, -34.61, -58.41, "direccion")

    lote_id = db.create_lote(conn, -34.60, -58.40, "Origen", 1, 1)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a, lead_b]])

    stops = db.get_sublote_stops(conn, sublote_id)

    assert len(stops) == 1
    assert sorted(stops[0]["lead_ids"]) == sorted([lead_a, lead_b])
    assert stops[0]["categorias"] == ["Fundas", "Repuestos"]


def test_create_lote_and_sublote_persist_relationships(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")

    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 1, 1)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a]])

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
    db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a]])

    db.mark_lote_compartido(conn, lote_id)

    sublote = db.get_sublotes_for_lote(conn, lote_id)[0]
    assert sublote["compartido_en"] is not None


def test_get_all_geocoded_leads_excludes_fallido_and_ungeocoded(conn):
    ok_id = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, ok_id, -34.6, -58.4, "direccion")
    fallido_id = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_geocode_result(conn, fallido_id, None, None, "fallido")
    db.upsert_lead(conn, "P3", "Repuestos", "C", "Dir C", "")  # still pendiente, no lat

    leads = db.get_all_geocoded_leads(conn)
    assert [lead["id"] for lead in leads] == [ok_id]


def test_get_all_geocoded_leads_includes_recently_shared_leads(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.6, -58.4, "direccion")
    lote_id = db.create_lote(conn, -34.6, -58.4, "Origen", 1, 1)
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a]])
    db.mark_sublote_compartido(conn, sublote_id)

    leads = db.get_all_geocoded_leads(conn)
    assert [lead["id"] for lead in leads] == [lead_a]


def test_get_lote_route_points_returns_origin_then_chained_leads_in_order(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.61, -58.41, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_geocode_result(conn, lead_b, -34.62, -58.42, "direccion")

    lote_id = db.create_lote(conn, -34.60, -58.40, "Mi Origen", 2, 2)
    db.create_sublote(conn, lote_id, 1, "https://maps.example/1", [[lead_a]])
    db.create_sublote(conn, lote_id, 2, "https://maps.example/2", [[lead_b]])

    points = db.get_lote_route_points(conn, lote_id)

    assert points == [
        {"id": None, "lat": -34.60, "lng": -58.40, "negocio": "Origen"},
        {"id": lead_a, "lead_ids": [lead_a], "lat": -34.61, "lng": -58.41, "negocio": "A",
         "categorias": ["Repuestos"], "direccion": "Dir A", "telefono": "",
         "outreach_status": "sin_contactar", "reviews_count": None, "rating": None},
        {"id": lead_b, "lead_ids": [lead_b], "lat": -34.62, "lng": -58.42, "negocio": "B",
         "categorias": ["Repuestos"], "direccion": "Dir B", "telefono": "",
         "outreach_status": "sin_contactar", "reviews_count": None, "rating": None},
    ]


def test_get_lote_route_points_merges_grouped_lead_ids_into_one_point(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "Mismo Negocio", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.61, -58.41, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Fundas", "Mismo Negocio", "Dir A", "")
    db.set_geocode_result(conn, lead_b, -34.61, -58.41, "direccion")

    lote_id = db.create_lote(conn, -34.60, -58.40, "Origen", 1, 1)
    db.create_sublote(conn, lote_id, 1, "https://maps.example", [[lead_a, lead_b]])

    points = db.get_lote_route_points(conn, lote_id)

    assert len(points) == 2  # origin + one merged stop
    stop = points[1]
    assert sorted(stop["lead_ids"]) == sorted([lead_a, lead_b])
    assert stop["categorias"] == ["Fundas", "Repuestos"]


def test_get_lote_route_points_returns_empty_for_unknown_lote(conn):
    assert db.get_lote_route_points(conn, 999) == []


def test_get_recent_origenes_orders_by_most_recent_first(conn):
    older_id = db.create_lote(conn, -34.60, -58.40, "Origen Viejo", 1, 1)
    newer_id = db.create_lote(conn, -34.61, -58.41, "Origen Nuevo", 1, 1)
    conn.execute("UPDATE lotes SET fecha_generado = ? WHERE id = ?", ("2026-01-01T00:00:00", older_id))
    conn.execute("UPDATE lotes SET fecha_generado = ? WHERE id = ?", ("2026-06-01T00:00:00", newer_id))
    conn.commit()

    origenes = db.get_recent_origenes(conn)

    assert [o["origen_texto"] for o in origenes] == ["Origen Nuevo", "Origen Viejo"]


def test_get_recent_origenes_deduplicates_identical_origins(conn):
    db.create_lote(conn, -34.60, -58.40, "Local FixLab", 1, 1)
    db.create_lote(conn, -34.60, -58.40, "Local FixLab", 1, 1)

    origenes = db.get_recent_origenes(conn)

    assert len(origenes) == 1
    assert origenes[0]["origen_texto"] == "Local FixLab"


def test_get_recent_origenes_respects_limit(conn):
    for i in range(5):
        db.create_lote(conn, -34.60, -58.40, f"Origen {i}", 1, 1)

    origenes = db.get_recent_origenes(conn, limit=2)

    assert len(origenes) == 2


def test_upsert_lead_stores_telefono(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "", "11-5555-1234")
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["telefono"] == "11-5555-1234"


def test_upsert_lead_defaults_outreach_status_to_sin_contactar(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["outreach_status"] == "sin_contactar"


def test_set_telefono_updates_existing_lead(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    db.set_telefono(conn, lead_id, "11-4444-5678")
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["telefono"] == "11-4444-5678"


def test_upsert_lead_stores_reviews_count_and_rating(conn):
    lead_id = db.upsert_lead(
        conn, "P1", "Repuestos", "Taller X", "Dir 1", "", reviews_count=15, rating=4.2
    )
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["reviews_count"] == 15
    assert row["rating"] == 4.2


def test_upsert_lead_reviews_and_rating_default_to_none(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["reviews_count"] is None
    assert row["rating"] is None


def test_set_reviews_rating_updates_existing_lead(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    db.set_reviews_rating(conn, lead_id, 30, 4.9)
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["reviews_count"] == 30
    assert row["rating"] == 4.9


def test_set_outreach_status_updates_status(conn):
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller X", "Dir 1", "")
    db.set_outreach_status(conn, lead_id, "contactado")
    row = conn.execute("SELECT * FROM leads_cache WHERE id = ?", (lead_id,)).fetchone()
    assert row["outreach_status"] == "contactado"


def test_get_crm_leads_returns_all_leads_across_categories(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    b = db.upsert_lead(conn, "P2", "Fundas", "B", "Dir B", "")

    leads = db.get_crm_leads(conn)

    assert {lead["id"] for lead in leads} == {a, b}


def test_get_crm_leads_filters_by_categoria(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.upsert_lead(conn, "P2", "Fundas", "B", "Dir B", "")

    leads = db.get_crm_leads(conn, categoria="Repuestos")

    assert [lead["id"] for lead in leads] == [a]


def test_get_crm_leads_filters_by_outreach_status(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_outreach_status(conn, b, "contactado")

    leads = db.get_crm_leads(conn, outreach_status="contactado")

    assert [lead["id"] for lead in leads] == [b]


def test_get_crm_leads_filters_by_min_reviews_and_min_rating(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "", reviews_count=5, rating=3.5)
    b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "", reviews_count=50, rating=4.9)

    leads = db.get_crm_leads(conn, min_reviews=20, min_rating=4.5)

    assert [lead["id"] for lead in leads] == [b]


def test_get_crm_leads_paginates_with_page_size(conn):
    for i in range(5):
        db.upsert_lead(conn, f"P{i}", "Repuestos", f"Lead {i}", "Dir", "")

    page1 = db.get_crm_leads(conn, page=1, page_size=2)
    page2 = db.get_crm_leads(conn, page=2, page_size=2)
    page3 = db.get_crm_leads(conn, page=3, page_size=2)

    assert [lead["negocio"] for lead in page1] == ["Lead 0", "Lead 1"]
    assert [lead["negocio"] for lead in page2] == ["Lead 2", "Lead 3"]
    assert [lead["negocio"] for lead in page3] == ["Lead 4"]


def test_count_crm_leads_respects_filters(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.upsert_lead(conn, "P2", "Fundas", "B", "Dir B", "")

    assert db.count_crm_leads(conn) == 2
    assert db.count_crm_leads(conn, categoria="Repuestos") == 1


def test_get_crm_leads_all_ignores_pagination(conn):
    for i in range(5):
        db.upsert_lead(conn, f"P{i}", "Repuestos", f"Lead {i}", "Dir", "")

    leads = db.get_crm_leads_all(conn)

    assert len(leads) == 5


def test_get_crm_leads_all_respects_filters(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.upsert_lead(conn, "P2", "Fundas", "B", "Dir B", "")

    leads = db.get_crm_leads_all(conn, categoria="Fundas")

    assert [lead["negocio"] for lead in leads] == ["B"]


def test_get_crm_leads_filters_by_search_query_matching_negocio(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center Palermo", "Dir A", "")
    db.upsert_lead(conn, "P2", "Repuestos", "Otro Local", "Dir B", "")

    leads = db.get_crm_leads(conn, q="iphone")

    assert [lead["id"] for lead in leads] == [a]


def test_get_crm_leads_filters_by_search_query_matching_direccion_or_telefono(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "Local A", "Av. Santa Fe 3421", "", telefono="1122334455")
    b = db.upsert_lead(conn, "P2", "Repuestos", "Local B", "Otra Calle 100", "", telefono="1199998888")

    by_direccion = db.get_crm_leads(conn, q="santa fe")
    by_telefono = db.get_crm_leads(conn, q="9999")

    assert [lead["id"] for lead in by_direccion] == [a]
    assert [lead["id"] for lead in by_telefono] == [b]


def test_get_crm_leads_search_combines_with_other_filters(conn):
    a = db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center", "Dir A", "")
    db.upsert_lead(conn, "P2", "Fundas", "iPhone Fundas", "Dir B", "")

    leads = db.get_crm_leads(conn, q="iphone", categoria="Repuestos")

    assert [lead["id"] for lead in leads] == [a]


def test_get_crm_leads_search_no_match_returns_empty(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center", "Dir A", "")

    leads = db.get_crm_leads(conn, q="samsung")

    assert leads == []


def test_count_crm_leads_respects_search_query(conn):
    db.upsert_lead(conn, "P1", "Repuestos", "iPhone Center", "Dir A", "")
    db.upsert_lead(conn, "P2", "Repuestos", "Otro Local", "Dir B", "")

    assert db.count_crm_leads(conn, q="iphone") == 1


def test_migrate_adds_missing_columns_to_pre_existing_database(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    conn = db.get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE leads_cache (
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
        CREATE TABLE lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_generado TEXT NOT NULL,
            origen_lat REAL NOT NULL,
            origen_lng REAL NOT NULL,
            origen_texto TEXT NOT NULL,
            tamano_solicitado INTEGER NOT NULL,
            tamano_real INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    db.init_db(db_path)

    conn = db.get_connection(db_path)
    lead_cols = {row["name"] for row in conn.execute("PRAGMA table_info(leads_cache)")}
    lote_cols = {row["name"] for row in conn.execute("PRAGMA table_info(lotes)")}
    conn.close()
    assert {"telefono", "outreach_status"} <= lead_cols
    assert "categoria" in lote_cols
