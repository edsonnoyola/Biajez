#!/bin/bash
# Database Backup Script
# Run this daily via cron: 0 2 * * * /path/to/backup_db.sh

# Configuration
DB_PATH="biajez.db"
BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/biajez_${DATE}.db"
KEEP_DAYS=30

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Perform backup
echo "🔄 Starting database backup..."
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    echo "✅ Backup created successfully: $BACKUP_FILE"
    
    # Compress backup
    gzip "$BACKUP_FILE"
    echo "✅ Backup compressed: ${BACKUP_FILE}.gz"
    
    # Delete old backups (older than KEEP_DAYS)
    find "$BACKUP_DIR" -name "biajez_*.db.gz" -mtime +$KEEP_DAYS -delete
    echo "✅ Old backups cleaned up (keeping last $KEEP_DAYS days)"
    
    # Show backup size
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
    echo "📊 Backup size: $BACKUP_SIZE"
    
else
    echo "❌ Backup failed!"
    exit 1
fi

echo "✅ Backup completed successfully"
