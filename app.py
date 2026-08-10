import os

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import create_user, get_user_by_email

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


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

PROFILE_USER = {
    "name": "Nitish Kumar",
    "email": "nitish@example.com",
    "initials": "NK",
    "member_since": "January 2025",
}

PROFILE_STATS = [
    {"label": "Total spent", "value": "₹39,280", "hint": "All time"},
    {"label": "Transactions", "value": "27", "hint": "All time"},
    {"label": "Top category", "value": "Food", "hint": "₹14,200 spent"},
]

PROFILE_TRANSACTIONS = [
    {"date": "Aug 8, 2026", "description": "Swiggy order", "category": "Food", "color_class": "cat-1", "amount": "₹450"},
    {"date": "Aug 6, 2026", "description": "Uber ride to airport", "category": "Travel", "color_class": "cat-3", "amount": "₹980"},
    {"date": "Aug 4, 2026", "description": "Electricity bill", "category": "Bills", "color_class": "cat-2", "amount": "₹2,150"},
    {"date": "Aug 2, 2026", "description": "Grocery shopping", "category": "Food", "color_class": "cat-1", "amount": "₹1,620"},
    {"date": "Jul 30, 2026", "description": "Netflix subscription", "category": "Entertainment", "color_class": "cat-4", "amount": "₹499"},
]

PROFILE_CATEGORIES = [
    {"name": "Food", "amount": "₹14,200", "percent": 36, "color_class": "cat-1", "width_class": "profile-w-35"},
    {"name": "Bills", "amount": "₹11,050", "percent": 28, "color_class": "cat-2", "width_class": "profile-w-30"},
    {"name": "Travel", "amount": "₹9,830", "percent": 25, "color_class": "cat-3", "width_class": "profile-w-25"},
    {"name": "Entertainment", "amount": "₹4,200", "percent": 11, "color_class": "cat-4", "width_class": "profile-w-10"},
]


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=PROFILE_USER,
        stats=PROFILE_STATS,
        transactions=PROFILE_TRANSACTIONS,
        categories=PROFILE_CATEGORIES,
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
