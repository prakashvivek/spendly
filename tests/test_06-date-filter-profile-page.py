"""
Tests for Step 6 — Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile-page.md

`GET /profile` gains optional `date_from` / `date_to` query params (ISO
`YYYY-MM-DD`, inclusive bounds) that must narrow the summary stats, recent
transactions, and category breakdown sections together. Four quick-select
presets ("This Month", "Last 3 Months", "Last 6 Months", "All Time") are
relative to "today", so `app._today()` — the seam the app documents
specifically for deterministic testing — is patched to a fixed date for the
preset tests.

Fixed-date dataset (4 expenses spanning ~7 months relative to the mocked
"today" of 2026-03-15), independent of any other seeded users in the DB.
Dates are chosen with wide safety margins around each preset boundary so
these tests do not depend on the exact day-level arithmetic used to compute
"N months ago" — only on the coarse spec description of each window:

    Food        100.00  "March lunch"     2026-03-10  (inside this month)
    Transport    50.00  "Jan cab"         2026-01-15  (inside last-3, outside this-month)
    Bills        30.00  "Nov electricity" 2025-11-01  (inside last-6, outside last-3)
    Shopping     20.00  "Aug jacket"      2025-08-01  (outside last-6 / all-time only)

    All-time total: 200.00 across 4 transactions.

Route-level preset tests do not hardcode the exact query-string bounds the
app computes for each preset; instead they extract the real `href` the app
rendered for that preset's link and follow it, so the assertions are about
observable behaviour (which expenses show up) rather than an assumed date
formula.
"""

import re
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from database import (
    create_user,
    get_category_breakdown,
    get_db,
    get_recent_transactions,
    get_summary_stats,
)

FIXED_TODAY = date(2026, 3, 15)

DEMO_EMAIL = "datefilter@spendly.com"
DEMO_PASSWORD = "password123"
DEMO_NAME = "Date Filter Demo"

DATED_EXPENSES = [
    (100.00, "Food", "March lunch", "2026-03-10"),
    (50.00, "Transport", "Jan cab", "2026-01-15"),
    (30.00, "Bills", "Nov electricity", "2025-11-01"),
    (20.00, "Shopping", "Aug jacket", "2025-08-01"),
]

ALL_DESCRIPTIONS = [b"March lunch", b"Jan cab", b"Nov electricity", b"Aug jacket"]
ALL_CATEGORIES = [b"Food", b"Transport", b"Bills", b"Shopping"]
REVERSED_RANGE_ERROR = b"Start date must be before end date."


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def dated_expenses_user(temp_db):
    """Seed a demo user with the fixed-date dataset described above.

    Depends only on `temp_db` (not `client`) so it can be combined freely
    with the `client` fixture, which independently seeds an unrelated
    default user — matching the pattern already used elsewhere in this
    test suite.
    """
    user_id = create_user(DEMO_NAME, DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD))

    conn = get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, description, date) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, amount, category, description, exp_date)
             for amount, category, description, exp_date in DATED_EXPENSES],
        )
        conn.commit()
    finally:
        conn.close()

    return user_id


@pytest.fixture
def fixed_today(monkeypatch):
    """Freeze app._today() so quick-select presets resolve deterministically."""
    monkeypatch.setattr(app_module, "_today", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _login(client):
    return client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})


def _profile_url(date_from=None, date_to=None):
    params = []
    if date_from is not None:
        params.append(f"date_from={date_from}")
    if date_to is not None:
        params.append(f"date_to={date_to}")
    if not params:
        return "/profile"
    return "/profile?" + "&".join(params)


def _anchor_tag(html, label):
    """Return the opening <a ...> tag markup for the given visible link text."""
    label_idx = html.index(label)
    tag_start = html.rindex("<a ", 0, label_idx)
    tag_end = html.index(">", tag_start)
    return html[tag_start:tag_end + 1]


def _href(tag):
    match = re.search(r'href="([^"]*)"', tag)
    assert match, f"No href attribute found in tag: {tag}"
    return match.group(1).replace("&amp;", "&")


def _preset_href(client, label):
    """Fetch the unfiltered profile page and return the real href the app
    rendered for the given preset label."""
    response = client.get("/profile")
    html = response.data.decode("utf-8")
    return _href(_anchor_tag(html, label))


# ------------------------------------------------------------------ #
# No filter -> unfiltered (Step 5 parity)                             #
# ------------------------------------------------------------------ #

def test_profile_no_query_params_returns_unfiltered_alltime_data(client, dated_expenses_user):
    """DoD: visiting /profile with no query params matches Step 5 behaviour."""
    _login(client)
    response = client.get("/profile")

    assert response.status_code == 200
    for description in ALL_DESCRIPTIONS:
        assert description in response.data, f"Expected {description} in unfiltered view"
    for category in ALL_CATEGORIES:
        assert category in response.data, f"Expected {category} in unfiltered view"
    assert "₹200.00".encode() in response.data, "Expected all-time total of ₹200.00"


