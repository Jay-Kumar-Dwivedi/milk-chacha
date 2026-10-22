import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
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
app.secret_key = os.getenv("SECRET_KEY", "milkchacha_secret_2024")


# ---------------- CART COUNT (available in all templates) ----------------
@app.context_processor
def inject_cart_count():
    if "user_id" in session:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM cart WHERE user_id=%s",
            (session["user_id"],)
        )
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return {"cart_count": int(count)}
    return {"cart_count": 0}


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email    = request.form["email"]
        password = request.form["password"]

        # Hash password before saving
        hashed_password = generate_password_hash(password)

        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        existing = cursor.fetchone()

        if existing:
            cursor.close()
            conn.close()
            flash("Email already registered. Please login.", "error")
            return redirect(url_for("register"))

        cursor.execute(
            "INSERT INTO users(full_name, email, password) VALUES(%s, %s, %s)",
            (full_name, email, hashed_password)
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email    = request.form["email"]
        password = request.form["password"]

        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            # Generate 6-digit OTP and store in session
            otp = str(random.randint(100000, 999999))
            session["otp"]         = otp
            session["otp_user_id"] = user["id"]
            session["otp_name"]    = user["full_name"]
            session["otp_email"]   = user["email"]

            # In production: send OTP via email/SMS
            # For demo: flash the OTP so user can see it
            flash(f"Your OTP is: {otp}  (Demo mode - shown here)", "otp")
            return redirect(url_for("verify_otp"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# ---------------- OTP VERIFY ----------------
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():

    if "otp" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        entered_otp = request.form["otp"].strip()

        if entered_otp == session["otp"]:
            # OTP matched — set real session
            session["user_id"]   = session.pop("otp_user_id")
            session["full_name"] = session.pop("otp_name")
            session["email"]     = session.pop("otp_email")
            session.pop("otp", None)

            flash(f"Welcome back, {session['full_name']}! 🎉", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid OTP. Please try again.", "error")

    return render_template("verify_otp.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT COUNT(*) as total_orders FROM orders WHERE user_id=%s",
        (session["user_id"],)
    )
    stats = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        name=session["full_name"],
        email=session["email"],
        total_orders=stats["total_orders"]
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
        quantity     = int(request.form["quantity"])
        price        = float(request.form["price"])
        total        = quantity * price

        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO orders (user_id, product_name, quantity, price)
            VALUES (%s, %s, %s, %s)
            """,
            (session["user_id"], product_name, quantity, price)
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
    price   = request.args.get("price", "60")

    return render_template("order.html", product=product, price=price)


# ---------------- MY ORDERS ----------------
@app.route("/my-orders")
def my_orders():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orders WHERE user_id=%s ORDER BY order_date DESC",
        (session["user_id"],)
    )

    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("my_orders.html", orders=orders)


# ---------------- CART: ADD ----------------
@app.route("/cart/add", methods=["POST"])
def cart_add():

    if "user_id" not in session:
        return redirect(url_for("login"))

    product_name = request.form["product_name"]
    price        = float(request.form["price"])

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    # If product already in cart, increase quantity
    cursor.execute(
        "SELECT id, quantity FROM cart WHERE user_id=%s AND product_name=%s",
        (session["user_id"], product_name)
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id=%s",
            (existing["id"],)
        )
    else:
        cursor.execute(
            "INSERT INTO cart (user_id, product_name, price, quantity) VALUES (%s,%s,%s,1)",
            (session["user_id"], product_name, price)
        )

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"'{product_name}' added to cart! 🛒", "success")
    return redirect(url_for("products"))


# ---------------- CART: VIEW ----------------
@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM cart WHERE user_id=%s ORDER BY added_at DESC",
        (session["user_id"],)
    )
    items = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("cart.html", items=items)


# ---------------- CART: UPDATE QTY ----------------
@app.route("/cart/update", methods=["POST"])
def cart_update():

    if "user_id" not in session:
        return redirect(url_for("login"))

    cart_id  = int(request.form["cart_id"])
    quantity = int(request.form["quantity"])

    conn   = get_connection()
    cursor = conn.cursor()

    if quantity <= 0:
        cursor.execute(
            "DELETE FROM cart WHERE id=%s AND user_id=%s",
            (cart_id, session["user_id"])
        )
    else:
        cursor.execute(
            "UPDATE cart SET quantity=%s WHERE id=%s AND user_id=%s",
            (quantity, cart_id, session["user_id"])
        )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("cart"))


# ---------------- CART: REMOVE ----------------
@app.route("/cart/remove/<int:cart_id>")
def cart_remove(cart_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM cart WHERE id=%s AND user_id=%s",
        (cart_id, session["user_id"])
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Item removed from cart.", "success")
    return redirect(url_for("cart"))


# ---------------- CART: CHECKOUT (place all as orders) ----------------
@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM cart WHERE user_id=%s",
        (session["user_id"],)
    )
    items = cursor.fetchall()

    if not items:
        flash("Your cart is empty!", "error")
        cursor.close()
        conn.close()
        return redirect(url_for("cart"))

    total = 0
    for item in items:
        cursor.execute(
            "INSERT INTO orders (user_id, product_name, quantity, price) VALUES (%s,%s,%s,%s)",
            (session["user_id"], item["product_name"], item["quantity"], item["price"])
        )
        total += item["quantity"] * float(item["price"])

    # Clear cart after checkout
    cursor.execute("DELETE FROM cart WHERE user_id=%s", (session["user_id"],))

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Order placed successfully! Total: ₹{total:.2f} 🎉", "success")
    return redirect(url_for("my_orders"))


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
