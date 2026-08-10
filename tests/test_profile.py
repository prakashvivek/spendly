import re
from pathlib import Path


def _login(client):
    client.post(
        "/login",
        data={"email": "nitish@example.com", "password": "password123"},
    )


def test_profile_redirects_to_login_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_profile_returns_200_when_logged_in(client):
    _login(client)
    response = client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_user_name_and_email(client):
    _login(client)
    response = client.get("/profile")
    assert b"Nitish Kumar" in response.data
    assert b"nitish@example.com" in response.data


def test_profile_shows_at_least_three_stats(client):
    _login(client)
    response = client.get("/profile")
    assert b"Total spent" in response.data
    assert b"Transactions" in response.data
    assert b"Top category" in response.data


def test_profile_shows_transaction_table_with_at_least_three_rows(client):
    _login(client)
    response = client.get("/profile")
    assert b"Swiggy order" in response.data
    assert b"Uber ride to airport" in response.data
    assert b"Electricity bill" in response.data


def test_profile_shows_category_breakdown_with_at_least_three_categories(client):
    _login(client)
    response = client.get("/profile")
    assert response.data.count(b"profile-cat-row") >= 3
    assert b"Food" in response.data
    assert b"Bills" in response.data
    assert b"Travel" in response.data


def test_navbar_shows_logged_in_state_after_login(client):
    _login(client)
    response = client.get("/profile")
    assert b">Profile</a>" in response.data
    assert b"Log out" in response.data
    assert b"Get started" not in response.data


def test_navbar_shows_signed_out_state_when_logged_out(client):
    response = client.get("/")
    assert b"Sign in" in response.data
    assert b"Get started" in response.data
    assert b"Log out" not in response.data


def test_profile_html_has_no_hex_colors(client):
    content = Path("templates/profile.html").read_text(encoding="utf-8")
    assert re.search(r"#[0-9a-fA-F]{3,6}", content) is None
