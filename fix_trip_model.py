"""
Complete database migration for trips table
Adds all missing columns
"""
import sqlite3

conn = sqlite3.connect('antigravity.db')
cursor = conn.cursor()

# Get existing columns
cursor.execute("PRAGMA table_info(trips)")
existing_columns = [column[1] for column in cursor.fetchall()]

print(f"Existing columns: {existing_columns}")

# Define all columns that should exist
required_columns = {
    'payment_id': 'TEXT',
    'booking_type': 'TEXT',
    'hotel_name': 'TEXT',
    'check_in_date': 'TEXT',
    'check_out_date': 'TEXT',
    'id': 'TEXT'
}

# Add missing columns
for column_name, column_type in required_columns.items():
    if column_name not in existing_columns:
        try:
            cursor.execute(f"ALTER TABLE trips ADD COLUMN {column_name} {column_type}")
            print(f"✅ Added column: {column_name}")
        except Exception as e:
            print(f"⚠️  Error adding {column_name}: {e}")

conn.commit()
conn.close()

print("\n✅ Migration complete!")
