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
    ("Main Account", "Manual", "current", "CHF"),
]