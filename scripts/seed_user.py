"""One-off script: insert a single realistic random Indian user."""

import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.security import generate_password_hash

from database.db import get_db

FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Arjun", "Divya",
    "Karthik", "Meera", "Rohan", "Isha", "Suresh", "Kavya", "Aditya", "Pooja",
    "Manoj", "Lakshmi", "Sandeep", "Neha", "Ravi", "Shreya", "Vivek", "Anjali",
    "Harish", "Deepika", "Nikhil", "Swati", "Gaurav", "Radha",
]

LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Menon", "Patel",
    "Rao", "Kulkarni", "Chatterjee", "Mukherjee", "Naidu", "Pillai", "Singh",
    "Desai", "Joshi", "Bhat", "Krishnan", "Chauhan",
]


def generate_user():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    number = random.randint(10, 999)
    email = f"{first.lower()}.{last.lower()}{number}@gmail.com"
    return name, email


def main():
    conn = get_db()
    try:
        while True:
            name, email = generate_user()
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if not existing:
                break

        password_hash = generate_password_hash("password123")
        created_at = datetime.now().isoformat(sep=" ", timespec="seconds")

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, email, password_hash, created_at),
        )
        conn.commit()

        print("User created:")
        print(f"  id:    {cursor.lastrowid}")
        print(f"  name:  {name}")
        print(f"  email: {email}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
