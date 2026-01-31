"""
Migration to add metadata column to notifications table
Stores flight change details (original vs new flight)
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('biajez.db')
    cursor = conn.cursor()
    
    print("🔄 Adding metadata column to notifications...")
    
    try:
        # Add metadata column
        cursor.execute("""
            ALTER TABLE notifications 
            ADD COLUMN metadata TEXT
        """)
        
        conn.commit()
        print("✅ metadata column added successfully")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️  metadata column already exists, skipping")
        else:
            raise e
    
    conn.close()
    print("✅ Migration completed!")

if __name__ == "__main__":
    migrate()
