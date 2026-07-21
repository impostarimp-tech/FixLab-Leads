import flask
import pytest

import routes_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    routes_app.db.init_db(db_path)
    monkeypatch.setattr(routes_app.db, "DB_PATH", db_path)
    test_app = flask.Flask(__name__)
    test_app.register_blueprint(routes_app.rutas_bp)
    return test_app.test_client()


def test_crm_accessible_without_password_when_env_var_unset(client, monkeypatch):
    monkeypatch.delenv("CRM_PASSWORD", raising=False)
    resp = client.get("/rutas/crm")
    assert resp.status_code == 200


def test_crm_requires_auth_when_password_configured(client, monkeypatch):
    monkeypatch.setenv("CRM_PASSWORD", "secreto123")
    resp = client.get("/rutas/crm")
    assert resp.status_code == 401


def test_crm_rejects_wrong_password(client, monkeypatch):
    monkeypatch.setenv("CRM_PASSWORD", "secreto123")
    resp = client.get("/rutas/crm", auth=("cualquiera", "incorrecta"))
    assert resp.status_code == 401


def test_crm_accepts_correct_password(client, monkeypatch):
    monkeypatch.setenv("CRM_PASSWORD", "secreto123")
    resp = client.get("/rutas/crm", auth=("cualquiera", "secreto123"))
    assert resp.status_code == 200
