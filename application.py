import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT symbol, name, SUM(shares) AS shares FROM stocks WHERE id = :user_id GROUP BY symbol", user_id = session["user_id"])
    print('step 1 | stocks: ' + str(stocks), flush=True)

    stock_total = 0

    for stock in stocks:
        # Via lookup() we get current price
        symbol = stock["symbol"]
        quote = lookup(symbol)
        price = quote["price"]
        # Price is converted into a string formatted by usd(). "Price" is needed for calculations and "price_string" is needed for formatting as usd() in index.html table
        stock['price_string'] = usd(price)
        # Price is added into "stocks" which is being sent into index.html
        stock['price'] = price
        # Shares is inquired from "stocks"
        shares = stock["shares"]
        # Total value is being calculated and added into "stocks"
        stock['total'] = shares * price
        # Total is converted into a string formatted by usd(). "total" is needed for calculations and "total_string" is needed for formatting as usd() in index.html table
        stock['total_string'] = usd(stock['total'])
        stock_total = stock_total + stock['total']
    print('step 2 | stocks: ' + str(stocks), flush=True)

    # Row "CASH" for index.html
    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])
    cash = user[0]['cash']
    if not stocks:
        final_total = usd(cash)
    else:
        final_total = usd(cash + stock_total)
    cash = usd(cash)
    return render_template('index.html', stocks=stocks, cash=cash, final_total=final_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Ensure stock symbol was provided
        if not request.form.get("symbol"):
            return apology("must provide stock's symbol", 403)

        # Ensure requested stock exists
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if not quote:
            return apology("stock doesn't exist", 403)

        # Ensure shares were provided
        if not request.form.get("shares"):
            return apology("must provide a number of shares", 403)

        # Ensure shares quantity is a positive integer
        if int(request.form.get("shares")) < 1:
            return apology("must provide a positive value", 403)

        # Ensure user has enough cash
        price = quote["price"]
        print('step 1 | price: ' + str(quote["price"]), flush=True)
        shares = float(request.form.get("shares"))
        print('step 1 | shares: ' + str(request.form.get("shares")), flush=True)
        total = price * shares
        print('step 2 | total: ' + str(total), flush=True)
        row = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])
        cash = float(row[0]["cash"])
        print('step 3 | user id: ' + str(session["user_id"]), flush=True)
        print('step 3 | cash: ' + str(cash), flush=True)

        if total > cash:
            return apology("not enough cash", 403)
        else:
            cash_total = cash - total
            print('step 4 | cash_total: ' + str(cash_total), flush=True)
            db.execute("INSERT INTO stocks(id, symbol, name, shares, price, total) VALUES (:id, :symbol, :name, :shares, :price, :total)", id = session["user_id"], symbol = request.form.get("symbol"), name = quote["name"], shares = request.form.get("shares"), price = quote["price"], total = total)
            db.execute("UPDATE users SET cash = :cash_total WHERE id = :user_id", cash_total = cash_total, user_id = session["user_id"])
            flash("Bought!")
            print('step 5', flush=True)
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT symbol, shares, price, transacted FROM stocks WHERE id = :user_id", user_id = session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol);
        return render_template("quoted.html", quote=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        hashed = generate_password_hash(request.form.get("password"))
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # USERNAME CHECK
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username does not exist
        if len(rows) != 0:
            return apology("this username is taken", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        elif not confirmation:
            return apology("must confirm password", 403)

        # Ensure confirmation password matches password
        elif not password == confirmation:
            return apology("passwords do not match", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = username, hash = hashed)

        # Log user in
        session["user_id"] = id
        session["username"] = username

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        print('SELL | symbol: ' + str(symbol), flush=True)
        if symbol == "invalid":
            return apology("must select stock", 403)
        print('SELL | symbol: ' + str(symbol), flush=True)
        if not request.form.get("shares"):
            return apology("must provide a number of shares", 403)

        shares = float(request.form.get("shares"))
        print('SELL | shares: ' + str(request.form.get("shares")), flush=True)
        if shares < 1:
            return apology("must provide a positive value", 403)
        symbols_owned = db.execute("SELECT symbol, SUM(shares) AS shares FROM stocks WHERE id = :user_id AND symbol= :symbol GROUP BY symbol", user_id = session["user_id"], symbol = symbol)
        print('SELL | symbols_owned: ' + str(symbols_owned), flush=True)
        if not symbols_owned:
            return apology("no such stock is owned", 403)
        if symbols_owned[0]["shares"] < shares:
            return apology("not enough shares of stock owned", 403)

        quote = lookup(symbol)
        price = quote["price"]
        print('SELL | price: ' + str(quote["price"]), flush=True)
        price = price
        total = price * shares
        total_sold = total * -1
        print('SELL | total: ' + str(total), flush=True)
        row = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])
        cash = float(row[0]["cash"])
        print('SELL | user id: ' + str(session["user_id"]), flush=True)
        print('SELL | cash: ' + str(cash), flush=True)
        cash_total = cash + total
        print('SELL | cash_total: ' + str(cash_total), flush=True)
        shares_sold = int(request.form.get("shares")) * -1

        db.execute("INSERT INTO stocks (id, symbol, name, shares, price, total) VALUES (:id, :symbol, :name, :shares_sold, :price, :total)", id = session["user_id"], symbol = request.form.get("symbol"), name = quote["name"], shares_sold = shares_sold, price = price, total = total_sold)
        db.execute("UPDATE users SET cash = :cash_total WHERE id = :user_id", cash_total = cash_total, user_id = session["user_id"])

        flash("Sold!")
        return redirect("/")

    else:
        symbols_owned = db.execute("SELECT symbol, SUM(shares) as shares FROM stocks WHERE id = :user_id GROUP BY symbol", user_id = session["user_id"])
        print('SELL | symbols_owned: ' + str(symbols_owned), flush=True)
        return render_template("sell.html", symbols_owned=symbols_owned)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
