import io
import calendar
from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, flash, redirect, render_template, Response, request, session
from flask_session import Session
from helpers import connectDataBase
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash


# Configure application
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = "some-secret-key"


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


''' The Folowing rotes are for user accesible pages '''
@app.route("/")
def index():
    # Checks user is loged in
    if ("user_id" not in session):
        return redirect("/login")
    
    return render_template("index.html")

''' The folowng routes handle login, registeration & logout'''
@app.route("/login", methods=["GET", "POST"])
def login():
    if (request.method == "GET"):
        return render_template("login.html")
    
    else:
        session.clear()

        # Get user details
        email = request.form.get("email_address").strip().lower()
        password = request.form.get("password")

        if (not email or not password):
            return render_template("error.html", message="Please eneter valid username and password")
        
        con = connectDataBase()
        cur = con.cursor()
        user = cur.execute("SELECT id, hash FROM users WHERE email = ?", (email,)).fetchone()
        con.close()

        # Check username and password
        if (not user):
            return render_template("error.html", message="User not found")
        if (check_password_hash(user["hash"], password) == False):
            return render_template("error.html", message="Incorrect Password")

        # Login 
        session["user_id"] = user["id"]

        return redirect("/")


@app.route("/logout")
def logout():

    # Logout user & Redirect to index
    session.clear()
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if (request.method == "GET"):
        return render_template("register.html")
    
    else:

        ''' Code black validates user inputs, inserts into DB if correct and logs user in.'''
        session.clear()

        username = request.form.get("username").strip()
        email = request.form.get("email_address").strip().lower()

        # Validate user inputs & Generates Hash
        if (not username or not email or not request.form.get("password_one") or not request.form.get("password_two")):
            return render_template("error.html", message="Please enter valid username and password")
        
        if (request.form.get("password_one") != request.form.get("password_two")):
            return render_template("error.html", message="Passwords do not match")
        

        # Insert user into database
        con = connectDataBase()
        cur = con.cursor()

        hash = generate_password_hash(request.form.get("password_one"), method='scrypt', salt_length=16)

        try:
            cur.execute("INSERT INTO users (email, username, hash) VALUES (?, ?, ?)", (email, username, hash))
            con.commit()
        except sqlite3.IntegrityError:
            # TODO: add as e to print check failure and return cleaner message error to user
            return render_template("error.html", message="SQL constraint failed likley due to unique check on email")
            

        # Login user, close connection & redirects Home
        session["user_id"] = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]

        con.close()

        return redirect("/")