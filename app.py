import math
import os
from calendar import monthrange
from datetime import date, datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_user,
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_email,
    get_user_by_id,
    insert_expense,
    update_expense,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")

EXPENSE_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or not email:
        return render_template("register.html", error="Name and email are required.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    password_hash = generate_password_hash(password)
    user_id = create_user(name, email, password_hash)

    if user_id is None:
        return render_template("register.html", error="An account with that email already exists.")

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"] = user["id"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _initials(name):
    """First letter of up to the first two words of a name, uppercased."""
    parts = name.split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _category_color_map(categories):
    """Assign cat-1..cat-4 to each distinct category name in ranking order,
    cycling if there are more than 4 (profile.css only defines 4 colors).
    """
    return {cat["name"]: f"cat-{(i % 4) + 1}" for i, cat in enumerate(categories)}


def _width_class(pct):
    """Round a percent to the nearest 5 and clamp to the available
    profile-w-5..profile-w-100 CSS step classes.
    """
    if pct <= 0:
        return "profile-w-5"
    rounded = min(100, max(5, round(pct / 5) * 5))
    return f"profile-w-{rounded}"


def _parse_date(value):
    """Parse an ISO "YYYY-MM-DD" string into a date, or None if missing
    or malformed."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _today():
    """Wraps date.today() so tests can monkeypatch "now" deterministically."""
    return date.today()


def _validate_expense_form(form):
    """Validate raw amount/category/date/description fields shared by
    add_expense and edit_expense. Returns (form_values, error, parsed):
      - form_values: dict of raw submitted values, for re-populating the
        form on error
      - error: None on success, else a user-facing error message
      - parsed: (amount, category, date_raw, description) on success, else None
    """
    amount_raw = form.get("amount", "")
    category = form.get("category", "")
    date_raw = form.get("date", "")
    description_raw = form.get("description", "")

    form_values = {
        "amount": amount_raw,
        "category": category,
        "date": date_raw,
        "description": description_raw,
    }

    try:
        amount = float(amount_raw)
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError
    except ValueError:
        return form_values, "Enter an amount greater than 0.", None

    if category not in EXPENSE_CATEGORIES:
        return form_values, "Select a valid category.", None

    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except ValueError:
        return form_values, "Enter a valid date.", None

    description = description_raw.strip()[:200] or None
    return form_values, None, (amount, category, date_raw, description)


def _subtract_months(d, months):
    """Return d shifted back by `months` calendar months, clamping the day
    of month for shorter target months (e.g. Aug 31 - 6 months -> Feb 28)."""
    month_index = d.month - 1 - months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _presets(today):
    """Quick-select date ranges anchored on `today`, in display order."""
    month_start = today.replace(day=1)
    return [
        {"key": "this_month", "label": "This Month", "date_from": month_start, "date_to": today},
        {"key": "last_3_months", "label": "Last 3 Months", "date_from": _subtract_months(today, 3), "date_to": today},
        {"key": "last_6_months", "label": "Last 6 Months", "date_from": _subtract_months(today, 6), "date_to": today},
        {"key": "all_time", "label": "All Time", "date_from": None, "date_to": None},
    ]


def _filter_view_context(today, date_from, date_to, filter_error):
    """Build everything the template needs to render the filter bar:
    preset links (with active state), whether the custom range is active,
    and the human-readable range label.
    """
    presets = _presets(today)
    active_preset = None
    if filter_error is None:
        if date_from is None and date_to is None:
            active_preset = "all_time"
        else:
            for preset in presets:
                if preset["date_from"] == date_from and preset["date_to"] == date_to:
                    active_preset = preset["key"]
                    break

    preset_links = [
        {
            "label": preset["label"],
            "url": url_for(
                "profile",
                date_from=preset["date_from"].isoformat() if preset["date_from"] else None,
                date_to=preset["date_to"].isoformat() if preset["date_to"] else None,
            ),
            "active": preset["key"] == active_preset,
        }
        for preset in presets
    ]
    is_custom_active = filter_error is not None or (active_preset is None and date_from is not None)
    range_label = (
        f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"
        if date_from
        else "All Time"
    )

    return preset_links, is_custom_active, range_label


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    raw_from = request.args.get("date_from", "")
    raw_to = request.args.get("date_to", "")
    parsed_from = _parse_date(raw_from)
    parsed_to = _parse_date(raw_to)

    filter_error = None
    date_from = date_to = None
    if parsed_from is not None and parsed_to is not None:
        if parsed_from > parsed_to:
            filter_error = "Start date must be before end date."
        else:
            date_from, date_to = parsed_from, parsed_to

    date_from_str = date_from.isoformat() if date_from else None
    date_to_str = date_to.isoformat() if date_to else None

    summary = get_summary_stats(user_id, date_from=date_from_str, date_to=date_to_str)
    raw_transactions = get_recent_transactions(
        user_id, limit=10, date_from=date_from_str, date_to=date_to_str
    )
    raw_categories = get_category_breakdown(user_id, date_from=date_from_str, date_to=date_to_str)
    category_colors = _category_color_map(raw_categories)

    today = _today()
    preset_links, is_custom_active, range_label = _filter_view_context(
        today, date_from, date_to, filter_error
    )

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": _initials(user_row["name"]),
        "member_since": user_row["member_since"],
    }

    stats = [
        {"label": "Total spent", "value": f"₹{summary['total_spent']:,.2f}", "hint": range_label},
        {"label": "Transactions", "value": str(summary["transaction_count"]), "hint": range_label},
        {"label": "Top category", "value": summary["top_category"], "hint": "Highest spend"},
    ]

    transactions = [
        {
            "id": txn["id"],
            "date": txn["date"],
            "description": txn["description"],
            "category": txn["category"],
            "color_class": category_colors.get(txn["category"], "cat-1"),
            "amount": f"₹{txn['amount']:,.2f}",
        }
        for txn in raw_transactions
    ]

    categories = [
        {
            "name": cat["name"],
            "amount": f"₹{cat['amount']:,.2f}",
            "percent": cat["pct"],
            "color_class": category_colors[cat["name"]],
            "width_class": _width_class(cat["pct"]),
        }
        for cat in raw_categories
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        preset_links=preset_links,
        is_custom_active=is_custom_active,
        filter_error=filter_error,
        range_label=range_label,
        date_from_value=raw_from,
        date_to_value=raw_to,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    today = _today().isoformat()

    if request.method == "GET":
        return render_template("add_expense.html", categories=EXPENSE_CATEGORIES, today=today)

    form_values, error, parsed = _validate_expense_form(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            today=today,
            error=error,
            form_values=form_values,
        )

    amount, category, date_raw, description = parsed
    insert_expense(user_id, amount, category, date_raw, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_expense.html", expense=expense, categories=EXPENSE_CATEGORIES
        )

    form_values, error, parsed = _validate_expense_form(request.form)
    if error:
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=EXPENSE_CATEGORIES,
            error=error,
            form_values=form_values,
        )

    amount, category, date_raw, description = parsed
    update_expense(id, user_id, amount, category, date_raw, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
