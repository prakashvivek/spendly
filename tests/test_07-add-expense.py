"""
Tests for Step 7 -- Add Expense.

Spec: .claude/specs/07-add-expense.md

`GET/POST /expenses/add` is a logged-in-only route. GET renders a form
(amount, category, date, description); POST validates the submission,
inserts it via `database/queries.py::insert_expense`, and redirects to
`/profile`. On any validation error the form is re-rendered with an error
message and the previously submitted values pre-filled.

These tests are derived strictly from the spec's stated routes,
validation rules, database changes, and "Tests to write" / "Definition of
done" sections -- not from reading `add_expense()`'s implementation.

Written independently of `tests/test_add_expense.py` (the implementation-time
test file) so this file can act as an independent check against the spec.
"""

import re
from datetime import date

from werkzeug.security import generate_password_hash

from database import create_user, get_db, insert_expense

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

LOGIN_EMAIL = "nitish@example.com"
LOGIN_PASSWORD = "password123"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _login(client):
    return client.post(
        "/login",
        data={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
    )


def _session_user_id(client):
    with client.session_transaction() as sess:
        return sess["user_id"]


def _expense_count(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _latest_expense(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _input_tag(html, name):
    """Return the full opening <input ...> tag markup for the given
    `name` attribute, regardless of attribute ordering.
    """
    match = re.search(rf'<input[^>]*name="{name}"[^>]*>', html)
    assert match, f'No <input name="{name}"> found in response body'
    return match.group(0)


def _attr(tag, attr_name):
    match = re.search(rf'{attr_name}="([^"]*)"', tag)
    return match.group(1) if match else None


VALID_EXPENSE_DATA = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


# ------------------------------------------------------------------ #
# Unit tests: database/queries.py::insert_expense                    #
# ------------------------------------------------------------------ #

def test_insert_expense_valid_data_row_is_queryable(temp_db):
    user_id = create_user(
        "Unit Test User", "unit-insert@example.com", generate_password_hash("password123")
    )

    insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None, "Expected insert_expense to create a queryable row"
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"
    assert row["description"] == "Lunch"


def test_insert_expense_none_description_stores_null(temp_db):
    user_id = create_user(
        "Unit Test User 2", "unit-insert-null@example.com", generate_password_hash("password123")
    )

    insert_expense(user_id, 20.0, "Transport", "2026-01-01", None)

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["description"] is None, "description=None must be stored as NULL"


# ------------------------------------------------------------------ #
# GET /expenses/add                                                   #
# ------------------------------------------------------------------ #

def test_get_add_expense_unauthenticated_redirects_to_login(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_get_add_expense_authenticated_returns_200(client):
    _login(client)
    response = client.get("/expenses/add")
    assert response.status_code == 200


def test_get_add_expense_category_select_has_all_seven_categories(client):
    _login(client)
    response = client.get("/expenses/add")
    html = response.data.decode()

    assert "<select" in html, "Expected a <select> element for category"
    for category in CATEGORIES:
        assert category in html, f"Expected category option '{category}' in form"


def test_get_add_expense_form_uses_post_method(client):
    _login(client)
    response = client.get("/expenses/add")
    html = response.data.decode().lower()

    assert "<form" in html
    assert 'method="post"' in html


def test_get_add_expense_date_field_defaults_to_today(client):
    _login(client)
    response = client.get("/expenses/add")
    html = response.data.decode()

    date_tag = _input_tag(html, "date")
    assert _attr(date_tag, "value") == date.today().isoformat(), (
        "Expected the date input to default to today's date"
    )


def test_get_add_expense_amount_field_has_correct_attributes(client):
    _login(client)
    response = client.get("/expenses/add")
    html = response.data.decode()

    amount_tag = _input_tag(html, "amount")
    assert _attr(amount_tag, "type") == "number"
    assert _attr(amount_tag, "step") == "0.01"
    assert _attr(amount_tag, "min") == "0.01"
    assert "required" in amount_tag


def test_get_add_expense_description_field_is_optional_with_maxlength_200(client):
    _login(client)
    response = client.get("/expenses/add")
    html = response.data.decode()

    description_tag = _input_tag(html, "description")
    assert _attr(description_tag, "maxlength") == "200"
    assert "required" not in description_tag


def test_get_add_expense_shows_save_button_and_cancel_link_to_profile(client):
    _login(client)
    response = client.get("/expenses/add")

    assert b"Save Expense" in response.data
    assert b'href="/profile"' in response.data


# ------------------------------------------------------------------ #
# POST /expenses/add -- auth guard                                    #
# ------------------------------------------------------------------ #

def test_post_add_expense_unauthenticated_redirects_to_login(client):
    response = client.post("/expenses/add", data=VALID_EXPENSE_DATA)
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_post_add_expense_unauthenticated_does_not_insert_row(client):
    conn = get_db()
    try:
        before = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()

    client.post("/expenses/add", data=VALID_EXPENSE_DATA)

    conn = get_db()
    try:
        after = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()

    assert after == before, "Unauthenticated POST must not write to the database"


# ------------------------------------------------------------------ #
# POST /expenses/add -- happy path                                    #
# ------------------------------------------------------------------ #

def test_post_add_expense_valid_data_redirects_to_profile(client):
    _login(client)
    response = client.post("/expenses/add", data=VALID_EXPENSE_DATA)
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_post_add_expense_valid_data_creates_row_in_db(client):
    _login(client)
    user_id = _session_user_id(client)

    client.post("/expenses/add", data=VALID_EXPENSE_DATA)

    row = _latest_expense(user_id)
    assert row is not None
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"
    assert row["description"] == "Lunch"


# ------------------------------------------------------------------ #
# POST /expenses/add -- validation errors                             #
# ------------------------------------------------------------------ #

def test_post_add_expense_missing_amount_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA)
    del data["amount"]

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower(), "Expected an error message in the response"


def test_post_add_expense_zero_amount_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, amount="0")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_post_add_expense_non_numeric_amount_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, amount="not-a-number")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_post_add_expense_negative_amount_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, amount="-10")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower(), (
        "amount must be a positive number greater than 0"
    )


