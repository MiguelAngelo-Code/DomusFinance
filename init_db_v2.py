import sqlite3
from pathlib import Path

DB_FILE = "finance.db"

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

SCHEMA = """
PRAGMA foreign_keys = ON;

-- =========================
-- Core users table
-- =========================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL
);


-- =========================
-- Accounts
-- =========================
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    institution TEXT,
    account_type TEXT NOT NULL DEFAULT 'current'
        CHECK (account_type IN ('current', 'savings', 'credit_card', 'cash', 'investment', 'loan', 'other')),
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =========================
-- Categories
-- =========================
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =========================
-- Merchants
-- =========================
CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    canonical_name TEXT NOT NULL,
    default_category_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, canonical_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (default_category_id) REFERENCES categories(id) ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS merchant_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    merchant_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, alias),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);



-- =========================
-- Transactions
-- =========================
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER,
    transaction_uid TEXT,

    transaction_date TEXT NOT NULL,      -- YYYY-MM-DD
    transaction_time TEXT,               -- HH:MM:SS
    booking_date TEXT,                   -- YYYY-MM-DD
    value_date TEXT,                     -- YYYY-MM-DD

    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('debit', 'credit')),

    raw_description_1 TEXT,
    raw_description_2 TEXT,
    raw_description_3 TEXT,

    normalized_alias TEXT,

    merchant_id INTEGER,
    merchant_source TEXT NOT NULL DEFAULT 'unknown'
        CHECK (merchant_source IN ('unknown', 'alias', 'rule', 'manual')),

    category_id INTEGER,
    category_source TEXT NOT NULL DEFAULT 'unknown'
        CHECK (category_source IN ('unknown', 'merchant_default', 'manual')),

    payment_reference TEXT,
    transaction_channel TEXT,

    raw_amount_text TEXT,
    raw_date_text TEXT,

    review_status TEXT NOT NULL DEFAULT 'pending_both'
        CHECK (
            review_status IN (
                'resolved',
                'pending_merchant',
                'pending_category',
                'pending_both'
            )
        ),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (user_id, account_id, transaction_uid),

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);



-- =========================
-- Review queues
-- =========================

CREATE TABLE IF NOT EXISTS alias_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    normalized_alias TEXT NOT NULL,
    raw_example TEXT,
    suggested_merchant_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'ignored')),
    resolved_merchant_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    UNIQUE (user_id, normalized_alias),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_merchant_id) REFERENCES merchants(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS merchant_category_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    merchant_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'ignored')),
    resolved_category_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    UNIQUE (user_id, merchant_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- =========================
-- Helpful indexes
-- =========================

CREATE INDEX IF NOT EXISTS idx_merchants_default_category_id
ON merchants(default_category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id
ON transactions(user_id);

CREATE INDEX IF NOT EXISTS idx_transactions_account_id
ON transactions(account_id);

CREATE INDEX IF NOT EXISTS idx_transactions_date
ON transactions(transaction_date);

CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id
ON transactions(merchant_id);

CREATE INDEX IF NOT EXISTS idx_transactions_category_id
ON transactions(category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_normalized_alias
ON transactions(normalized_alias);

CREATE INDEX IF NOT EXISTS idx_alias_reviews_status
ON alias_reviews(status);

CREATE INDEX IF NOT EXISTS idx_merchant_category_reviews_status
ON merchant_category_reviews(status);

-- =========================
-- updated_at Triggers
-- =========================

-- Update timestamp when account details change
CREATE TRIGGER IF NOT EXISTS trg_accounts_updated_at
AFTER UPDATE OF name, institution, account_type, currency ON accounts
FOR EACH ROW
BEGIN
    UPDATE accounts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp when category name changes
CREATE TRIGGER IF NOT EXISTS trg_categories_updated_at
AFTER UPDATE OF name ON categories
FOR EACH ROW
BEGIN
    UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp when merchant details change
CREATE TRIGGER IF NOT EXISTS trg_merchants_updated_at
AFTER UPDATE OF canonical_name, default_category_id ON merchants
FOR EACH ROW
BEGIN
    UPDATE merchants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp when transaction details change 
-- (Excludes updated_at and review_status to prevent infinite loops)
CREATE TRIGGER IF NOT EXISTS trg_transactions_updated_at
AFTER UPDATE OF 
    account_id, transaction_date, transaction_time, booking_date, 
    value_date, amount_cents, currency, direction, raw_description_1, 
    normalized_alias, merchant_id, category_id
ON transactions
FOR EACH ROW
BEGIN
    UPDATE transactions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- =========================
-- 2. Review Status Maintenance
-- =========================

-- Sets the initial review status based on what data was provided during import
CREATE TRIGGER IF NOT EXISTS trg_transactions_set_review_status_after_insert
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    UPDATE transactions
    SET review_status = CASE
        WHEN NEW.merchant_id IS NULL AND NEW.category_id IS NULL THEN 'pending_both'
        WHEN NEW.merchant_id IS NULL THEN 'pending_merchant'
        WHEN NEW.category_id IS NULL THEN 'pending_category'
        ELSE 'resolved'
    END
    WHERE id = NEW.id;
END;

-- Automatically updates the status when a user fixes a merchant or category
CREATE TRIGGER IF NOT EXISTS trg_transactions_set_review_status_after_update
AFTER UPDATE OF merchant_id, category_id ON transactions
FOR EACH ROW
BEGIN
    UPDATE transactions
    SET review_status = CASE
        WHEN NEW.merchant_id IS NULL AND NEW.category_id IS NULL THEN 'pending_both'
        WHEN NEW.merchant_id IS NULL THEN 'pending_merchant'
        WHEN NEW.category_id IS NULL THEN 'pending_category'
        ELSE 'resolved'
    END
    WHERE id = NEW.id;
END;

-- =========================
-- 3. Automation Logic
-- =========================

-- When a Merchant gets a "Default Category", automatically apply it to 
-- all existing 'unknown' transactions for that merchant.
CREATE TRIGGER IF NOT EXISTS trg_merchants_apply_default_category_to_transactions
AFTER UPDATE OF default_category_id ON merchants
FOR EACH ROW
WHEN NEW.default_category_id IS NOT NULL
BEGIN
    UPDATE transactions
    SET category_id = NEW.default_category_id,
        category_source = 'merchant_default'
    WHERE user_id = NEW.user_id
      AND merchant_id = NEW.id
      AND category_id IS NULL
      AND category_source = 'unknown';
END;
"""


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON;")
    con.row_factory = sqlite3.Row
    return con


def create_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def main() -> None:
    db_exists = Path(DB_FILE).exists()

    con = get_connection()
    create_schema(con)

    con.close()

    if db_exists:
        print(f"Database checked/updated successfully: {DB_FILE}")
    else:
        print(f"Database created successfully: {DB_FILE}")

    print("Schema is ready.")


if __name__ == "__main__":
    main()