# ------------------------------------------------------------------ #
# Valid custom range                                                  #
# ------------------------------------------------------------------ #

def test_profile_valid_custom_range_filters_all_three_sections(client, dated_expenses_user):
    """A valid custom range narrows summary stats, transactions, and categories together."""
    _login(client)
    response = client.get(_profile_url("2025-10-01", "2025-12-01"))

    assert response.status_code == 200
    assert b"Nov electricity" in response.data, "In-range transaction should be shown"
    assert b"March lunch" not in response.data, "Out-of-range transaction should be hidden"
    assert b"Jan cab" not in response.data, "Out-of-range transaction should be hidden"
    assert b"Aug jacket" not in response.data, "Out-of-range transaction should be hidden"
    assert b"Bills" in response.data, "In-range category should be shown"
    assert b"Shopping" not in response.data, "Out-of-range category should be excluded"
    assert "₹30.00".encode() in response.data, "Filtered total should only include the in-range expense"


def test_profile_custom_range_boundaries_are_inclusive(client, dated_expenses_user):
    """date_from/date_to bounds are inclusive of expenses on those exact dates."""
    _login(client)
    response = client.get(_profile_url("2026-03-10", "2026-03-10"))

    assert response.status_code == 200
    assert b"March lunch" in response.data, "Expense dated exactly date_from/date_to must be included"
    assert "₹100.00".encode() in response.data


def test_profile_valid_custom_range_shows_no_error_message(client, dated_expenses_user):
    """A well-formed, non-reversed range must not trigger the validation error."""
    _login(client)
    response = client.get(_profile_url("2025-10-01", "2025-12-01"))

    assert response.status_code == 200
    assert REVERSED_RANGE_ERROR not in response.data


def test_profile_custom_range_date_inputs_reflect_submitted_values(client, dated_expenses_user):
    """DoD: the custom-range fields visually indicate the currently applied filter."""
    _login(client)
    response = client.get(_profile_url("2025-10-01", "2025-12-01"))
    html = response.data.decode("utf-8")

    assert 'value="2025-10-01"' in html, "date_from input should reflect the submitted value"
    assert 'value="2025-12-01"' in html, "date_to input should reflect the submitted value"


def test_profile_custom_range_not_matching_any_preset_leaves_all_presets_inactive(client, dated_expenses_user):
    """When a custom range doesn't coincide with a preset, no preset button is active."""
    _login(client)
    response = client.get(_profile_url("2025-10-01", "2025-12-01"))
    html = response.data.decode("utf-8")

    for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
        tag = _anchor_tag(html, label)
        assert "active" not in tag.lower(), f"'{label}' should not be marked active for an unmatched custom range"


# ------------------------------------------------------------------ #
# Quick-select presets (deterministic via fixed_today)                #
# ------------------------------------------------------------------ #

def test_this_month_preset_link_filters_to_current_calendar_month(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "This Month")
    response = client.get(href)

    assert response.status_code == 200
    assert b"March lunch" in response.data
    assert b"Jan cab" not in response.data
    assert b"Nov electricity" not in response.data
    assert b"Aug jacket" not in response.data
    assert "₹100.00".encode() in response.data


def test_last_3_months_preset_link_filters_to_3_month_window(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "Last 3 Months")
    response = client.get(href)

    assert response.status_code == 200
    assert b"March lunch" in response.data
    assert b"Jan cab" in response.data
    assert b"Nov electricity" not in response.data
    assert b"Aug jacket" not in response.data
    assert "₹150.00".encode() in response.data


def test_last_6_months_preset_link_filters_to_6_month_window(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "Last 6 Months")
    response = client.get(href)

    assert response.status_code == 200
    assert b"March lunch" in response.data
    assert b"Jan cab" in response.data
    assert b"Nov electricity" in response.data
    assert b"Aug jacket" not in response.data
    assert "₹180.00".encode() in response.data


def test_all_time_preset_link_shows_every_expense(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "All Time")
    response = client.get(href)

    assert response.status_code == 200
    for description in ALL_DESCRIPTIONS:
        assert description in response.data
    assert "₹200.00".encode() in response.data


def test_all_time_preset_link_has_no_query_params(client, dated_expenses_user, fixed_today):
    """DoD: the All Time preset must pass no query params (clean /profile URL)."""
    _login(client)
    href = _preset_href(client, "All Time")

    assert "?" not in href, f"Expected a clean /profile URL, got: {href}"


# ------------------------------------------------------------------ #
# Reversed range (date_from > date_to)                                #
# ------------------------------------------------------------------ #

