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

from database import create_user, get_db
from database import get_summary_stats

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


def test_summary_stats_valid_user_with_expenses(demo_user):
    stats = get_summary_stats(demo_user)
    assert stats["total_spent"] == pytest.approx(346.24)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_summary_stats_nonexistent_user(temp_db):
    stats = get_summary_stats(999999)
    assert stats["total_spent"] == pytest.approx(0)
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


def test_summary_stats_user_with_no_expenses(temp_db):
    user_id = create_user(
        "No Expenses", "no-expenses@spendly.com", generate_password_hash("password123")
    )
    stats = get_summary_stats(user_id)
    assert stats["total_spent"] == pytest.approx(0)
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


def test_profile_route_shows_correct_summary_stats(client, demo_user):
    _login_demo_user(client)
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"346.24" in response.data
    assert b"8" in response.data
    assert b"Bills" in response.data


def test_profile_route_zero_expense_user_shows_zero_stats(client):
    client.post(
        "/register",
        data={
            "name": "Zero Expense User",
            "email": "zero-expense-stats@spendly.com",
            "password": "password123",
        },
    )
    client.post(
        "/login",
        data={"email": "zero-expense-stats@spendly.com", "password": "password123"},
    )
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"0.00" in response.data
    assert b"0" in response.data
