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


class _FakeCreds:
    def __init__(self, valid=True):
        self.valid = valid
        self.expired = False
        self.refresh_token = None


def test_get_sheets_client_uses_service_account_when_env_var_set(monkeypatch):
    fake_creds = _FakeCreds()
    mock_from_info = MagicMock(return_value=fake_creds)
    monkeypatch.setattr(sync.service_account.Credentials, "from_service_account_info", mock_from_info)
    mock_authorize = MagicMock(return_value="fake_client")
    monkeypatch.setattr(sync.gspread, "authorize", mock_authorize)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account", "project_id": "test"}')

    client = sync.get_sheets_client()

    mock_from_info.assert_called_once_with({"type": "service_account", "project_id": "test"}, scopes=sync.SCOPES)
    mock_authorize.assert_called_once_with(fake_creds)
    assert client == "fake_client"


def test_get_sheets_client_uses_oauth_token_json_when_set(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    fake_creds = _FakeCreds(valid=True)
    fake_creds.expired = False
    mock_from_info = MagicMock(return_value=fake_creds)
    monkeypatch.setattr(sync.UserCredentials, "from_authorized_user_info", mock_from_info)
    mock_authorize = MagicMock(return_value="fake_client_from_token")
    monkeypatch.setattr(sync.gspread, "authorize", mock_authorize)
    token_json = '{"token": "abc", "refresh_token": "xyz", "client_id": "id", "client_secret": "secret"}'
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_JSON", token_json)

    client = sync.get_sheets_client()

    mock_from_info.assert_called_once_with(
        {"token": "abc", "refresh_token": "xyz", "client_id": "id", "client_secret": "secret"},
        scopes=sync.SCOPES,
    )
    mock_authorize.assert_called_once_with(fake_creds)
    assert client == "fake_client_from_token"


def test_get_sheets_client_refreshes_expired_oauth_token_json(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    fake_creds = _FakeCreds(valid=False)
    fake_creds.expired = True
    fake_creds.refresh_token = "some-refresh-token"
    fake_creds.refresh = MagicMock()
    monkeypatch.setattr(sync.UserCredentials, "from_authorized_user_info", MagicMock(return_value=fake_creds))
    monkeypatch.setattr(sync.gspread, "authorize", MagicMock(return_value="fake_client"))
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_JSON", '{"token": "abc"}')

    sync.get_sheets_client()

    fake_creds.refresh.assert_called_once()


def test_get_sheets_client_falls_back_to_oauth_flow_without_service_account_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_TOKEN_JSON", raising=False)
    monkeypatch.setattr(sync, "TOKEN_FILE", str(tmp_path / "nonexistent_token.pickle"))
    fake_creds = _FakeCreds(valid=True)
    mock_flow = MagicMock()
    mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = fake_creds
    monkeypatch.setattr(sync, "InstalledAppFlow", mock_flow)
    monkeypatch.setattr(sync.gspread, "authorize", MagicMock(return_value="fake_client_oauth"))

    client = sync.get_sheets_client()

    assert client == "fake_client_oauth"


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


def test_sync_all_tabs_skips_rows_already_cached_by_place_id(tmp_path, monkeypatch):
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
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

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


def test_sync_all_tabs_stores_telefono_for_new_leads(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA",
             "Telefono": "11-5555-1234"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    sync.sync_all_tabs(conn, client)

    row = conn.execute("SELECT telefono FROM leads_cache WHERE place_id = 'PA'").fetchone()
    assert row["telefono"] == "11-5555-1234"


def test_sync_all_tabs_stores_reviews_count_and_rating_for_new_leads(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA",
             "Reseñas": 42, "Rating": 4.5},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    sync.sync_all_tabs(conn, client)

    row = conn.execute("SELECT reviews_count, rating FROM leads_cache WHERE place_id = 'PA'").fetchone()
    assert row["reviews_count"] == 42
    assert row["rating"] == 4.5


def test_sync_all_tabs_refreshes_reviews_count_and_rating_for_existing_lead(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = db.upsert_lead(conn, "PA", "Repuestos", "Taller A", "Dir A", "", reviews_count=10, rating=3.0)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA",
             "Reseñas": 25, "Rating": 4.8},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)

    sync.sync_all_tabs(conn, client)

    row = conn.execute(
        "SELECT reviews_count, rating FROM leads_cache WHERE id = ?", (lead_id,)
    ).fetchone()
    assert row["reviews_count"] == 25
    assert row["rating"] == 4.8


def test_sync_all_tabs_handles_missing_reviews_and_rating(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    sync.sync_all_tabs(conn, client)

    row = conn.execute("SELECT reviews_count, rating FROM leads_cache WHERE place_id = 'PA'").fetchone()
    assert row["reviews_count"] is None
    assert row["rating"] is None


def test_sync_all_tabs_handles_telefono_returned_as_int_by_gspread(tmp_path, monkeypatch):
    # gspread's get_all_records() auto-types numeric-looking cells (e.g. a phone
    # number with no leading zero/dash) as int rather than str.
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA",
             "Telefono": 1155551234},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    sync.sync_all_tabs(conn, client)

    row = conn.execute("SELECT telefono FROM leads_cache WHERE place_id = 'PA'").fetchone()
    assert row["telefono"] == "1155551234"


def test_sync_all_tabs_backfills_telefono_for_already_cached_lead(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    db.upsert_lead(conn, "PA", "Repuestos", "Taller A", "Dir A", "")  # no telefono yet

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA",
             "Telefono": "11-4444-5678"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)

    summary = sync.sync_all_tabs(conn, client)

    assert summary["nuevos"] == 0
    row = conn.execute("SELECT telefono FROM leads_cache WHERE place_id = 'PA'").fetchone()
    assert row["telefono"] == "11-4444-5678"


def test_sync_all_tabs_does_not_overwrite_existing_telefono(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    lead_id = db.upsert_lead(conn, "PA", "Repuestos", "Taller A", "Dir A", "")
    db.set_telefono(conn, lead_id, "11-0000-0000")

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA",
             "Telefono": "11-9999-9999"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)

    sync.sync_all_tabs(conn, client)

    row = conn.execute("SELECT telefono FROM leads_cache WHERE place_id = 'PA'").fetchone()
    assert row["telefono"] == "11-0000-0000"


def test_row_place_id_falls_back_to_name_and_address_when_missing():
    row = {"Negocio": "Taller Z", "Direccion": "Calle 123", "Place_ID": ""}
    key = sync._row_place_id(row, "Repuestos")
    assert key == "NOID:Repuestos:taller z|calle 123"


def test_sync_all_tabs_progress_yields_log_and_progress_events(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)

    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA"},
            {"Negocio": "Taller B", "Direccion": "Dir B", "Maps_URL": "", "Place_ID": "PB"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    events = list(sync.sync_all_tabs_progress(conn, client))

    log_events = [e for e in events if e["type"] == "log"]
    progress_events = [e for e in events if e["type"] == "progress"]
    done_events = [e for e in events if e["type"] == "done"]

    assert any("Repuestos" in e["msg"] or "repuestos" in e["msg"].lower() for e in log_events)
    assert [e["actual"] for e in progress_events] == [1, 2]
    assert all(e["total"] == 2 for e in progress_events)
    assert len(done_events) == 1
    assert done_events[0]["summary"] == {"nuevos": 2, "geocodificados": 2, "fallidos": 0}


def test_sync_all_tabs_progress_skips_geocode_log_when_nothing_pending(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)

    events = list(sync.sync_all_tabs_progress(conn, client))

    assert not any("pendientes" in e.get("msg", "") for e in events)
    assert events[-1] == {"type": "done", "summary": {"nuevos": 0, "geocodificados": 0, "fallidos": 0}}


def test_sync_all_tabs_wrapper_still_returns_final_summary(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.get_connection(db_path)
    tabs_data = {
        sync.CATEGORIA_TABS["Repuestos"]: [
            {"Negocio": "Taller A", "Direccion": "Dir A", "Maps_URL": "", "Place_ID": "PA"},
        ],
        sync.CATEGORIA_TABS["Fundas"]: [],
        sync.CATEGORIA_TABS["Telefonos"]: [],
    }
    client = _fake_client(tabs_data)
    monkeypatch.setattr(sync.geocoding, "geocode_lead", lambda **kwargs: ((-34.6, -58.4), "direccion"))

    summary = sync.sync_all_tabs(conn, client)

    assert summary == {"nuevos": 1, "geocodificados": 1, "fallidos": 0}
