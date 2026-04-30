import csv
from datetime import datetime
from flask import request, session, redirect, render_template, url_for
import hashlib
import io
import re
import sqlite3


# -----------------------------
# Cosnstants
# -----------------------------

DB_FILE = "NostraFinance.db"

DEFAULT_CATEGORIES = [
    "Groceries",
    "Dining",
    "Shopping",
    "Transport",
    "Utilities",
    "Insurance",
    "Pharmacy",
    "Salary",
    "Cash Withdrawal",
    "Transfers",
    "Entertainment",
    "Healthcare",
    "Education",
    "Children",
    "Pets",
    "Travel",
    "Rent",
    "Mortgage",
    "Savings",
    "Uncategorized",
]

DEFAULT_ACCOUNTS = [
    ("Main Account", "UBS", "Current Account", "CHF"),
]

# -----------------------------
# Helpers for database queries
# -----------------------------

def connectDataBase(db = DB_FILE):
        # Connects to DB returns dicts
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con


def get_current_user_id():
    return session.get("user_id")


# -----------------------------
# Helpers for onboarding
# -----------------------------


def seed_default_categories():
    con = connectDataBase()
    cur = con.cursor()
    user = get_current_user_id()

    for category_name in DEFAULT_CATEGORIES:
        cur.execute(
            """
            INSERT OR IGNORE INTO categories (user_id, name)
            VALUES (?, ?)
            """,
            (user, category_name),
        )
    con.commit()


def seed_default_accounts():
    con = connectDataBase()
    cur = con.cursor()
    user = get_current_user_id
    for name, institution, account_type, currency in DEFAULT_ACCOUNTS:
        cur.execute(
            """
            INSERT OR IGNORE INTO accounts (
                user_id,
                name,
                institution,
                account_type,
                currency
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (user, name, institution, account_type, currency),
        )
    con.commit()
