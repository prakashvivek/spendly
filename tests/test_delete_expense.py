"""
Tests for Step 9 -- Delete Expense.

Spec: .claude/specs/09-delete-expense.md

`POST /expenses/<id>/delete` is a logged-in-only route (GET is not
accepted -- 405). It verifies the expense belongs to the requesting user
(reusing `get_expense_by_id`), deletes it via
`database/queries.py::delete_expense`, and redirects to `/profile`. If the
expense doesn't exist or belongs to another user, it returns 404 and leaves
the row untouched.

These tests are derived strictly from the spec's stated routes, ownership
rules, and "Tests to write" / "Definition of done" sections -- not from
reading `delete_expense()`'s implementation.
"""

from werkzeug.security import generate_password_hash

from database import create_user, delete_expense, get_db, insert_expense

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


def _expense_row(expense_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _other_user_expense_id():
    """Create a second user with one expense, return that expense's id."""
    other_user_id = create_user(
        "Other User", "other-delete@example.com", generate_password_hash("password123")
    )
    return insert_expense(other_user_id, 75.0, "Bills", "2026-02-01", "Electricity")


# ------------------------------------------------------------------ #
# Unit tests: database/queries.py::delete_expense                    #
# ------------------------------------------------------------------ #

def test_delete_expense_own_row_removes_it_from_db(temp_db):
    user_id = create_user(
        "Unit Test User", "unit-delete@example.com", generate_password_hash("password123")
    )
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    delete_expense(expense_id, user_id)

    assert _expense_row(expense_id) is None, "Expected the row to be gone after delete"


def test_delete_expense_wrong_user_id_leaves_row_untouched(temp_db):
    owner_id = create_user(
        "Owner User", "owner-delete@example.com", generate_password_hash("password123")
    )
    intruder_id = create_user(
        "Intruder User", "intruder-delete@example.com", generate_password_hash("password123")
    )
    expense_id = insert_expense(owner_id, 50.0, "Food", "2026-03-20", "Lunch")

    delete_expense(expense_id, intruder_id)

    row = _expense_row(expense_id)
    assert row is not None, "Deleting with the wrong user_id must be a silent no-op"
    assert row["user_id"] == owner_id


def test_delete_expense_non_existent_id_raises_no_error(temp_db):
    user_id = create_user(
        "Unit Test User 2", "unit-delete-2@example.com", generate_password_hash("password123")
    )

    delete_expense(999999, user_id)  # must not raise


# ------------------------------------------------------------------ #
# POST /expenses/<id>/delete -- auth guard                            #
# ------------------------------------------------------------------ #

def test_post_delete_expense_unauthenticated_redirects_to_login(client):
    user_id = create_user(
        "Auth Guard User", "auth-guard-delete@example.com", generate_password_hash("password123")
    )
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_post_delete_expense_unauthenticated_does_not_delete_row(client):
    user_id = create_user(
        "Auth Guard User 2", "auth-guard-delete-2@example.com", generate_password_hash("password123")
    )
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    client.post(f"/expenses/{expense_id}/delete")

    assert _expense_row(expense_id) is not None, "Unauthenticated POST must not delete"


# ------------------------------------------------------------------ #
# POST /expenses/<id>/delete -- happy path                            #
# ------------------------------------------------------------------ #

def test_post_delete_expense_own_expense_redirects_to_profile(client):
    _login(client)
    user_id = _session_user_id(client)
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_post_delete_expense_own_expense_removes_row_from_db(client):
    _login(client)
    user_id = _session_user_id(client)
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    client.post(f"/expenses/{expense_id}/delete")

    assert _expense_row(expense_id) is None


# ------------------------------------------------------------------ #
# POST /expenses/<id>/delete -- ownership / not-found                 #
# ------------------------------------------------------------------ #

def test_post_delete_expense_other_users_expense_returns_404(client):
    _login(client)
    other_expense_id = _other_user_expense_id()

    response = client.post(f"/expenses/{other_expense_id}/delete")

    assert response.status_code == 404


def test_post_delete_expense_other_users_expense_leaves_row_untouched(client):
    _login(client)
    other_expense_id = _other_user_expense_id()

    client.post(f"/expenses/{other_expense_id}/delete")

    assert _expense_row(other_expense_id) is not None, (
        "Deleting another user's expense must not remove it"
    )


def test_post_delete_expense_non_existent_id_returns_404(client):
    _login(client)
    response = client.post("/expenses/999999/delete")
    assert response.status_code == 404


def test_post_delete_expense_twice_second_call_returns_404(client):
    _login(client)
    user_id = _session_user_id(client)
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    first = client.post(f"/expenses/{expense_id}/delete")
    second = client.post(f"/expenses/{expense_id}/delete")

    assert first.status_code == 302
    assert second.status_code == 404


# ------------------------------------------------------------------ #
# GET /expenses/<id>/delete -- method not allowed                     #
# ------------------------------------------------------------------ #

def test_get_delete_expense_returns_405(client):
    _login(client)
    user_id = _session_user_id(client)
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 405


# ------------------------------------------------------------------ #
# Template changes: profile transaction table "Delete" action         #
# ------------------------------------------------------------------ #

def test_profile_page_has_delete_form_per_transaction(client):
    _login(client)
    user_id = _session_user_id(client)
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    response = client.get("/profile")
    html = response.data.decode()

    assert f'action="/expenses/{expense_id}/delete"' in html
    assert "Delete" in html


def test_profile_page_still_has_edit_link_alongside_delete(client):
    _login(client)
    user_id = _session_user_id(client)
    expense_id = insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    response = client.get("/profile")
    html = response.data.decode()

    assert f'href="/expenses/{expense_id}/edit"' in html
    assert "Edit" in html
