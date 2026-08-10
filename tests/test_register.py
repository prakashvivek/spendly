from database import db as db_module

NAME_EMAIL_ERROR = "Name and email are required."
PASSWORD_LENGTH_ERROR = "Password must be at least 8 characters."
DUPLICATE_EMAIL_ERROR = "An account with that email already exists."


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
        data={"name": "New User", "email": "new-user@example.com", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_post_register_success_creates_row(client):
    client.post(
        "/register",
        data={"name": "New User", "email": "new-user@example.com", "password": "password123"},
    )

    conn = db_module.get_db()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", ("new-user@example.com",)
        ).fetchone()
    finally:
        conn.close()

    assert user is not None
    assert user["password_hash"] != "password123"


def test_post_register_missing_name_rerenders_with_error(client):
    before = _user_count()
    response = client.post(
        "/register",
        data={"name": "", "email": "new-user@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert NAME_EMAIL_ERROR.encode() in response.data
    assert _user_count() == before


def test_post_register_missing_email_rerenders_with_error(client):
    before = _user_count()
    response = client.post(
        "/register",
        data={"name": "New User", "email": "", "password": "password123"},
    )
    assert response.status_code == 200
    assert NAME_EMAIL_ERROR.encode() in response.data
    assert _user_count() == before


def test_post_register_short_password_rerenders_with_error(client):
    before = _user_count()
    response = client.post(
        "/register",
        data={"name": "New User", "email": "new-user@example.com", "password": "short"},
    )
    assert response.status_code == 200
    assert PASSWORD_LENGTH_ERROR.encode() in response.data
    assert _user_count() == before


def test_post_register_duplicate_email_rerenders_with_error(client):
    # nitish@example.com already exists via the seeded fixture data
    response = client.post(
        "/register",
        data={"name": "Someone Else", "email": "nitish@example.com", "password": "password456"},
    )

    assert response.status_code == 200
    assert DUPLICATE_EMAIL_ERROR.encode() in response.data
    assert _user_count("nitish@example.com") == 1


def test_register_page_form_action_uses_url_for(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b'action="/register"' in response.data
