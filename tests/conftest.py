import pytest

import app as app_module
from database import db as db_module


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point db_module at a throwaway SQLite file and initialize it."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    return db_module


@pytest.fixture
def client(temp_db):
    """A Flask test client backed by the temp DB, with a seeded user."""
    temp_db.seed_db()
    app_module.app.config["TESTING"] = True
    app_module.app.secret_key = "test-secret-key"
    with app_module.app.test_client() as test_client:
        yield test_client
