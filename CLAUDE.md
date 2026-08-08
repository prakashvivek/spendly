# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

"Spendly" is a Flask expense tracker built as a guided, step-by-step learning project. Forms, routes, and comments in the code (e.g. `app.py`, `database/db.py`) explicitly mark what a "student" is expected to build next (e.g. `# Students will write this file in Step 1 — Database Setup`, `return "Logout — coming in Step 3"`). When asked to implement one of these placeholder routes or the database layer, follow the scope implied by the existing comment/step number rather than building out unrelated functionality ahead of it.

Currently implemented: static landing/marketing pages (`landing`, `terms`, `privacy`) and the register/login page shells (forms render, but have no backend handler — `register()`/`login()` only do `render_template`, there is no `POST` handling yet). `database/db.py` and `database/__init__.py` are empty stubs. Not yet implemented: DB layer, auth (register/login/logout POST handlers, sessions), profile, and all expense CRUD (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`).

## Commands

Activate the venv first (Windows):
```
venv\Scripts\activate
```

Run the app (starts on port 5001, debug mode on):
```
python app.py
```

Run tests:
```
pytest
```

Install/refresh dependencies:
```
pip install -r requirements.txt
```

There is no lint/format tooling configured in this repo.

## Architecture

- **`app.py`** — single-file Flask app; all routes are defined here directly on the module-level `app` object (no blueprints). This is the place new routes get added.
- **`database/db.py`** — intended home for the DB access layer once implemented: `get_db()` (SQLite connection, `row_factory` + foreign keys on), `init_db()` (creates tables with `CREATE TABLE IF NOT EXISTS`), `seed_db()` (dev sample data). The SQLite file is `expense_tracker.db` (gitignored, created at runtime — not committed).
- **Templates** (`templates/`) use Jinja2 inheritance from `templates/base.html`, which defines the shared `<nav>`/`<footer>` chrome and three blocks: `title`, `head`, `content`, `scripts`. Every page template extends `base.html` and fills `content`; auth/CRUD pages should follow the same pattern rather than duplicating the shell.
- **Static assets**: `static/css/style.css` is the shared/global stylesheet (nav, footer, auth forms, base layout); `static/css/landing.css` holds landing-page-specific styles. `static/js/main.js` is currently an empty placeholder for future client-side behavior.
- Auth forms (`login.html`, `register.html`) already define the field names the backend must accept: register posts `name`, `email`, `password` to `/register`; login posts `email`, `password` to `/login`. Both templates support an `error` template variable for displaying a validation/auth error banner — reuse this when wiring up the POST handlers rather than inventing a new error-passing mechanism.
