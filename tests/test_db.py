from database import db as db_module


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")


def test_init_db_creates_tables(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    db_module.init_db()

    conn = db_module.get_db()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    assert {"users", "expenses"}.issubset(tables)


def test_get_db_has_foreign_keys_on(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    db_module.init_db()

    conn = db_module.get_db()
    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.close()

    assert fk_status == 1


def test_seed_db_inserts_sample_data(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    db_module.init_db()
    db_module.seed_db()

    conn = db_module.get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    expenses = conn.execute("SELECT * FROM expenses").fetchall()
    conn.close()

    assert len(users) >= 1
    assert len(expenses) >= 1
    assert expenses[0]["user_id"] == users[0]["id"]
