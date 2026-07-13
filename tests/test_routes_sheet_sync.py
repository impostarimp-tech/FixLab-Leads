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
