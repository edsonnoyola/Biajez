import sqlite3

# Path to SQLite database
db_path = "antigravity.db"

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("🔄 Migrando base de datos para Order Management...")

# Add missing columns to trips table
try:
    cursor.execute("ALTER TABLE trips ADD COLUMN duffel_order_id TEXT")
    print("✅ Added duffel_order_id")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  duffel_order_id already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN refund_amount NUMERIC(10, 2)")
    print("✅ Added refund_amount")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  refund_amount already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN departure_city TEXT")
    print("✅ Added departure_city")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  departure_city already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN arrival_city TEXT")
    print("✅ Added arrival_city")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  arrival_city already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN departure_date DATE")
    print("✅ Added departure_date")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  departure_date already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN return_date DATE")
    print("✅ Added return_date")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  return_date already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN ticket_url TEXT")
    print("✅ Added ticket_url")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  ticket_url already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN trip_id TEXT")
    print("✅ Added trip_id")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  trip_id already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE trips ADD COLUMN pnr_code TEXT")
    print("✅ Added pnr_code")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  pnr_code already exists")
    else:
        raise

conn.commit()
conn.close()

print("\n✅ Migración completa! Reinicia el backend si está corriendo.")
