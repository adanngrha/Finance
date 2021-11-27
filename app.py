from datetime import datetime
import os
import re

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        username = request.form.get("username")
        password = request.form.get("password")
        passwordConfirm = request.form.get("password-confirmation")

        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        # Ensure password-confirmation was submitted
        elif not passwordConfirm:
            return apology("must provide password confirmation", 403)

        # Ensure password and password-confirmation is matched
        elif password != passwordConfirm:
            return apology("password not matched with the password confirmation", 403)

        # Hash password
        hash = generate_password_hash(password)

        # Store username and hashed password to the database
        db.execute("INSERT INTO users (username, hash, cash) VALUES (?, ?, ?)", username, hash, 10000)
 
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        # User reached route via GET (as by clicking a link or via redirect)
        return render_template("register.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required  # decorator
def quote():
    """Get stock quote."""
    if request.method == "POST":
        
        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("Symbol required", 403)
        
        # This is dictionary
        company = lookup(request.form.get("symbol"))
        
        # Handle if stocks doesn't exists
        if company == None:
            return apology("Stocks doesn't exists", 403)
  
        return render_template("quoted.html", company=company)
    
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        
        # Get user_id
        user_id = session.get("user_id")
        
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        shares = int(shares)
        
        # Ensure symbol was submitted
        if not symbol:
            return apology("Symbol required", 403)
        
        # Ensure shares was positive integer
        if not shares > 0:
            return apology("Shares must positive integer", 403)
        
        # This is dictionary
        company = lookup(symbol)

        # Ensure stocks exists
        if company == None:
            return apology("Stocks doesn't exists", 403)
        
        # Ensure shares was submitted
        elif not shares:
            return apology("Shares required", 403)
        
        # Times stocks price with shares
        price = company["price"] * shares
        
        # Get user cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cash[0]["cash"]
        cash = float(cash)
        
        # Ensure user cash is enough 
        if cash < price:
            return apology("User cash is not enough to buy", 403)
        
        # Transaction datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Store transactions to database
        db.execute("INSERT INTO transactions(user_id, transaction_type, symbol, company_name, shares, price, transacted) VALUES(?, ?, ?, ?, ?, ?, ?)", user_id, "buy", company["symbol"], company["name"], shares, price, now)
        
        # Update user cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - price, user_id)

        # Redirect user to homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")    


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == "POST":
        redirect("/")

    else:
        return render_template("index.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        redirect("/")

    else:
        return render_template("sell.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == "POST":
        redirect("/")

    else:
        return render_template("history.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
