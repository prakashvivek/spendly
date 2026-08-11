import os

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_user,
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_email,
    get_user_by_id,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")


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


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    summary = get_summary_stats(user_id)
    raw_transactions = get_recent_transactions(user_id, limit=10)
    raw_categories = get_category_breakdown(user_id)
    category_colors = _category_color_map(raw_categories)

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": _initials(user_row["name"]),
        "member_since": user_row["member_since"],
    }

    stats = [
        {"label": "Total spent", "value": f"₹{summary['total_spent']:,.2f}", "hint": "All time"},
        {"label": "Transactions", "value": str(summary["transaction_count"]), "hint": "All time"},
        {"label": "Top category", "value": summary["top_category"], "hint": "Highest spend"},
    ]

    transactions = [
        {
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
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
