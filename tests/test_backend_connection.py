"""
Tests for the /profile route and database/queries.py once they are wired
to real data (Step 5 — Backend Connection).

Shared fixture: a "Demo User" with a fixed 8-expense dataset used by all
three query-concern test groups (transactions, stats, categories) so they
all assert against identical numbers. This fixture is local to this file
only — it does not touch database/db.py's seed_db() or conftest.py, so the
existing nitish@example.com seed data and every test relying on it are
unaffected.

Demo dataset (8 expenses, 7 categories, total 346.24, Bills is top):
    Food            45.50
    Transport       32.00
    Bills          120.00
    Bills           45.74   (Bills total: 165.74 — highest)
    Shopping        38.00
    Entertainment   15.00
    Health          25.00
    Other           25.00
"""

import pytest
from werkzeug.security import generate_password_hash

from database import create_user, get_db, get_recent_transactions

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_NAME = "Demo User"

DEMO_EXPENSES = [
    (45.50, "Food", "Groceries", "2026-08-01"),
    (32.00, "Transport", "Metro card top-up", "2026-08-02"),
    (120.00, "Bills", "Internet bill", "2026-08-03"),
    (45.74, "Bills", "Mobile recharge", "2026-08-04"),
    (38.00, "Shopping", "New shoes", "2026-08-05"),
    (15.00, "Entertainment", "Movie ticket", "2026-08-06"),
    (25.00, "Health", "Pharmacy", "2026-08-07"),
    (25.00, "Other", "Misc purchase", "2026-08-08"),
]


@pytest.fixture
def demo_user(temp_db):
    """Seed the Demo User + fixed 8-expense dataset, return the user id."""
    user_id = create_user(DEMO_NAME, DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD))

    conn = get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, description, date) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, amount, category, description, date)
             for amount, category, description, date in DEMO_EXPENSES],
        )
        conn.commit()
    finally:
        conn.close()

    return user_id


def _login_demo_user(client):
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})


def test_recent_transactions_returns_rows_for_demo_user(demo_user):
    transactions = get_recent_transactions(demo_user)

    assert len(transactions) == 8
    assert transactions[0]["date"] == "2026-08-08"
    for txn in transactions:
        assert set(txn.keys()) == {"date", "description", "category", "amount"}


def test_recent_transactions_newest_first_order(demo_user):
    transactions = get_recent_transactions(demo_user)
    dates = [txn["date"] for txn in transactions]

    assert dates == sorted(dates, reverse=True)


def test_recent_transactions_nonexistent_user_returns_empty_list(temp_db):
    assert get_recent_transactions(999999) == []


def test_recent_transactions_user_with_no_expenses_returns_empty_list(temp_db):
    user_id = create_user("No Expenses", "noexpenses@spendly.com", generate_password_hash("password123"))

    assert get_recent_transactions(user_id) == []


def test_recent_transactions_respects_limit(demo_user):
    transactions = get_recent_transactions(demo_user, limit=3)

    assert len(transactions) == 3
    assert [txn["date"] for txn in transactions] == ["2026-08-08", "2026-08-07", "2026-08-06"]


def test_profile_route_shows_transactions_newest_first(client, demo_user):
    _login_demo_user(client)
    response = client.get("/profile")

    assert response.status_code == 200
    aug_8_index = response.data.index(b"Misc purchase")
    aug_1_index = response.data.index(b"Groceries")
    assert aug_8_index < aug_1_index


def test_profile_route_transactions_show_rupee_symbol(client, demo_user):
    _login_demo_user(client)
    response = client.get("/profile")

    assert "₹".encode() in response.data
