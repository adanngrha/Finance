from datetime import datetime
import os
import re
from threading import current_thread
from urllib.parse import uses_netloc

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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
        db.execute(
            "INSERT INTO users (username, hash, cash) VALUES (?, ?, ?)", username, hash, 10000)
 
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", username)

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
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", user_id)
        cash = cash[0]["cash"]
        cash = float(cash)
        
        # Ensure user cash is enough 
        if cash < price:
            return apology("User cash is not enough to buy", 403)
        
        # Transaction datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Store companies data to database (companies table) otherwise if company already there, ignore
        db.execute(
            "INSERT OR IGNORE INTO companies (symbol, company_name) VALUES (?, ?)", symbol, company["name"])
        
        company_id = db.execute(
            "SELECT id FROM companies WHERE symbol = ?", symbol)
        company_id = company_id[0]["id"]

        # Check if stock ever buy by the user
        check_assets = db.execute(
            "SELECT * FROM assets WHERE user_id = ? AND company_id = ?", user_id, company_id)
        check_assets = len(check_assets)
        
        if check_assets != 1:
            # Store new assets data to database (assets table)
            db.execute(
                "INSERT OR IGNORE INTO assets (user_id, company_id, current_shares) VALUES (?, ?, ?)",
                   user_id, company_id, shares)
        else:
            # Update shares value
            current_shares = db.execute(
                "SELECT current_shares FROM assets WHERE company_id = ?", company_id)
            current_shares = current_shares[0]["current_shares"]
            current_shares = current_shares + shares
            
            db.execute(
                "UPDATE assets SET current_shares = ? WHERE company_id = ?", current_shares, company_id)

        # Store transactions data to database (transaction table)
        db.execute(
            "INSERT INTO transactions (user_id, company_id, transaction_type, shares, price, transacted) VALUES (?, ?, ?, ?, ?, ?)",
                   user_id, company_id, "buy", shares, price, now)

        # Update user cash (users table)
        cash = cash - price
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        # Redirect user to homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")    


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get user_id
    user_id = session.get("user_id")

    # Get user company id list
    company_id = db.execute(
        "SELECT company_id FROM assets WHERE user_id = ?", user_id)
    company_id = [x['company_id'] for x in company_id]

    # List of symbols, company_names, shares, price, and total_price
    symbols_list = []
    company_names_list = []
    current_shares_list = []
    price_list = []
    total_price_list = []

    # Get user company names list
    for company in company_id:

        symbol = db.execute(
            "SELECT symbol FROM companies WHERE id = ?", company)
        stocks = lookup(symbol[0]["symbol"])
        symbols_list.append(stocks["symbol"])

        company_name = db.execute(
            "SELECT company_name FROM companies WHERE id = ?", company)
        company_name = company_name[0]["company_name"]
        company_names_list.append(company_name)

        # Get user all current shares list
        current_shares = db.execute(
            "SELECT current_shares FROM assets WHERE user_id = ? AND company_id = ?", user_id, company)
        current_shares = current_shares[0]["current_shares"]
        current_shares_list.append(current_shares)

        price = stocks["price"]
        price_list.append(price)

        total_price = price * current_shares
        total_price_list.append(total_price)

    # Update user cash
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash[0]["cash"]

    length = len(symbols_list)
    
    TOTAL = cash

    for total in total_price_list:
        TOTAL = TOTAL + total
    
    # Redirect user to homepage
    return render_template(
        "index.html", length = length, symbols_list = symbols_list, company_names_list = company_names_list,
        current_shares_list = current_shares_list, price_list = price_list, total_price_list = total_price_list,
        cash = cash, TOTAL = TOTAL)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Get user_id
        user_id = session.get("user_id")
        
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        stocks = lookup(symbol)
        price = stocks["price"]
        price = price * float(shares)
                
        # Check user cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cash[0]["cash"]
        cash = cash + price 

        # Get company id
        company_id = db.execute("SELECT id FROM companies WHERE symbol = ?", symbol)
        company_id = company_id[0]["id"]
        
        # Transaction datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update assets table if shares = 0 DELETE
        # Get company available shares
        available_shares = db.execute(
            "SELECT current_shares FROM assets WHERE user_id = ? AND company_id = ?", user_id, company_id)
        available_shares = available_shares[0]["current_shares"]
        available_shares = available_shares - int(shares)
        if available_shares == 0:
            # DELETE
            db.execute("DELETE FROM assets WHERE user_id = ? AND company_id = ?", user_id, company_id) 
        else:
            # UPDATE
            db.execute("UPDATE assets SET current_shares = ? WHERE user_id = ? AND company_id = ?", 
                       available_shares, user_id, company_id)
        
        # Insert to transactions table
        db.execute(
            "INSERT INTO transactions (user_id, company_id, transaction_type, shares, price, transacted) VALUES(?, ?, ?, ?, ?, ?)",
            user_id, company_id, "sell", shares, price, now)
        
        # Update user cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)
        
        # Redirect user to homepage
        return redirect("/")

    else:
        # Get user_id
        user_id = session.get("user_id")
        
        # Get user company id list
        company_id = db.execute(
        "SELECT company_id FROM assets WHERE user_id = ?", user_id)
        company_id = [x['company_id'] for x in company_id]
        
        # Symbols list 
        symbols_list = []
        
        for company in company_id:
            symbol = db.execute(
            "SELECT symbol FROM companies WHERE id = ?", company)
            symbol = symbol[0]["symbol"]
            symbols_list.append(symbol)
        return render_template("sell.html", symbols_list = symbols_list)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == "POST":
        
        return redirect("/")

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
