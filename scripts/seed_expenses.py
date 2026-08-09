"""One-off script: seed N random expenses for a user across past M months.

Usage: python scripts/seed_expenses.py <user_id> <count> <months>
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db

CATEGORIES = [
    ("Food", 50, 800, 35, [
        "Lunch at office canteen", "Dinner with friends", "Groceries",
        "Zomato order", "Swiggy order", "Street food", "Breakfast",
    ]),
    ("Transport", 20, 500, 20, [
        "Auto fare", "Ola cab", "Uber ride", "Metro card recharge",
        "Petrol", "Bus ticket",
    ]),
    ("Bills", 200, 3000, 15, [
        "Electricity bill", "Mobile recharge", "Internet bill",
        "Gas cylinder", "Water bill", "DTH recharge",
    ]),
    ("Shopping", 200, 5000, 15, [
        "Clothes shopping", "Amazon order", "Flipkart order",
        "New shoes", "Home decor",
    ]),
    ("Other", 50, 1000, 8, [
        "Miscellaneous", "Gift", "Donation", "Stationery",
    ]),
    ("Entertainment", 100, 1500, 4, [
        "Movie tickets", "Netflix subscription", "Concert ticket",
        "Gaming purchase",
    ]),
    ("Health", 100, 2000, 3, [
        "Pharmacy", "Doctor consultation", "Gym membership", "Lab tests",
    ]),
]


def random_date(months):
    now = datetime.now()
    start = now - timedelta(days=30 * months)
    delta_days = (now - start).days
    offset = random.randint(0, max(delta_days, 0))
    return start + timedelta(days=offset)


def pick_category():
    weights = [c[3] for c in CATEGORIES]
    return random.choices(CATEGORIES, weights=weights, k=1)[0]


def main():
    if len(sys.argv) != 4:
        print("Usage: python scripts/seed_expenses.py <user_id> <count> <months>")
        sys.exit(1)

    try:
        user_id = int(sys.argv[1])
        count = int(sys.argv[2])
        months = int(sys.argv[3])
    except ValueError:
        print("Usage: python scripts/seed_expenses.py <user_id> <count> <months>")
        sys.exit(1)

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            print(f"No user found with id {user_id}.")
            sys.exit(1)

        records = []
        for _ in range(count):
            category, lo, hi, _, descriptions = pick_category()
            amount = round(random.uniform(lo, hi), 2)
            description = random.choice(descriptions)
            date = random_date(months).strftime("%Y-%m-%d")
            records.append((user_id, amount, category, description, date))

        try:
            conn.execute("BEGIN")
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, description, date) "
                "VALUES (?, ?, ?, ?, ?)",
                records,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        dates = [r[4] for r in records]
        print(f"Inserted {len(records)} expenses for user_id={user_id}")
        print(f"Date range: {min(dates)} to {max(dates)}")
        print("Sample records:")
        sample = random.sample(records, min(5, len(records)))
        for user_id_, amount, category, description, date in sample:
            print(f"  {date}  {category:<14} ₹{amount:>8.2f}  {description}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
