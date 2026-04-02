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

# -----------------------------
# Helpers for database queries
# -----------------------------


def connectDataBase(db = DB_FILE):
        # Connects to DB returns dicts
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        
        return con

# -----------------------------
# Helpers for /import_csv
# -----------------------------

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON;")
    con.row_factory = sqlite3.Row
    return con


def get_current_user_id() -> int | None:
    return session.get("user_id")


def get_current_family_group_id(con: sqlite3.Connection, user_id: int) -> int | None:
    row = con.execute(
        """
        SELECT family_group_id
        FROM family_group_members
        WHERE user_id = ?
        ORDER BY
            CASE role
                WHEN 'owner' THEN 1
                WHEN 'admin' THEN 2
                WHEN 'member' THEN 3
                WHEN 'viewer' THEN 4
                ELSE 5
            END,
            id
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    return row["family_group_id"] if row else None


def get_account_for_import(
    con: sqlite3.Connection,
    family_group_id: int,
    requested_account_id: int | None = None
) -> int | None:
    if requested_account_id is not None:
        row = con.execute(
            """
            SELECT id
            FROM accounts
            WHERE id = ?
              AND family_group_id = ?
              AND is_active = 1
            """,
            (requested_account_id, family_group_id),
        ).fetchone()
        return row["id"] if row else None

    # Fallback to first active account in the household
    row = con.execute(
        """
        SELECT id
        FROM accounts
        WHERE family_group_id = ?
          AND is_active = 1
        ORDER BY id
        LIMIT 1
        """,
        (family_group_id,),
    ).fetchone()

    return row["id"] if row else None


def parse_ubs_date(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def parse_ubs_time(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).strftime("%H:%M:%S")
        except ValueError:
            pass

    return None


def parse_ubs_number(value: str | None) -> float | None:
    if value is None:
        return None

    value = value.strip()
    if value == "":
        return None

    # Handle Swiss/European formatting safely:
    # remove spaces and apostrophe thousands separators
    cleaned = value.replace(" ", "").replace("'", "")

    # If there is a comma but no dot, treat comma as decimal separator
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")

    # If both comma and dot exist, assume commas are thousands separators
    elif "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_alias(*parts: str | None) -> str | None:
    text = " ".join((part or "").strip() for part in parts if part and part.strip())
    if not text:
        return None

    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_transaction_uid(
    account_id: int,
    transaction_date: str | None,
    transaction_time: str | None,
    booking_date: str | None,
    value_date: str | None,
    amount: float | None,
    currency: str | None,
    direction: str | None,
    raw_description_1: str | None,
    raw_description_2: str | None,
    raw_description_3: str | None,
    balance: float | None,
    source_row_number: int,
) -> str:
    payload = "|".join([
        str(account_id),
        transaction_date or "",
        transaction_time or "",
        booking_date or "",
        value_date or "",
        f"{amount:.2f}" if amount is not None else "",
        currency or "",
        direction or "",
        raw_description_1 or "",
        raw_description_2 or "",
        raw_description_3 or "",
        f"{balance:.2f}" if balance is not None else "",
        str(source_row_number),
    ])

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# -----------------------------
# Core import function
# -----------------------------

def import_ubs_csv(file_storage, user_id: int, requested_account_id: int | None = None) -> dict:
    con = get_connection()
    cur = con.cursor()

    try:
        family_group_id = get_current_family_group_id(con, user_id)
        if family_group_id is None:
            raise ValueError("No family group found for this user.")

        account_id = get_account_for_import(con, family_group_id, requested_account_id)
        if account_id is None:
            raise ValueError("No valid account found for this upload.")

        # Create import batch
        cur.execute(
            """
            INSERT INTO import_batches (
                family_group_id,
                account_id,
                uploaded_by_user_id,
                source_filename,
                source_format,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                family_group_id,
                account_id,
                user_id,
                file_storage.filename,
                "ubs_csv_export",
                "Imported from UBS CSV export",
            ),
        )
        import_batch_id = cur.lastrowid

        inserted = 0
        skipped = 0

        # UBS file you uploaded:
        # - comma separated
        # - first 11 lines are title / metadata
        # - line 12 is the real header
        text_stream = io.TextIOWrapper(file_storage.stream, encoding="utf-8-sig", newline="")
        reader = csv.reader(text_stream)

        for _ in range(11):
            next(reader, None)

        header = next(reader, None)
        if not header:
            raise ValueError("CSV header row was not found.")

        # Expected real columns from your UBS export:
        # 0  Date de transaction
        # 1  Heure de transaction
        # 2  Date de comptabilisation
        # 3  Date de valeur
        # 4  Monnaie
        # 5  Débit
        # 6  Crédit
        # 7  Sous-montant
        # 8  Solde
        # 9  No de transaction
        # 10 Description1
        # 11 Description2
        # 12 Description3
        # 13 Notes de bas de page
        #
        # Some rows may have a trailing empty column, so we trim/pad.

        for source_row_number, row in enumerate(reader, start=13):
            if not row or not any(cell.strip() for cell in row):
                continue

            row = row[:14]
            while len(row) < 14:
                row.append("")

            row = [cell.strip() for cell in row]

            raw_date_text = row[0]
            transaction_date = parse_ubs_date(row[0])
            transaction_time = parse_ubs_time(row[1])
            booking_date = parse_ubs_date(row[2])
            value_date = parse_ubs_date(row[3])
            currency = row[4] or None

            debit = parse_ubs_number(row[5])
            credit = parse_ubs_number(row[6])
            sub_amount = parse_ubs_number(row[7])  # available if you ever want it later
            balance = parse_ubs_number(row[8])

            raw_description_1 = row[10] or None
            raw_description_2 = row[11] or None
            raw_description_3 = row[12] or None
            footnotes = row[13] or None

            # Direction + amount
            if debit is not None and credit is None:
                direction = "debit"
                amount = abs(debit)
                raw_amount_text = row[5]
            elif credit is not None and debit is None:
                direction = "credit"
                amount = abs(credit)
                raw_amount_text = row[6]
            elif debit is not None and credit is not None:
                # Defensive fallback if both are populated
                direction = "credit" if credit >= debit else "debit"
                amount = abs(credit if direction == "credit" else debit)
                raw_amount_text = row[6] if direction == "credit" else row[5]
            else:
                # No usable amount
                skipped += 1
                continue

            normalized = normalize_alias(raw_description_1, raw_description_2, raw_description_3)

            transaction_uid = build_transaction_uid(
                account_id=account_id,
                transaction_date=transaction_date,
                transaction_time=transaction_time,
                booking_date=booking_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
                direction=direction,
                raw_description_1=raw_description_1,
                raw_description_2=raw_description_2,
                raw_description_3=raw_description_3,
                balance=balance,
                source_row_number=source_row_number,
            )

            cur.execute(
                """
                INSERT OR IGNORE INTO transactions (
                    family_group_id,
                    account_id,
                    transaction_uid,
                    import_batch_id,

                    transaction_date,
                    transaction_time,
                    booking_date,
                    value_date,

                    amount,
                    currency,
                    direction,

                    raw_description_1,
                    raw_description_2,
                    raw_description_3,

                    normalized_alias,

                    merchant_id,
                    merchant_source,

                    category_id,
                    category_source,

                    payment_reference,
                    card_expiry,
                    transaction_type,
                    transaction_channel,

                    balance,

                    source_row_number,
                    raw_amount_text,
                    raw_date_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    family_group_id,
                    account_id,
                    transaction_uid,
                    import_batch_id,

                    transaction_date,
                    transaction_time,
                    booking_date,
                    value_date,

                    amount,
                    currency or "",
                    direction,

                    raw_description_1,
                    raw_description_2,
                    raw_description_3,

                    normalized,

                    None,
                    "unknown",

                    None,
                    "unknown",

                    footnotes,   # storing footnotes here is practical for now
                    None,
                    None,
                    None,

                    balance,

                    source_row_number,
                    raw_amount_text,
                    raw_date_text,
                ),
            )

            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        con.commit()

        return {
            "import_batch_id": import_batch_id,
            "inserted": inserted,
            "skipped": skipped,
            "account_id": account_id,
            "family_group_id": family_group_id,
        }

    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# -----------------------------
# Helpers for /onboarding
# -----------------------------

def get_current_user_id():
    return session.get("user_id")

# Todo: needs edditing to bring to new databsde

def seed_default_categories_for_group(con: sqlite3.Connection, family_group_id: int) -> None:
    cur = con.cursor()
    for category_name in DEFAULT_CATEGORIES:
        cur.execute(
            """
            INSERT OR IGNORE INTO categories (family_group_id, name)
            VALUES (?, ?)
            """,
            (family_group_id, category_name),
        )
    con.commit()


# Todo: needs edditing to bring to new databsde
def seed_default_accounts_for_group(con: sqlite3.Connection, family_group_id: int) -> None:
    cur = con.cursor()
    for name, institution, account_type, currency in DEFAULT_ACCOUNTS:
        cur.execute(
            """
            INSERT OR IGNORE INTO accounts (
                family_group_id,
                name,
                institution,
                account_type,
                currency
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (family_group_id, name, institution, account_type, currency),
        )
    con.commit()
