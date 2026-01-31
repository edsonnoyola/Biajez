"""
Database migration script to create airline_credits table
"""
import sqlite3
from datetime import datetime

def migrate():
    conn = sqlite3.connect('antigravity.db')
    cursor = conn.cursor()
    
    print("🔄 Creating airline_credits table...")
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS airline_credits (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                airline_iata_code TEXT NOT NULL,
                credit_amount NUMERIC(10, 2) NOT NULL,
                credit_currency TEXT NOT NULL,
                credit_code TEXT,
                credit_name TEXT,
                expires_at DATETIME,
                spent_at DATETIME,
                invalidated_at DATETIME,
                order_id TEXT,
                passenger_id TEXT,
                issued_on DATE NOT NULL,
                type TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            )
        """)
        print("✅ Created airline_credits table")
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_airline_credits_user_id 
            ON airline_credits(user_id)
        """)
        print("✅ Created index on user_id")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_airline_credits_spent_at 
            ON airline_credits(spent_at)
        """)
        print("✅ Created index on spent_at")
        
        conn.commit()
        print("✅ Migration complete!")
        
    except sqlite3.Error as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