def test_reversed_range_falls_back_to_unfiltered_and_shows_error(client, dated_expenses_user):
    _login(client)
    response = client.get(_profile_url("2026-03-15", "2026-01-01"))

    assert response.status_code == 200, "Reversed range must not error out"
    assert REVERSED_RANGE_ERROR in response.data, (
        "Expected a user-visible error message for date_from > date_to"
    )
    for description in ALL_DESCRIPTIONS:
        assert description in response.data, "Reversed range should fall back to the unfiltered view"
    assert "₹200.00".encode() in response.data


# ------------------------------------------------------------------ #
# Malformed / empty date strings                                      #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "date_from,date_to",
    [
        ("not-a-date", "2026-03-15"),
        ("2026-03-01", "not-a-date"),
        ("not-a-date", "also-not-a-date"),
        ("2026-13-40", "2026-03-15"),  # syntactically date-shaped but invalid
        ("2026/03/15", "2026-03-20"),  # wrong separator
    ],
)
def test_malformed_date_falls_back_silently_without_crashing(client, dated_expenses_user, date_from, date_to):
    _login(client)
    response = client.get(_profile_url(date_from, date_to))

    assert response.status_code == 200, "Malformed date input must not produce a 500"
    for description in ALL_DESCRIPTIONS:
        assert description in response.data, "Malformed input should fall back to the unfiltered view"
    assert "₹200.00".encode() in response.data
    assert REVERSED_RANGE_ERROR not in response.data, (
        "Malformed (non-reversed) input should silently fall back, not show the reversed-range error"
    )


def test_empty_string_date_params_falls_back_to_unfiltered(client, dated_expenses_user):
    _login(client)
    response = client.get("/profile?date_from=&date_to=")

    assert response.status_code == 200
    for description in ALL_DESCRIPTIONS:
        assert description in response.data
    assert "₹200.00".encode() in response.data


def test_sql_injection_style_date_param_does_not_crash_and_falls_back(client, dated_expenses_user):
    """Parameterised queries + strptime validation must safely absorb hostile input."""
    _login(client)
    injection = "2026-03-01' OR '1'='1"
    response = client.get(_profile_url(injection, "2026-03-15"))

    assert response.status_code == 200, "SQL-injection-shaped input must not crash the app"
    for description in ALL_DESCRIPTIONS:
        assert description in response.data, "Falls back to unfiltered view, all expenses visible"
    assert "₹200.00".encode() in response.data


# ------------------------------------------------------------------ #
# Partial filter (only one of date_from/date_to present)              #
# ------------------------------------------------------------------ #

def test_partial_filter_only_date_from_falls_back_to_unfiltered(client, dated_expenses_user):
    _login(client)
    response = client.get(_profile_url(date_from="2025-10-01"))

    assert response.status_code == 200
    for description in ALL_DESCRIPTIONS:
        assert description in response.data
    assert "₹200.00".encode() in response.data


def test_partial_filter_only_date_to_falls_back_to_unfiltered(client, dated_expenses_user):
    _login(client)
    response = client.get(_profile_url(date_to="2025-12-01"))

    assert response.status_code == 200
    for description in ALL_DESCRIPTIONS:
        assert description in response.data
    assert "₹200.00".encode() in response.data


# ------------------------------------------------------------------ #
# Active-state visual indication                                      #
# ------------------------------------------------------------------ #

def test_all_time_preset_is_visually_active_by_default(client, dated_expenses_user, fixed_today):
    _login(client)
    response = client.get("/profile")
    html = response.data.decode("utf-8")

    tag = _anchor_tag(html, "All Time")
    assert "active" in tag.lower(), "The default/unfiltered view should mark 'All Time' as active"


def test_this_month_preset_is_active_and_others_are_not(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "This Month")
    response = client.get(href)
    html = response.data.decode("utf-8")

    this_month_tag = _anchor_tag(html, "This Month")
    all_time_tag = _anchor_tag(html, "All Time")
    assert "active" in this_month_tag.lower(), "'This Month' should be marked active when its range is selected"
    assert "active" not in all_time_tag.lower(), "'All Time' should not be marked active when another range is selected"


def test_last_3_months_preset_is_active_when_selected(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "Last 3 Months")
    response = client.get(href)
    html = response.data.decode("utf-8")

    tag = _anchor_tag(html, "Last 3 Months")
    assert "active" in tag.lower()


def test_last_6_months_preset_is_active_when_selected(client, dated_expenses_user, fixed_today):
    _login(client)
    href = _preset_href(client, "Last 6 Months")
    response = client.get(href)
    html = response.data.decode("utf-8")

    tag = _anchor_tag(html, "Last 6 Months")
    assert "active" in tag.lower()


