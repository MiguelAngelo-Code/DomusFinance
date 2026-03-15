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
-- Family groups / households
-- =========================
CREATE TABLE IF NOT EXISTS family_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS family_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (family_group_id, user_id),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =========================
-- Accounts
-- =========================
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    institution TEXT,
    account_type TEXT NOT NULL DEFAULT 'current'
        CHECK (account_type IN ('current', 'savings', 'credit_card', 'cash', 'investment', 'loan', 'other')),
    currency TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (family_group_id, name),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE
);

-- =========================
-- Categories
-- =========================
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    name TEXT NOT NULL COLLATE NOCASE,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (family_group_id, name),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE
);

-- =========================
-- Merchants
-- =========================
CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    canonical_name TEXT NOT NULL COLLATE NOCASE,
    default_category_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (family_group_id, canonical_name),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (default_category_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS merchant_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    alias TEXT NOT NULL COLLATE NOCASE,
    merchant_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (family_group_id, alias),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

-- =========================
-- Import batches
-- =========================
CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    account_id INTEGER,
    uploaded_by_user_id INTEGER,
    source_filename TEXT,
    source_format TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- =========================
-- Transactions
-- =========================
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    account_id INTEGER,
    transaction_uid TEXT,
    import_batch_id INTEGER,

    transaction_date TEXT NOT NULL,      -- YYYY-MM-DD
    transaction_time TEXT,               -- HH:MM:SS
    booking_date TEXT,                   -- YYYY-MM-DD
    value_date TEXT,                     -- YYYY-MM-DD

    amount REAL NOT NULL,
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
    card_expiry TEXT,
    transaction_type TEXT,
    transaction_channel TEXT,

    balance REAL,

    source_row_number INTEGER,
    raw_amount_text TEXT,
    raw_date_text TEXT,

    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    deleted_at TEXT,
    deleted_by_user_id INTEGER,

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

    UNIQUE (family_group_id, account_id, transaction_uid),

    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    FOREIGN KEY (deleted_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- =========================
-- Review queues
-- =========================
CREATE TABLE IF NOT EXISTS alias_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    normalized_alias TEXT NOT NULL COLLATE NOCASE,
    raw_example TEXT,
    suggested_merchant_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'ignored')),
    resolved_merchant_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    UNIQUE (family_group_id, normalized_alias),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_merchant_id) REFERENCES merchants(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS merchant_category_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_group_id INTEGER NOT NULL,
    merchant_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'ignored')),
    resolved_category_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    UNIQUE (family_group_id, merchant_id),
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- =========================
-- Helpful indexes
-- =========================
CREATE INDEX IF NOT EXISTS idx_family_group_members_user_id
ON family_group_members(user_id);

CREATE INDEX IF NOT EXISTS idx_family_group_members_group_id
ON family_group_members(family_group_id);

CREATE INDEX IF NOT EXISTS idx_accounts_family_group_id
ON accounts(family_group_id);

CREATE INDEX IF NOT EXISTS idx_categories_family_group_id
ON categories(family_group_id);

CREATE INDEX IF NOT EXISTS idx_merchants_family_group_id
ON merchants(family_group_id);

CREATE INDEX IF NOT EXISTS idx_merchants_default_category_id
ON merchants(default_category_id);

CREATE INDEX IF NOT EXISTS idx_merchant_aliases_family_group_id
ON merchant_aliases(family_group_id);

CREATE INDEX IF NOT EXISTS idx_merchant_aliases_merchant_id
ON merchant_aliases(merchant_id);

CREATE INDEX IF NOT EXISTS idx_import_batches_family_group_id
ON import_batches(family_group_id);

CREATE INDEX IF NOT EXISTS idx_import_batches_account_id
ON import_batches(account_id);

CREATE INDEX IF NOT EXISTS idx_transactions_family_group_id
ON transactions(family_group_id);

CREATE INDEX IF NOT EXISTS idx_transactions_account_id
ON transactions(account_id);

CREATE INDEX IF NOT EXISTS idx_transactions_date
ON transactions(transaction_date);

CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id
ON transactions(merchant_id);

