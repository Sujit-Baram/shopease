"""Database layer for ShopEase.

Works with two databases, chosen by the DB_ENGINE environment variable:
  - sqlite (default): a single file, zero setup. Good for your laptop and Module 1.
  - mysql: MySQL or Amazon RDS for MySQL (Module 4 onwards).

All SQL in the app uses "?" placeholders; for MySQL they are converted to "%s".
"""
import os
import sqlite3
from datetime import datetime

ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()

SCHEMA_SQLITE = [
    """CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        price INTEGER NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        emoji TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        total INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'PLACED',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        product_name TEXT NOT NULL,
        unit_price INTEGER NOT NULL,
        qty INTEGER NOT NULL
    )""",
]

SCHEMA_MYSQL = [
    """CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        category VARCHAR(60) NOT NULL,
        description TEXT NOT NULL,
        price INT NOT NULL,
        stock INT NOT NULL DEFAULT 0,
        emoji VARCHAR(16) NOT NULL DEFAULT '',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        customer_name VARCHAR(120) NOT NULL,
        email VARCHAR(160) NOT NULL,
        phone VARCHAR(20) NOT NULL,
        address VARCHAR(400) NOT NULL,
        total INT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PLACED',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT NOT NULL,
        product_id INT NOT NULL,
        product_name VARCHAR(120) NOT NULL,
        unit_price INT NOT NULL,
        qty INT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    ) CHARACTER SET utf8mb4""",
]

# name, category, description, price (rupees), stock, emoji
SEED_PRODUCTS = [
    ("Wireless Earbuds", "Electronics", "Bluetooth 5.3 earbuds with noise cancelling and 30-hour battery.", 2499, 25, "\U0001F3A7"),
    ("Smart Watch", "Electronics", "Heart rate, steps and sleep tracking with a 7-day battery.", 4999, 15, "⌚"),
    ("Laptop 14-inch", "Electronics", "Thin and light laptop: 16 GB RAM, 512 GB SSD, full HD screen.", 45000, 8, "\U0001F4BB"),
    ("Bluetooth Speaker", "Electronics", "Waterproof portable speaker with deep bass.", 1999, 30, "\U0001F50A"),
    ("Power Bank 20000mAh", "Electronics", "Fast-charging power bank with two USB ports.", 1299, 3, "\U0001F50B"),
    ("Running Shoes", "Fashion", "Lightweight running shoes with cushioned soles.", 2999, 20, "\U0001F45F"),
    ("Denim Jacket", "Fashion", "Classic blue denim jacket, regular fit.", 1799, 12, "\U0001F9E5"),
    ("Sunglasses", "Fashion", "UV400 polarised sunglasses with a hard case.", 899, 40, "\U0001F576️"),
    ("Travel Backpack", "Fashion", "30-litre backpack with a padded laptop pocket.", 1499, 18, "\U0001F392"),
    ("Coffee Mug Set", "Home", "Set of 4 ceramic mugs, microwave safe.", 599, 35, "☕"),
    ("Table Lamp", "Home", "LED desk lamp with 3 brightness levels.", 1099, 0, "\U0001F4A1"),
    ("Indoor Plant", "Home", "Easy-care money plant in a ceramic pot.", 449, 22, "\U0001FAB4"),
]


def connect():
    """Open a new database connection."""
    if ENGINE == "mysql":
        import pymysql  # installed from requirements.txt
        return pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "shopease"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "shopease"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    path = os.getenv("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "shopease.db"))
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def sql(statement):
    """Convert '?' placeholders to '%s' for MySQL."""
    return statement.replace("?", "%s") if ENGINE == "mysql" else statement


def to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return d


def query_all(conn, statement, params=()):
    cur = conn.cursor()
    cur.execute(sql(statement), params)
    rows = [to_dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def query_one(conn, statement, params=()):
    cur = conn.cursor()
    cur.execute(sql(statement), params)
    row = to_dict(cur.fetchone())
    cur.close()
    return row


def execute(conn, statement, params=()):
    """Run an INSERT/UPDATE/DELETE. Returns (lastrowid, rowcount)."""
    cur = conn.cursor()
    cur.execute(sql(statement), params)
    result = (cur.lastrowid, cur.rowcount)
    cur.close()
    return result


def init_db():
    """Create the tables if they are missing, and add the sample products once."""
    conn = connect()
    try:
        cur = conn.cursor()
        for statement in (SCHEMA_MYSQL if ENGINE == "mysql" else SCHEMA_SQLITE):
            cur.execute(statement)
        cur.execute("SELECT COUNT(*) AS n FROM products")
        row = cur.fetchone()
        count = row["n"] if isinstance(row, dict) else row[0]
        if count == 0:
            # fixed ids + "IGNORE": if two API processes start at once, the products are still added only once
            ignore = "INSERT IGNORE" if ENGINE == "mysql" else "INSERT OR IGNORE"
            cur.executemany(
                sql(ignore + " INTO products (id, name, category, description, price, stock, emoji) VALUES (?, ?, ?, ?, ?, ?, ?)"),
                [(i + 1,) + p for i, p in enumerate(SEED_PRODUCTS)],
            )
        conn.commit()
        cur.close()
    finally:
        conn.close()