# ------------------------------------------------------------------ #
# Rupee symbol always present                                         #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "query_string",
    [
        "",
        "?date_from=2025-10-01&date_to=2025-12-01",
        "?date_from=2026-03-15&date_to=2026-01-01",  # reversed
        "?date_from=not-a-date&date_to=2026-03-15",  # malformed
    ],
)
def test_rupee_symbol_present_regardless_of_active_filter(client, dated_expenses_user, query_string):
    _login(client)
    response = client.get(f"/profile{query_string}")

    assert response.status_code == 200
    assert "₹".encode() in response.data, "Amounts must always be displayed with the ₹ symbol"


# ------------------------------------------------------------------ #
# No expenses in the selected range                                   #
# ------------------------------------------------------------------ #

def test_range_with_no_matching_expenses_shows_zero_state_without_error(client, dated_expenses_user):
    _login(client)
    response = client.get(_profile_url("2024-01-01", "2024-01-31"))

    assert response.status_code == 200
    assert "₹0.00".encode() in response.data, "Total spent should be ₹0.00 for an empty range"
    for description in ALL_DESCRIPTIONS:
        assert description not in response.data, "No transactions should appear for an empty range"
    for category in ALL_CATEGORIES:
        assert category not in response.data, "Category breakdown should be empty for an empty range"


# ------------------------------------------------------------------ #
# Auth guard — must not regress under the new query params            #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "query_string",
    [
        "",
        "?date_from=2025-10-01&date_to=2025-12-01",
        "?date_from=2026-03-15&date_to=2026-01-01",
        "?date_from=not-a-date&date_to=2026-03-15",
        "?date_from=2025-10-01",
    ],
)
def test_unauthenticated_profile_request_redirects_to_login(client, query_string):
    """No login has occurred; any date-filter query params must not bypass auth."""
    response = client.get(f"/profile{query_string}")

    assert response.status_code == 302, "Unauthenticated /profile access must redirect"
    assert "/login" in response.headers.get("Location", ""), "Must redirect to the login page"


# ------------------------------------------------------------------ #
# Direct unit coverage of the query helpers (database/queries.py)     #
# ------------------------------------------------------------------ #

def test_get_summary_stats_filters_by_date_range(dated_expenses_user):
    stats = get_summary_stats(dated_expenses_user, date_from="2025-09-15", date_to="2026-03-15")

    assert stats["total_spent"] == pytest.approx(180.00)
    assert stats["transaction_count"] == 3
    assert stats["top_category"] == "Food"


def test_get_summary_stats_date_boundaries_are_inclusive(dated_expenses_user):
    stats = get_summary_stats(dated_expenses_user, date_from="2026-03-10", date_to="2026-03-10")

    assert stats["transaction_count"] == 1
    assert stats["total_spent"] == pytest.approx(100.00)


def test_get_summary_stats_without_range_matches_unfiltered_alltime(dated_expenses_user):
    stats = get_summary_stats(dated_expenses_user)

    assert stats["total_spent"] == pytest.approx(200.00)
    assert stats["transaction_count"] == 4


def test_get_recent_transactions_filters_and_keeps_newest_first_order(dated_expenses_user):
    transactions = get_recent_transactions(
        dated_expenses_user, date_from="2025-09-15", date_to="2026-03-15"
    )

    assert [t["date"] for t in transactions] == ["2026-03-10", "2026-01-15", "2025-11-01"]


def test_get_recent_transactions_limit_applies_within_filtered_range(dated_expenses_user):
    transactions = get_recent_transactions(
        dated_expenses_user, limit=2, date_from="2025-09-15", date_to="2026-03-15"
    )

    assert len(transactions) == 2
    assert [t["date"] for t in transactions] == ["2026-03-10", "2026-01-15"]


def test_get_recent_transactions_without_range_matches_unfiltered_alltime(dated_expenses_user):
    transactions = get_recent_transactions(dated_expenses_user)

    assert len(transactions) == 4
    assert transactions[0]["date"] == "2026-03-10"


def test_get_category_breakdown_filters_and_percentages_still_sum_to_100(dated_expenses_user):
    result = get_category_breakdown(dated_expenses_user, date_from="2025-09-15", date_to="2026-03-15")

    names = {c["name"] for c in result}
    assert names == {"Food", "Transport", "Bills"}
    assert "Shopping" not in names
    assert sum(c["pct"] for c in result) == 100


def test_get_category_breakdown_without_range_matches_unfiltered_alltime(dated_expenses_user):
    result = get_category_breakdown(dated_expenses_user)

    names = {c["name"] for c in result}
    assert names == {"Food", "Transport", "Bills", "Shopping"}
    assert sum(c["pct"] for c in result) == 100


def test_get_category_breakdown_empty_range_returns_empty_list(dated_expenses_user):
    result = get_category_breakdown(dated_expenses_user, date_from="2024-01-01", date_to="2024-01-31")

    assert result == []
