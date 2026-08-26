import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from db import get_connection

# Load environment variables from .env
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Secret key from .env
app.secret_key = os.getenv("SECRET_KEY")


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users(full_name,email,password) VALUES(%s,%s,%s)",
            (full_name, email, password)
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["email"] = user["email"]

            return redirect(url_for("dashboard"))

        return "Invalid Email or Password"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        name=session["full_name"],
        email=session["email"]
    )


# ---------------- PRODUCTS ----------------
@app.route("/products")
def products():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("products.html")


# ---------------- ORDER ----------------
@app.route("/order", methods=["GET", "POST"])
def order():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        product_name = request.form["product_name"]
        quantity = int(request.form["quantity"])
        price = float(request.form["price"])

        total = quantity * price

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO orders
            (user_id, product_name, quantity, price)
            VALUES (%s, %s, %s, %s)
            """,
            (
                session["user_id"],
                product_name,
                quantity,
                price
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        return render_template(
            "order_success.html",
            product=product_name,
            quantity=quantity,
            price=price,
            total=total
        )

    product = request.args.get("product", "Fresh Milk")
    price = request.args.get("price", "60")

    return render_template(
        "order.html",
        product=product,
        price=price
    )


# ---------------- MY ORDERS ----------------
@app.route("/my-orders")
def my_orders():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orders WHERE user_id=%s ORDER BY order_date DESC",
        (session["user_id"],)
    )

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "my_orders.html",
        orders=orders
    )


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)