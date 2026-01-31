"""
Database migration script to add order change fields to trips table
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('antigravity.db')
    cursor = conn.cursor()
    
    print("🔄 Adding order change fields to trips table...")
    
    # Add change_request_id
    try:
        cursor.execute("ALTER TABLE trips ADD COLUMN change_request_id TEXT")
        print("✅ Added change_request_id")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  change_request_id already exists")
        else:
            raise
    
    # Add change_penalty_amount
    try:
        cursor.execute("ALTER TABLE trips ADD COLUMN change_penalty_amount NUMERIC(10, 2)")
        print("✅ Added change_penalty_amount")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  change_penalty_amount already exists")
        else:
            raise
    
    # Add previous_order_id
    try:
        cursor.execute("ALTER TABLE trips ADD COLUMN previous_order_id TEXT")
        print("✅ Added previous_order_id")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  previous_order_id already exists")
        else:
            raise
    
    conn.commit()
    conn.close()
    print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
