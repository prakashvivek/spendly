import pytest

from app import app as flask_app
from database import db as db_module


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()


@pytest.fixture
def client(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client


def _user_count(email=None):
    conn = db_module.get_db()
    try:
        if email is None:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", (email,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_get_register_still_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200


def test_post_register_success_redirects_to_login(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_post_register_success_creates_row(client):
    client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )

    conn = db_module.get_db()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", ("nitish@example.com",)
        ).fetchone()
    finally:
        conn.close()

    assert user is not None
    assert user["password_hash"] != "password123"


def test_post_register_missing_name_rerenders_with_error(client):
    response = client.post(
        "/register",
        data={"name": "", "email": "nitish@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert b"Name and email are required." in response.data
    assert _user_count() == 0


def test_post_register_missing_email_rerenders_with_error(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "", "password": "password123"},
    )
    assert response.status_code == 200
    assert b"Name and email are required." in response.data
    assert _user_count() == 0


def test_post_register_short_password_rerenders_with_error(client):
    response = client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "short"},
    )
    assert response.status_code == 200
    assert b"Password must be at least 8 characters." in response.data
    assert _user_count() == 0


def test_post_register_duplicate_email_rerenders_with_error(client):
    client.post(
        "/register",
        data={"name": "Nitish Kumar", "email": "nitish@example.com", "password": "password123"},
    )

    response = client.post(
        "/register",
        data={"name": "Someone Else", "email": "nitish@example.com", "password": "password456"},
    )

    assert response.status_code == 200
    assert b"An account with that email already exists." in response.data
    assert _user_count("nitish@example.com") == 1