def test_post_add_expense_infinite_amount_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, amount="inf")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower(), (
        "amount must be a finite positive number"
    )


def test_post_add_expense_nan_amount_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, amount="nan")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower(), (
        "amount must be a finite positive number"
    )


def test_post_add_expense_invalid_category_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, category="NotARealCategory")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_post_add_expense_invalid_date_rerenders_with_error(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, date="not-a-date")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_post_add_expense_validation_error_retains_previous_values(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA, amount="0", description="Keep me on error")

    response = client.post("/expenses/add", data=data)
    html = response.data.decode()

    assert response.status_code == 200
    assert "Food" in html, "Previously chosen category should be pre-filled"
    assert "2026-03-20" in html, "Previously entered date should be pre-filled"
    assert "Keep me on error" in html, "Previously entered description should be pre-filled"


def test_post_add_expense_invalid_data_does_not_insert_row(client):
    _login(client)
    user_id = _session_user_id(client)
    before = _expense_count(user_id)

    client.post(
        "/expenses/add",
        data=dict(VALID_EXPENSE_DATA, amount="not-a-number"),
    )

    after = _expense_count(user_id)
    assert after == before, "A failed validation must not write a row to the database"


# ------------------------------------------------------------------ #
# POST /expenses/add -- optional description                          #
# ------------------------------------------------------------------ #

def test_post_add_expense_no_description_redirects_to_profile(client):
    _login(client)
    data = dict(VALID_EXPENSE_DATA)
    del data["description"]

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_post_add_expense_no_description_saves_null_in_db(client):
    _login(client)
    user_id = _session_user_id(client)
    data = dict(VALID_EXPENSE_DATA)
    del data["description"]

    client.post("/expenses/add", data=data)

    row = _latest_expense(user_id)
    assert row is not None
    assert row["description"] is None


def test_post_add_expense_whitespace_only_description_saves_null_in_db(client):
    _login(client)
    user_id = _session_user_id(client)
    data = dict(VALID_EXPENSE_DATA, description="   ")

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 302, "Whitespace-only description is still optional/valid"
    row = _latest_expense(user_id)
    assert row is not None
    assert row["description"] is None, "Blank/whitespace description must be stored as NULL"


def test_post_add_expense_long_description_truncated_to_200_chars(client):
    _login(client)
    user_id = _session_user_id(client)
    data = dict(VALID_EXPENSE_DATA, description="x" * 500)

    response = client.post("/expenses/add", data=data)

    assert response.status_code == 302
    row = _latest_expense(user_id)
    assert row is not None
    assert len(row["description"]) == 200, (
        "description must be capped at 200 chars server-side, even if the "
        "client bypasses the HTML maxlength attribute"
    )


# ------------------------------------------------------------------ #
# Template changes: profile "Add Expense" button + navbar link        #
# ------------------------------------------------------------------ #

def test_profile_page_has_add_expense_button(client):
    _login(client)
    response = client.get("/profile")

    assert b'href="/expenses/add"' in response.data
    assert b"Add Expense" in response.data


def test_navbar_shows_add_expense_link_when_logged_in(client):
    _login(client)
    # /expenses/add itself has no separate "Add Expense" button (it *is* the
    # form page), so a link to it here can only come from the navbar.
    response = client.get("/expenses/add")

    assert response.status_code == 200
    assert b'href="/expenses/add"' in response.data


def test_navbar_hides_add_expense_link_when_logged_out(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b'href="/expenses/add"' not in response.data, (
        "Add Expense navbar link must only render when session.user_id is set"
    )
