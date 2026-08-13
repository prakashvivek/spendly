"""
Query helpers for pages that read and write expense data.

Kept separate from database/db.py (which owns auth/user CRUD). Most
functions here are read-only reporting queries for the profile page;
insert_expense() is the one write path, added for the add-expense form.
Each function opens its own connection via get_db() and closes it before
returning, so callers never have to manage connections themselves.
"""

from datetime import datetime

from database.db import get_db


def _date_filter_clause(date_from, date_to):
    """Return (sql_fragment, params) for an optional inclusive date range
    filter on the `date` column. Empty when no filter is active.
    """
    if date_from is not None and date_to is not None:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


def get_user_by_id(user_id):
    """Look up a single user by id.

    Returns {"name", "email", "member_since"}, or None if no user has
    that id. member_since is formatted "Month YYYY" from created_at.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created_at.strftime("%B %Y"),
    }


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {"total_spent", "transaction_count", "top_category"} for a
    user's expenses. Zero-expense case: total_spent=0, transaction_count=0,
    top_category="—".

    If date_from and date_to are both given (ISO "YYYY-MM-DD" strings),
    only expenses with date in that inclusive range are considered.
    """
    conn = get_db()
    try:
        clause, date_params = _date_filter_clause(date_from, date_to)

        totals_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?" + clause,
            (user_id, *date_params),
        ).fetchone()

        top_row = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " "
            "GROUP BY category ORDER BY total DESC LIMIT 1",
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": totals_row["total"],
        "transaction_count": totals_row["count"],
        "top_category": top_row["category"] if top_row is not None else "—",
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return up to `limit` most recent expenses for user_id, newest first.
    Each item: {"date", "description", "category", "amount"}.

    Returns [] if the user has no expenses. If date_from and date_to are
    both given (ISO "YYYY-MM-DD" strings), only expenses with date in that
    inclusive range are considered.
    """
    conn = get_db()
    try:
        clause, date_params = _date_filter_clause(date_from, date_to)
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return categories for user_id ordered by amount desc:
    [{"name", "amount", "pct"}, ...] with integer pct values summing to 100.

    Integer percentages are computed with the largest-remainder method
    (Hamilton apportionment) so they always sum to exactly 100. If
    date_from and date_to are both given (ISO "YYYY-MM-DD" strings), only
    expenses with date in that inclusive range are considered.
    """
    conn = get_db()
    try:
        clause, date_params = _date_filter_clause(date_from, date_to)
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " "
            "GROUP BY category ORDER BY total DESC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)

    bases = []
    remainders = []
    for row in rows:
        raw = row["total"] / grand_total * 100
        base = int(raw // 1)
        bases.append(base)
        remainders.append(raw - base)

    leftover = 100 - sum(bases)
    order = sorted(range(len(rows)), key=lambda i: remainders[i], reverse=True)
    for i in order[:leftover]:
        bases[i] += 1

    return [
        {"name": row["category"], "amount": row["total"], "pct": bases[i]}
        for i, row in enumerate(rows)
    ]


def insert_expense(user_id, amount, category, date, description):
    """Insert a new expense row and return its id.

    description may be None, stored as NULL.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
