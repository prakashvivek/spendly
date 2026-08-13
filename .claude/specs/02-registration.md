# Spec: Registration

## Overview
Spendly currently renders a registration form (`GET /register`) but does not
process submissions — there is no way to actually create an account yet.
This step adds the `POST /register` handler that validates the submitted
form, hashes the password, inserts a new row into the `users` table, and
redirects the new user to the login page. This is the first step that
writes to the database from a live route, and it unblocks login (Step 3)
and everything downstream that requires an authenticated user.

## Depends on
- Step 1 — Database setup (`database/db.py`, `users` table, `get_db()`)

## Routes
- `POST /register` — validate form input, create the user, redirect to
  `GET /login` on success or re-render `register.html` with an error —
  public

## Database changes
No database changes. The `users` table (`id`, `name`, `email`,
`password_hash`, `created_at`) already supports this feature as defined in
`database/db.py`.

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — change the form's
  `action="/register"` to `action="{{ url_for('register') }}"`; ensure the
  `error` block continues to display validation/duplicate-email errors
  passed from the route

## Files to change
- `app.py` — add a `POST` method to the existing `register` view function;
  keep the `GET` behavior (render `register.html`) unchanged
- `database/db.py` — add a small helper (e.g. `create_user(name, email,
  password_hash)`) so `app.py` contains no raw SQL, per the "no DB logic in
  route functions" rule
- `templates/register.html` — fix hardcoded form action to use `url_for()`

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access goes through `database/db.py` — no raw SQL in `app.py`
- Never hardcode URLs in templates — always use `url_for()`
- Use `abort()` for HTTP errors, not bare error strings
- Validate: name and email required and non-empty, email not already
  registered, password meets the 8-character minimum implied by the
  form's placeholder text
- On duplicate email or invalid input, re-render `register.html` with a
  populated `error` variable and HTTP 200 (do not redirect away from the
  form on failure)

## Definition of done
- [ ] `python app.py` starts without errors on port 5001
- [ ] Submitting the register form with a new name/email/password creates
      a row in the `users` table with a hashed (not plaintext) password
- [ ] After successful registration, the browser is redirected to
      `/login`
- [ ] Submitting the form with an email that already exists re-renders
      `register.html` showing an error, and does not create a duplicate row
- [ ] Submitting the form with a missing name, missing email, or password
      under 8 characters re-renders `register.html` with an error and
      creates no row
- [ ] The register form's `action` uses `url_for('register')`, not a
      hardcoded path
- [ ] No raw SQL string formatting anywhere — all queries in
      `database/db.py` use `?` placeholders
