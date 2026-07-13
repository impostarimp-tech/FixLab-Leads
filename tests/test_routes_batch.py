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
