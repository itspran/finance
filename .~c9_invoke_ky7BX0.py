import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    uid = session["user_id"]
    portfolio = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE uid=? ORDER BY symbol", uid)
    info = []
    for x in portfolio:
        info.append(lookup(x["symbol"]))
    total = 0
    for stock in info:
        shares = db.execute("SELECT SUM(shares) FROM (SELECT * FROM portfolios WHERE uid=? AND symbol=?)", uid, stock["symbol"])
        stock["shares"] = shares[0]["SUM(shares)"]
        temp = lookup(stock["symbol"])
        stock["price"] = temp["price"]
        
        stock["total"] = stock["shares"] * stock["price"]
        total = total + stock["total"]
    
    user = db.execute("SELECT * FROM users WHERE id=?", uid)
    cash = user[0]["cash"]
    total = total + cash
    return render_template("index.html", info=info, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    uid = session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id=?", uid)
    username = user[0]["username"]
    cash = user[0]["cash"]
    if request.method == "GET":
        return render_template("buy.html", username=username, balance=cash)
    else:
        if not request.form.get("symbol"):
            return apology("Enter a Symbol")
        qty = request.form.get("shares")
        if not qty.isnumeric():
            return apology("Invalid quantity")
        qty = int(request.form.get("shares")) 
        if qty <= 0 or qty % 1 != 0:
            return apology("Invalid Quantity")
        if not lookup(request.form.get("symbol")):
            return apology("Invalid Symbol")
        data = lookup(request.form.get("symbol"))
        
        stockprice = data["price"]*qty
        if cash < stockprice:
            return apology("Insufficient Balance")
        now = datetime.now()
        
        dt = now.strftime("%d/%m/%Y %H:%M:%S")
        
        db.execute("INSERT INTO transactions (uid,shares,price,time,symbol) VALUES(?,?,?,?,?)", uid, qty, stockprice, dt, data["symbol"])
        db.execute("INSERT INTO portfolios (uid,symbol,shares) VALUES(?,?,?)", uid, data["symbol"], qty)
        cash = cash-stockprice
        db.execute("UPDATE users SET cash=? WHERE id=?", cash, uid)
        return redirect("/")
    
    # return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    uid = session["user_id"]
    log = db.execute("SELECT * FROM transactions WHERE uid=?", uid)
    return render_template("history.html", log=log)
    
    # return apology("TODO")


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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # return apology("TODO")
    
    if request.method == "GET":
        return render_template("quote.html")
    else:
        user = request.form.get("symbol")
        if not lookup(user):
            return apology("Symbol not found")
        else:
            data = lookup(user)
            price = usd(data["price"])
            symbol = data["symbol"]
            
        return render_template("quoted.html", name=data["name"], price=price, symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        
        passw = request.form.get("password")
        confirm = request.form.get("confirmation")
        if passw != confirm:
            return apology("Password Mismatch")
        
        users = db.execute("SELECT * FROM users")
        userlist = []
        for user in users:
            userlist.append(user["username"])
        user = request.form.get("username")
        if user in userlist:
            return apology("Duplicate Username")
        
        hashed = generate_password_hash(request.form.get("password"))
        
        db.execute("INSERT INTO users (username,hash) VALUES(?,?)", user, hashed)
        
        return redirect("/")
        
            
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    uid = session["user_id"]
    portfolio = db.execute("SELECT DISTINCT symbol FROM portfolios WHERE uid=? ORDER BY symbol", uid)
    info = []
    symbols = []
    for x in portfolio:
        symbols.append(x["symbol"])
    for x in portfolio:
        info.append(lookup(x["symbol"]))
    
    for stock in info:
        shares = db.execute("SELECT SUM(shares) FROM (SELECT * FROM portfolios WHERE uid=? AND symbol=?)", uid, stock["symbol"])
        stock["shares"] = shares[0]["SUM(shares)"]
        temp = lookup(stock["symbol"])
        stock["price"] = temp["price"]
        
        stock["total"] = stock["shares"] * stock["price"]
    user = db.execute("SELECT * FROM users WHERE id=?", uid)
    cash = user[0]["cash"]
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html", info=info)
    else:
        if request.form.get("symbol") not in symbols:
            return apology("Invalid Symbol")
        data = lookup(request.form.get("symbol"))
        qty = request.form.get("shares")
        if not qty.isnumeric():
            return apology("Invalid Quantity")
        stockprice = data["price"]
        amt = int(qty)
        amt = amt*-1
        
        q = amt*-1
        
        now = datetime.now()
        
        dt = now.strftime("%d/%m/%Y %H:%M:%S")
        # reformat and update portfolio
        total = db.execute("SELECT SUM(SHARES) FROM (SELECT * FROM portfolios WHERE uid=? AND symbol=?)", uid, data["symbol"])
        tot = int(total[0]["SUM(SHARES)"])
        
        if q > tot:
            return apology("You don't have that many shares!")
        
        db.execute("DELETE FROM portfolios WHERE uid=? AND symbol=?", uid, data["symbol"])
        db.execute("INSERT INTO portfolios (uid,symbol,shares) VALUES(?,?,?)", uid, data["symbol"], total[0]["SUM(SHARES)"]-q)
        
        #handle 0
        temp = db.execute("SELECT shares FROM portfolios WHERE uid=? AND symbol=?", uid, data["symbol"])
        if temp[0]["shares"] == 0:
            db.execute("DELETE FROM portfolios WHERE uid=? AND symbol=?", uid, data["symbol"])
            
        # update transactions
        db.execute("INSERT INTO transactions (uid,shares,price,time,symbol) VALUES(?,?,?,?,?)",
                   uid, amt, stockprice, dt, data["symbol"])
        
        return redirect("/")
        