CREATE INDEX IF NOT EXISTS idx_transactions_category_id
ON transactions(category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_import_batch_id
ON transactions(import_batch_id);

CREATE INDEX IF NOT EXISTS idx_transactions_normalized_alias
ON transactions(normalized_alias);

CREATE INDEX IF NOT EXISTS idx_transactions_is_deleted
ON transactions(is_deleted);

CREATE INDEX IF NOT EXISTS idx_alias_reviews_family_group_id
ON alias_reviews(family_group_id);

CREATE INDEX IF NOT EXISTS idx_alias_reviews_status
ON alias_reviews(status);

CREATE INDEX IF NOT EXISTS idx_merchant_category_reviews_family_group_id
ON merchant_category_reviews(family_group_id);

CREATE INDEX IF NOT EXISTS idx_merchant_category_reviews_status
ON merchant_category_reviews(status);

-- =========================
-- updated_at triggers
-- =========================
CREATE TRIGGER IF NOT EXISTS trg_family_groups_updated_at
AFTER UPDATE OF name ON family_groups
FOR EACH ROW
BEGIN
    UPDATE family_groups
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_accounts_updated_at
AFTER UPDATE OF name, institution, account_type, currency, is_active ON accounts
FOR EACH ROW
BEGIN
    UPDATE accounts
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_categories_updated_at
AFTER UPDATE OF name, is_active ON categories
FOR EACH ROW
BEGIN
    UPDATE categories
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_merchants_updated_at
AFTER UPDATE OF canonical_name, default_category_id, is_active ON merchants
FOR EACH ROW
BEGIN
    UPDATE merchants
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_updated_at
AFTER UPDATE OF
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
    raw_date_text,
    is_deleted,
    deleted_at,
    deleted_by_user_id,
    review_status
ON transactions
FOR EACH ROW
BEGIN
    UPDATE transactions
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- =========================
-- review_status auto-maintenance
-- =========================
CREATE TRIGGER IF NOT EXISTS trg_transactions_set_review_status_after_insert
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    UPDATE transactions
    SET review_status = CASE
        WHEN NEW.is_deleted = 1 THEN 'resolved'
        WHEN NEW.merchant_id IS NULL AND NEW.category_id IS NULL THEN 'pending_both'
        WHEN NEW.merchant_id IS NULL THEN 'pending_merchant'
        WHEN NEW.category_id IS NULL THEN 'pending_category'
        ELSE 'resolved'
    END
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_set_review_status_after_update
AFTER UPDATE OF merchant_id, category_id, is_deleted ON transactions
FOR EACH ROW
BEGIN
    UPDATE transactions
    SET review_status = CASE
        WHEN NEW.is_deleted = 1 THEN 'resolved'
        WHEN NEW.merchant_id IS NULL AND NEW.category_id IS NULL THEN 'pending_both'
        WHEN NEW.merchant_id IS NULL THEN 'pending_merchant'
        WHEN NEW.category_id IS NULL THEN 'pending_category'
        ELSE 'resolved'
    END
    WHERE id = NEW.id;
END;

-- =========================
-- Apply merchant default category to uncategorized transactions
-- Only where category_source is still 'unknown'
-- =========================
CREATE TRIGGER IF NOT EXISTS trg_merchants_apply_default_category_to_transactions
AFTER UPDATE OF default_category_id ON merchants
FOR EACH ROW
WHEN NEW.default_category_id IS NOT NULL
BEGIN
    UPDATE transactions
    SET category_id = NEW.default_category_id,
        category_source = 'merchant_default'
    WHERE family_group_id = NEW.family_group_id
      AND merchant_id = NEW.id
      AND category_id IS NULL
      AND category_source = 'unknown'
      AND is_deleted = 0;
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


def create_family_group(
    con: sqlite3.Connection,
    group_name: str,
    owner_user_id: int,
    seed_defaults: bool = True
) -> int:
    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO family_groups (name, created_by_user_id)
        VALUES (?, ?)
        """,
        (group_name, owner_user_id),
    )
    family_group_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO family_group_members (family_group_id, user_id, role)
        VALUES (?, ?, 'owner')
        """,
        (family_group_id, owner_user_id),
    )

    con.commit()

    if seed_defaults:
        seed_default_categories_for_group(con, family_group_id)
        seed_default_accounts_for_group(con, family_group_id)

    return family_group_id


def create_demo_user_and_group(con: sqlite3.Connection) -> None:
    """
    Optional helper for development only.
    Creates a demo user and household if none exist.
    The password hash below is just placeholder text, not a real hashed password.
    Remove this function if you do not want demo data.
    """
    cur = con.cursor()

    existing_user = cur.execute(
        "SELECT id FROM users WHERE email = ?",
        ("demo@example.com",)
    ).fetchone()

    if existing_user:
        return

    cur.execute(
        """
        INSERT INTO users (username, email, hash)
        VALUES (?, ?, ?)
        """,
        ("demo", "demo@example.com", "replace-with-real-hash"),
    )
    user_id = cur.lastrowid
    con.commit()

    create_family_group(con, "Demo Household", user_id, seed_defaults=True)


def main() -> None:
    db_exists = Path(DB_FILE).exists()

    con = get_connection()
    create_schema(con)

    # Uncomment this only if you want demo data created automatically.
    # create_demo_user_and_group(con)

    con.close()

    if db_exists:
        print(f"Database checked/updated successfully: {DB_FILE}")
    else:
        print(f"Database created successfully: {DB_FILE}")

    print("Schema is ready.")
    print("Default categories and accounts are seeded when you create a family group.")


if __name__ == "__main__":
    main()