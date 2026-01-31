"""
Database migration for webhooks and notifications system
Creates tables: webhook_events, notifications
"""
import sqlite3
from datetime import datetime

def migrate():
    conn = sqlite3.connect('biajez.db')
    cursor = conn.cursor()
    
    print("🔄 Starting webhooks migration...")
    
    # Create webhook_events table
    print("Creating webhook_events table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhook_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL,
            processed BOOLEAN DEFAULT 0,
            processed_at DATETIME,
            created_at DATETIME NOT NULL,
            error_message TEXT
        )
    """)
    
    # Create index on event_type for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_webhook_events_type 
        ON webhook_events(event_type)
    """)
    
    # Create index on processed for filtering
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_webhook_events_processed 
        ON webhook_events(processed)
    """)
    
    print("✅ webhook_events table created")
    
    # Create notifications table
    print("Creating notifications table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            read BOOLEAN DEFAULT 0,
            action_required BOOLEAN DEFAULT 0,
            related_order_id TEXT,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES profiles(user_id)
        )
    """)
    
    # Create index on user_id for faster user queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_user 
        ON notifications(user_id)
    """)
    
    # Create index on read status
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_read 
        ON notifications(read)
    """)
    
    # Create index on created_at for sorting
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_created 
        ON notifications(created_at DESC)
    """)
    
    print("✅ notifications table created")
    
    conn.commit()
    conn.close()
    
    print("✅ Migration completed successfully!")
    print("\nCreated tables:")
    print("  - webhook_events (with indexes on event_type, processed)")
    print("  - notifications (with indexes on user_id, read, created_at)")

if __name__ == "__main__":
    migrate()
