import sqlite3
from datetime import datetime
import pandas as pd

DB_NAME = 'tracker.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            preferred_site TEXT
        )
    ''')
    # Create products table (NOTE: Redundant target_price column removed)
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP,
            platform TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    # Create user_products table (associates users and products)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            target_price REAL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    # Create price_history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    conn.commit()
    conn.close()

def add_user(email, name, preferred_site=None):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, name, preferred_site) VALUES (?, ?, ?)', (email, name, preferred_site))
        user_id = c.lastrowid
    except sqlite3.IntegrityError:
        c.execute('SELECT id FROM users WHERE email = ?', (email,))
        user_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return user_id

def add_product(title, url, image_url, platform):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO products (title, url, image_url, platform, last_checked) VALUES (?, ?, ?, ?, ?)', (title, url, image_url, platform, datetime.now()))
        product_id = c.lastrowid
    except sqlite3.IntegrityError:
        c.execute('SELECT id FROM products WHERE url = ?', (url,))
        product_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return product_id

def add_user_product(user_id, product_id, target_price=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id FROM user_products WHERE user_id = ? AND product_id = ?', (user_id, product_id))
    existing = c.fetchone()
    if existing:
        return existing[0]
    c.execute('INSERT INTO user_products (user_id, product_id, target_price) VALUES (?, ?, ?)', (user_id, product_id, target_price))
    user_product_id = c.lastrowid
    conn.commit()
    conn.close()
    return user_product_id

def add_price_entry(product_id, price):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO price_history (product_id, price) VALUES (?, ?)', (product_id, price))
    conn.commit()
    conn.close()

def get_all_user_products():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT u.id, p.id, up.id, p.url
        FROM user_products up
        JOIN users u ON up.user_id = u.id
        JOIN products p ON up.product_id = p.id
    ''')
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_id_by_email(email):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE email = ?', (email,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_products_by_user_id_with_latest_price(user_id):
    conn = get_connection()
    c = conn.cursor()
    # Efficiently gets all products for a user with their most recent price
    c.execute('''
        WITH LatestPrice AS (
            SELECT 
                product_id, 
                price,
                ROW_NUMBER() OVER(PARTITION BY product_id ORDER BY timestamp DESC) as rn
            FROM price_history
        )
        SELECT 
            p.title, 
            p.url, 
            p.image_url, 
            up.target_price, 
            p.platform, 
            lp.price as current_price
        FROM user_products up
        JOIN products p ON up.product_id = p.id
        LEFT JOIN LatestPrice lp ON p.id = lp.product_id AND lp.rn = 1
        WHERE up.user_id = ?
    ''', (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_price_history_by_url(url):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT ph.timestamp, ph.price
        FROM price_history ph
        JOIN products p ON ph.product_id = p.id
        WHERE p.url = ?
        ORDER BY ph.timestamp ASC
    ''', (url,))
    rows = c.fetchall()
    # Return a list of dictionaries for easy JSON serialization
    return [{'timestamp': row[0], 'price': row[1]} for row in rows]

def update_product_last_checked(product_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE products SET last_checked = ? WHERE id = ?', (datetime.now(), product_id))
    conn.commit()
    conn.close()

def export_to_excel():
    conn = get_connection()
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    with pd.ExcelWriter('tracker_export.xlsx') as writer:
        for table_name in tables['name']:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            df.to_excel(writer, sheet_name=table_name, index=False)
    conn.close()
    print("Exported database to tracker_export.xlsx")