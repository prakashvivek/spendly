INVALID_CREDENTIALS_ERROR = "Invalid email or password."


def test_login_success_redirects_to_profile_and_sets_session(client):
    response = client.post(
        "/login",
        data={"email": "nitish@example.com", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"

    with client.session_transaction() as sess:
        assert sess["user_id"] is not None


def test_login_wrong_password_shows_generic_error_no_session(client):
    response = client.post(
        "/login",
        data={"email": "nitish@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 200
    assert INVALID_CREDENTIALS_ERROR.encode() in response.data

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_unknown_email_shows_same_generic_error(client):
    response = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 200
    assert INVALID_CREDENTIALS_ERROR.encode() in response.data

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_wrong_password_and_unknown_email_show_identical_error(client):
    wrong_password = client.post(
        "/login",
        data={"email": "nitish@example.com", "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "whatever"},
    )
    assert INVALID_CREDENTIALS_ERROR.encode() in wrong_password.data
    assert INVALID_CREDENTIALS_ERROR.encode() in unknown_email.data


def test_login_missing_password_field_does_not_error(client):
    response = client.post("/login", data={"email": "nitish@example.com"})
    assert response.status_code == 200
    assert INVALID_CREDENTIALS_ERROR.encode() in response.data


def test_logout_after_login_clears_session_and_redirects(client):
    client.post(
        "/login",
        data={"email": "nitish@example.com", "password": "password123"},
    )
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_when_not_logged_in_does_not_error(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_login_page_form_action_uses_url_for(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b'action="/login"' in response.data


def test_login_page_redirects_to_profile_when_already_logged_in(client):
    client.post(
        "/login",
        data={"email": "nitish@example.com", "password": "password123"},
    )
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
