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


def test_generate_lote_visits_each_business_once_even_if_listed_in_two_categories(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    # 3 distinct businesses, but one of them ("Negocio 1") is listed under both
    # Repuestos and Fundas at the same address -- a real pattern in the Sheet.
    lead_ids = []
    for i in range(3):
        lead_id = db.upsert_lead(conn, f"P{i}", "Repuestos", f"Negocio {i}", f"Dir {i}", "")
        db.set_geocode_result(conn, lead_id, -34.60, -58.40 + i * 0.001, "direccion")
        lead_ids.append(lead_id)
    dup_id = db.upsert_lead(conn, "P1-fundas", "Fundas", "Negocio 1", "Dir 1", "")
    db.set_geocode_result(conn, dup_id, -34.60, -58.401, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.60, -58.4005)):
        result = batch.generate_lote(conn, origen_texto="Local FixLab", n=3)

    # requesting 3 gives 3 distinct physical stops, not 3 minus the duplicate
    assert result["tamano_real"] == 3
    stops = [lead for s in result["sublotes"] for lead in s["leads"]]
    assert len(stops) == 3

    all_lead_ids = [lead_id for stop in stops for lead_id in stop["lead_ids"]]
    assert sorted(all_lead_ids) == sorted(lead_ids + [dup_id])

    negocio_1_stop = next(stop for stop in stops if stop["negocio"] == "Negocio 1")
    assert sorted(negocio_1_stop["lead_ids"]) == sorted([lead_ids[1], dup_id])
    assert negocio_1_stop["categorias"] == ["Fundas", "Repuestos"]


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


def test_generate_lote_raises_for_non_positive_n(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.60, -58.401)):
        for invalid_n in (0, -1):
            try:
                batch.generate_lote(conn, origen_texto="Local FixLab", n=invalid_n)
                assert False, f"expected ValueError for n={invalid_n}"
            except ValueError:
                pass


def test_generate_lote_skips_geocoding_when_origen_coords_given(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Unico", "Dir", "")
    db.set_geocode_result(conn, lead_id, -34.60, -58.40, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text") as mock_geocode:
        result = batch.generate_lote(
            conn, origen_texto="Local FixLab (guardado)", n=1, origen_coords=(-34.60, -58.401)
        )

    mock_geocode.assert_not_called()
    assert result["tamano_real"] == 1
    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (result["lote_id"],)).fetchone()
    assert (lote["origen_lat"], lote["origen_lng"]) == (-34.60, -58.401)


def test_generate_lote_uses_matching_lead_coords_instead_of_geocoding(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    origin_lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller Apple Fix", "Dir Origen", "")
    db.set_geocode_result(conn, origin_lead_id, -34.60, -58.40, "direccion")
    candidate_id = db.upsert_lead(conn, "P2", "Repuestos", "Candidato", "Dir", "")
    db.set_geocode_result(conn, candidate_id, -34.601, -58.401, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text") as mock_geocode:
        result = batch.generate_lote(conn, origen_texto="taller APPLE fix", n=5)

    mock_geocode.assert_not_called()
    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (result["lote_id"],)).fetchone()
    assert (lote["origen_lat"], lote["origen_lng"]) == (-34.60, -58.40)


def test_generate_lote_falls_back_to_geocoding_when_no_lead_matches(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = db.upsert_lead(conn, "P1", "Repuestos", "Unico", "Dir", "")
    db.set_geocode_result(conn, lead_id, -34.60, -58.40, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.62, -58.42)) as mock_geocode:
        result = batch.generate_lote(conn, origen_texto="Av. Rivadavia 100", n=5)

    mock_geocode.assert_called_once_with("Av. Rivadavia 100")
    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (result["lote_id"],)).fetchone()
    assert (lote["origen_lat"], lote["origen_lng"]) == (-34.62, -58.42)


def test_generate_lote_excludes_leads_outside_the_default_search_radius(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    nearby_id = db.upsert_lead(conn, "P1", "Repuestos", "Cerca", "Dir A", "")
    db.set_geocode_result(conn, nearby_id, -34.60, -58.401, "direccion")
    faraway_id = db.upsert_lead(conn, "P2", "Repuestos", "Lejos", "Dir B", "")
    db.set_geocode_result(conn, faraway_id, -31.4, -64.2, "direccion")  # Cordoba

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.60, -58.40)):
        result = batch.generate_lote(conn, origen_texto="Local FixLab", n=10)

    all_ids = [lid for s in result["sublotes"] for lead in s["leads"] for lid in lead["lead_ids"]]
    assert nearby_id in all_ids
    assert faraway_id not in all_ids


def test_generate_lote_restricts_pool_to_given_categoria(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    repuestos_id = db.upsert_lead(conn, "P1", "Repuestos", "Taller Repuestos", "Dir", "")
    db.set_geocode_result(conn, repuestos_id, -34.60, -58.401, "direccion")
    fundas_id = db.upsert_lead(conn, "P2", "Fundas", "Taller Fundas", "Dir", "")
    db.set_geocode_result(conn, fundas_id, -34.60, -58.402, "direccion")

    with patch("routes_batch.geocoding.geocode_free_text", return_value=(-34.60, -58.40)):
        result = batch.generate_lote(conn, origen_texto="Local FixLab", n=10, categoria="Fundas")

    assert result["categoria"] == "Fundas"
    assert result["tamano_real"] == 1
    assert result["sublotes"][0]["leads"][0]["id"] == fundas_id
    lote = conn.execute("SELECT * FROM lotes WHERE id = ?", (result["lote_id"],)).fetchone()
    assert lote["categoria"] == "Fundas"


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
