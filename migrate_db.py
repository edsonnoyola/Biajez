"""
Database Migration Script - Add missing columns
Run this once to update the database schema
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    exit(1)

# Fix for Render's postgres:// vs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

migrations = [
    # Trip table - new columns
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS baggage_services TEXT;",
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS checkin_status VARCHAR DEFAULT 'NOT_CHECKED_IN';",
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS boarding_pass_url VARCHAR;",
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS duffel_order_id VARCHAR;",

    # Notification table - metadata column
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS extra_data TEXT;",

    # E-ticket number from Duffel documents
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS eticket_number VARCHAR;",
]

print("🔄 Running database migrations...")

with engine.connect() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"✅ {sql[:60]}...")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"⏭️  Column already exists, skipping...")
            else:
                print(f"⚠️  {e}")

print("\n✅ Migrations complete!")
