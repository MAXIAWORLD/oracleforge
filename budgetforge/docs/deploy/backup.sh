#!/usr/bin/env bash
# BudgetForge — daily DB backup with 30-day retention
# Cron (run as ubuntu): 0 3 * * * /opt/budgetforge/docs/deploy/backup.sh >> /var/log/budgetforge-backup.log 2>&1
set -euo pipefail

DB_SRC="/opt/budgetforge/backend/budgetforge.db"
BACKUP_DIR="/opt/budgetforge-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_DIR/budgetforge-$STAMP.db"

mkdir -p "$BACKUP_DIR"

# sqlite3 .backup flushes WAL before copying — safe under live writes
sqlite3 "$DB_SRC" ".backup '$DEST'"
gzip "$DEST"

# Rotate: delete backups older than 30 days
find "$BACKUP_DIR" -name "*.db.gz" -mtime +30 -delete

echo "[$(date -u +%FT%TZ)] backup OK → ${DEST}.gz"
