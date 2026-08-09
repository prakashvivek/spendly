# Spec: Login and Logout

## Overview
This step wires up real authentication for Spendly. `GET /login` currently
renders a static form and `GET /logout` is a stub string response. This
feature implements session-based login (verifying credentials against the
`users` table and setting a signed session cookie) and logout (clearing that
session), so that later steps (profile, expenses) have a logged-in user to
work with.

## Depends on
- **Step 1 — Database setup**: `users` table with `password_hash` must exist
  and `get_db()` must be available (`database/db.py`).
- **Step 2 — Registration**: `GET /register` template exists so users can be
  pointed there if login fails. Login itself does not require `POST
  /register` to be implemented — test users can come from
  `database.db.seed_db()` (seeds `nitish@example.com` / `password123`).

## Routes
- `GET /login` — renders the login form — public (already implemented, kept as-is)
- `POST /login` — validates email + password against `users`, sets
  `session["user_id"]` on success and redirects to `/profile`; re-renders
  `login.html` with an error on failure — public
- `GET /logout` — clears the session and redirects to `/login` — logged-in
  (safe to call when already logged out; just redirects)

## Database changes
No new tables or columns. Add one helper to `database/db.py`:
- `get_user_by_email(email)` — parameterized `SELECT id, name, email,
  password_hash FROM users WHERE email = ?`, returns a single row or `None`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change `<form action="/login">` to
    `<form action="{{ url_for('login') }}">` (currently hardcoded, violates
    the no-hardcoded-URLs rule)

## Files to change
- `app.py` —
  - set `app.secret_key` (required for Flask sessions; read from an env var
    with a dev-only fallback)
  - change `/login` to accept `GET` and `POST` (`methods=["GET", "POST"]`)
  - implement `POST /login`: look up user via
    `database.db.get_user_by_email`, verify password with
    `werkzeug.security.check_password_hash`, set `session["user_id"]` on
    success, `abort()`-free error handling — re-render `login.html` with
    `error=` on failure
  - implement `GET /logout`: `session.clear()`, `redirect(url_for("login"))`
- `database/db.py` — add `get_user_by_email(email)`
- `templates/login.html` — fix hardcoded form action

## Files to create
None.

## New dependencies
No new dependencies. `flask.session` and
`werkzeug.security.check_password_hash` are already available via
`requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`check_password_hash` — never compare
  plaintext)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Do not implement `/profile`, `/expenses/*` — they remain stubs (Steps 4, 7–9)
- Session cookie is the only auth mechanism — no remember-me / JWT / new packages

## Definition of done
- [ ] `POST /login` with the seeded credentials
      (`nitish@example.com` / `password123`) redirects to `/profile` and a
      session cookie is set
- [ ] `POST /login` with a wrong password re-renders `login.html` with an
      error message and no session cookie is set
- [ ] `POST /login` with an email not in the `users` table re-renders
      `login.html` with an error message (no user enumeration — same
      generic error as wrong password)
- [ ] `GET /logout` after logging in clears the session and redirects to
      `/login`
- [ ] `GET /logout` when not logged in does not error — it redirects to
      `/login`
- [ ] `templates/login.html` form action uses `url_for('login')`, not a
      hardcoded string
- [ ] `pytest` passes with no regressions
