"""
Database access layer for Spendly.

Provides:
    get_db()   — returns a SQLite connection with row_factory and
                 foreign keys enabled
    init_db()  — creates all tables (CREATE TABLE IF NOT EXISTS)
    seed_db()  — inserts sample data for local development

The SQLite file lives at the project root as `expense_tracker.db`
(gitignored, created at runtime).
"""

import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"


def get_db():
    """Open a new SQLite connection with row access by column name and
    foreign key enforcement turned on (SQLite has it off by default).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the users and expenses tables if they don't exist yet."""
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                description TEXT,
                date        TEXT NOT NULL,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert a sample user and a few sample expenses for local dev.

    Safe to call multiple times: the user insert is keyed off the
    UNIQUE email constraint, and expenses are only inserted if the
    table is currently empty.
    """
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (name, email, password_hash) "
            "VALUES (?, ?, ?)",
            (
                "Nitish Kumar",
                "nitish@example.com",
                generate_password_hash("password123"),
            ),
        )
        conn.commit()

        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("nitish@example.com",)
        ).fetchone()

        expense_count = conn.execute(
            "SELECT COUNT(*) FROM expenses"
        ).fetchone()[0]

        if expense_count == 0:
            sample_expenses = [
                (user["id"], 450.00, "Food", "Lunch with team", "2026-08-01"),
                (user["id"], 1200.00, "Transport", "Cab to airport", "2026-08-03"),
                (user["id"], 2999.00, "Shopping", "New headphones", "2026-08-05"),
            ]
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, description, date) "
                "VALUES (?, ?, ?, ?, ?)",
                sample_expenses,
            )
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Database ready at {DB_PATH}")
