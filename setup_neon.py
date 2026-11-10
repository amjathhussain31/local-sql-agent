# setup_neon.py
import os
import random
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("NEON_DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("NEON_DATABASE_URL not found in .env")

REGIONS    = ["North", "South", "East", "West", "Central"]
SEGMENTS   = ["Consumer", "Corporate", "Home Office"]
REASONS    = ["Defective", "Wrong item", "Changed mind", "Damaged in transit"]
PRODUCTS   = [
    ("Laptop Pro 15",    "Electronics",     1299.99),
    ("Wireless Mouse",   "Electronics",       29.99),
    ("Standing Desk",    "Furniture",         449.99),
    ("Office Chair",     "Furniture",         299.99),
    ("Stapler Set",      "Office Supplies",    12.99),
    ("Notebook Pack",    "Office Supplies",     8.99),
    ("Polo Shirt",       "Clothing",           34.99),
    ("Winter Jacket",    "Clothing",           89.99),
    ("Coffee Beans 1kg", "Food",               18.99),
    ("Protein Bar Box",  "Food",               24.99),
    ("USB-C Hub",        "Electronics",        49.99),
    ("Monitor 27in",     "Electronics",       349.99),
    ("Bookshelf",        "Furniture",         199.99),
    ("Pen Set",          "Office Supplies",     6.99),
    ("Sneakers",         "Clothing",           69.99),
]
FIRST = ["Amjath","Priya","Ravi","Sara","James","Mei","Carlos","Fatima","Tom","Aisha"]
LAST  = ["Kumar","Patel","Singh","Chen","Smith","Ali","Johnson","Lee","Brown","Das"]

def random_date(start_ago=730, end_ago=0):
    start = datetime.now() - timedelta(days=start_ago)
    end   = datetime.now() - timedelta(days=end_ago)
    secs  = random.randint(0, int((end - start).total_seconds()))
    return (start + timedelta(seconds=secs)).strftime("%Y-%m-%d")

print("Connecting to Neon...")
conn = psycopg2.connect(DATABASE_URL)
cur  = conn.cursor()
print("Connected.")

print("Dropping old tables...")
cur.execute("""
    DROP TABLE IF EXISTS returns  CASCADE;
    DROP TABLE IF EXISTS orders   CASCADE;
    DROP TABLE IF EXISTS products CASCADE;
    DROP TABLE IF EXISTS customers CASCADE;
""")

print("Creating tables...")
cur.execute("""
    CREATE TABLE customers (
        id          SERIAL PRIMARY KEY,
        name        TEXT NOT NULL,
        region      TEXT NOT NULL,
        segment     TEXT NOT NULL,
        joined_date TEXT NOT NULL
    );
    CREATE TABLE products (
        id       SERIAL PRIMARY KEY,
        name     TEXT NOT NULL,
        category TEXT NOT NULL,
        price    NUMERIC(10,2) NOT NULL,
        stock    INTEGER NOT NULL DEFAULT 100
    );
    CREATE TABLE orders (
        id          SERIAL PRIMARY KEY,
        customer_id INTEGER REFERENCES customers(id),
        product_id  INTEGER REFERENCES products(id),
        quantity    INTEGER NOT NULL,
        total       NUMERIC(10,2) NOT NULL,
        order_date  TEXT NOT NULL
    );
    CREATE TABLE returns (
        id          SERIAL PRIMARY KEY,
        order_id    INTEGER REFERENCES orders(id),
        reason      TEXT NOT NULL,
        return_date TEXT NOT NULL
    );
""")

print("Seeding customers...")
for _ in range(100):
    cur.execute(
        "INSERT INTO customers (name,region,segment,joined_date) VALUES (%s,%s,%s,%s)",
        (f"{random.choice(FIRST)} {random.choice(LAST)}",
         random.choice(REGIONS), random.choice(SEGMENTS), random_date(1095,365))
    )

print("Seeding products...")
for name, cat, price in PRODUCTS:
    cur.execute(
        "INSERT INTO products (name,category,price,stock) VALUES (%s,%s,%s,%s)",
        (name, cat, price, random.randint(5, 200))
    )

print("Seeding orders...")
order_ids = []
for _ in range(500):
    cid = random.randint(1, 100)
    pid = random.randint(1, 15)
    qty = random.randint(1, 5)
    tot = round(qty * PRODUCTS[pid-1][2], 2)
    cur.execute(
        "INSERT INTO orders (customer_id,product_id,quantity,total,order_date) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (cid, pid, qty, tot, random_date(730, 0))
    )
    order_ids.append(cur.fetchone()[0])

print("Seeding returns...")
for oid in random.sample(order_ids, k=75):
    cur.execute(
        "INSERT INTO returns (order_id,reason,return_date) VALUES (%s,%s,%s)",
        (oid, random.choice(REASONS), random_date(60, 0))
    )

conn.commit()
conn.close()

print("\nVerifying...")
conn = psycopg2.connect(DATABASE_URL)
cur  = conn.cursor()
for t in ["customers","products","orders","returns"]:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t:<12} {cur.fetchone()[0]} rows")
conn.close()
print("\nDone. Neon is ready.")