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
    sublote_id = db.create_sublote(conn, lote_id, 1, "https://maps.example", [lead_a])
    db.mark_sublote_compartido(conn, sublote_id)

    leads = db.get_all_geocoded_leads(conn)
    assert [lead["id"] for lead in leads] == [lead_a]


def test_get_lote_route_points_returns_origin_then_chained_leads_in_order(conn):
    lead_a = db.upsert_lead(conn, "P1", "Repuestos", "A", "Dir A", "")
    db.set_geocode_result(conn, lead_a, -34.61, -58.41, "direccion")
    lead_b = db.upsert_lead(conn, "P2", "Repuestos", "B", "Dir B", "")
    db.set_geocode_result(conn, lead_b, -34.62, -58.42, "direccion")

    lote_id = db.create_lote(conn, -34.60, -58.40, "Mi Origen", 2, 2)
    db.create_sublote(conn, lote_id, 1, "https://maps.example/1", [lead_a])
    db.create_sublote(conn, lote_id, 2, "https://maps.example/2", [lead_b])

    points = db.get_lote_route_points(conn, lote_id)

    assert points == [
        {"lat": -34.60, "lng": -58.40, "negocio": "Origen"},
        {"lat": -34.61, "lng": -58.41, "negocio": "A"},
        {"lat": -34.62, "lng": -58.42, "negocio": "B"},
    ]


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
