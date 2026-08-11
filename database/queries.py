"""
Read-only query helpers for pages that aggregate expense data.

Kept separate from database/db.py (which owns auth/user CRUD) because these
are all reporting queries for the profile page. Each function opens its own
connection via get_db() and closes it before returning, so callers never
have to manage connections themselves.
"""

from datetime import datetime

from database.db import get_db


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


def get_summary_stats(user_id):
    """Return {"total_spent", "transaction_count", "top_category"} for a
    user's expenses. Zero-expense case: total_spent=0, transaction_count=0,
    top_category="—".

    Implemented in a follow-up step.
    """
    return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def get_recent_transactions(user_id, limit=10):
    """Return up to `limit` most recent expenses for user_id, newest first.
    Each item: {"date", "description", "category", "amount"}.

    Implemented in a follow-up step.
    """
    return []


def get_category_breakdown(user_id):
    """Return categories for user_id ordered by amount desc:
    [{"name", "amount", "pct"}, ...] with integer pct values summing to 100.

    Integer percentages are computed with the largest-remainder method
    (Hamilton apportionment) so they always sum to exactly 100.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
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
