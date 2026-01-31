import sqlite3
import os

# Path to SQLite database
db_path = "antigravity.db"

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("🔄 Migrando base de datos...")

# Add missing columns
try:
    cursor.execute("ALTER TABLE profiles ADD COLUMN seat_position_preference TEXT DEFAULT 'WINDOW'")
    print("✅ Added seat_position_preference")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  seat_position_preference already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE profiles ADD COLUMN preferred_airline TEXT")
    print("✅ Added preferred_airline")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  preferred_airline already exists")
    else:
        raise

try:
    cursor.execute("ALTER TABLE profiles ADD COLUMN preferred_hotel_chains TEXT")
    print("✅ Added preferred_hotel_chains")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⚠️  preferred_hotel_chains already exists")
    else:
        raise

conn.commit()
conn.close()

print("\n✅ Migración completa! Ahora reinicia el backend.")
