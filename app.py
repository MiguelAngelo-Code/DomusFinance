import io
import calendar
from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, flash, redirect, render_template, Response, request, session
from flask_session import Session
from helpers import connectDataBase, get_current_user_id, get_connection, import_ubs_csv, url_for, user_has_family_group, get_invite_by_token, invite_is_valid, add_user_to_family_group, mark_invite_as_accepted, create_family_group
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


@app.route("/import")
def import_csv():
    if ("user_id" not in session):
        return redirect("/login")
    
    return render_template("import_csv.html")



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

    
''' The following function are hidden routes the users'''
@app.route("/upload-csv", methods=["POST"])
def upload_csv():
    user_id = get_current_user_id()
    if not user_id:
        return redirect("/login")

    file = request.files.get("csv_file")
    if file is None or file.filename == "":
        return render_template("error.html", message="Please choose a CSV file.")

    if not file.filename.lower().endswith(".csv"):
        return render_template("error.html", message="Please upload a CSV file.")

    # Optional: pass an account_id from a form select input
    account_id_raw = request.form.get("account_id")
    requested_account_id = None

    if account_id_raw:
        try:
            requested_account_id = int(account_id_raw)
        except ValueError:
            return render_template("error.html", message="Invalid account selected.")

    try:
        result = import_ubs_csv(
            file_storage=file,
            user_id=user_id,
            requested_account_id=requested_account_id,
        )
    except ValueError as e:
        return render_template("error.html", message=str(e))
    except sqlite3.Error:
        return render_template("error.html", message="Database error while importing CSV.")
    except Exception:
        return render_template("error.html", message="Could not import that CSV file.")

    return redirect(
        url_for(
            "transactions",
            imported=result["inserted"],
            skipped=result["skipped"],
            batch=result["import_batch_id"],
        )
    )