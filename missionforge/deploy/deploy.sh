#!/usr/bin/env bash
# MissionForge — VPS deploy script
# Usage: bash deploy.sh [vps_user@host]
# Default target: ubuntu@maxiaworld.app
set -euo pipefail

TARGET="${1:-ubuntu@maxiaworld.app}"
REMOTE_DIR="/opt/missionforge"
SERVICE="missionforge"

echo "==> Deploying MissionForge to $TARGET"

# 1. Sync backend
rsync -az --delete \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache/' \
  --exclude='missionforge.db' \
  --exclude='chroma_db/' \
  missionforge/backend/ "$TARGET:$REMOTE_DIR/backend/"

# 2. Sync landing page
rsync -az --delete \
  missionforge/landing/ "$TARGET:$REMOTE_DIR/landing/"

# 3. Remote setup
ssh "$TARGET" bash << 'REMOTE'
set -euo pipefail
cd /opt/missionforge

# Virtualenv
if [ ! -d venv ]; then
  python3.12 -m venv venv
fi
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r backend/requirements.txt

# Alembic migrations
cd backend
../venv/bin/python -m alembic upgrade head
cd ..

# Systemd service
sudo cp backend/../deploy/missionforge.service /etc/systemd/system/missionforge.service 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable missionforge
sudo systemctl restart missionforge

echo "==> Service status:"
sudo systemctl status missionforge --no-pager -l | head -20
REMOTE

echo "==> Deploy complete. https://mission.maxiaworld.app"
