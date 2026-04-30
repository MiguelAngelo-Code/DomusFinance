import csv
from datetime import datetime
from flask import request, session, redirect, render_template, url_for
import hashlib
import io
import re
import sqlite3

# -----------------------------
# Helpers for database queries
# -----------------------------
DB_FILE = "NostraFinance.db"

def connectDataBase(db = DB_FILE):
        # Connects to DB returns dicts
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        
        return con

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON;")
    con.row_factory = sqlite3.Row
    return con


def get_current_user_id() -> int | None:
    return session.get("user_id")