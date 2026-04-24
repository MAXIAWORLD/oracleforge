#!/usr/bin/env bash
# BudgetForge — one-time production setup (run ONCE after first deploy)
# Usage: ssh ubuntu@<vps-ip> 'bash /opt/budgetforge/docs/deploy/setup-prod.sh'
set -euo pipefail

DOMAIN="${1:-budgetforge.yourdomain.com}"
DEPLOY_DIR="/opt/budgetforge"
BACKUP_SCRIPT="$DEPLOY_DIR/docs/deploy/backup.sh"

echo "=== BudgetForge prod setup — domain: $DOMAIN ==="

# 1. Verify required ENV vars are present in backend .env
echo ""
echo "--- Checking backend .env ---"
ENV_FILE="$DEPLOY_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.prod.example and fill in values."
  exit 1
fi
REQUIRED_VARS=(SECRET_KEY ADMIN_API_KEY DATABASE_URL APP_URL)
for VAR in "${REQUIRED_VARS[@]}"; do
  if ! grep -q "^${VAR}=" "$ENV_FILE"; then
    echo "  MISSING: $VAR"
    MISSING=1
  else
    echo "  OK: $VAR"
  fi
done
if [ -n "${MISSING:-}" ]; then
  echo "Fill in missing vars before continuing."
  exit 1
fi

# 2. Nginx + certbot
echo ""
echo "--- Nginx + Certbot ---"
sudo apt-get install -y -q certbot python3-certbot-nginx
sudo cp "$DEPLOY_DIR/docs/deploy/nginx.conf" /etc/nginx/sites-available/budgetforge
sudo ln -sf /etc/nginx/sites-available/budgetforge /etc/nginx/sites-enabled/budgetforge
sudo sed -i "s/budgetforge.yourdomain.com/$DOMAIN/g" /etc/nginx/sites-available/budgetforge
sudo nginx -t
sudo systemctl reload nginx

sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$(grep ADMIN_EMAIL "$ENV_FILE" | cut -d= -f2)" --redirect
echo "  Certbot renewal timer: $(systemctl is-active certbot.timer 2>/dev/null || echo 'installed by certbot')"

# 3. Backup cron (daily at 03:00 UTC)
echo ""
echo "--- Backup cron ---"
chmod +x "$BACKUP_SCRIPT"
CRON_LINE="0 3 * * * $BACKUP_SCRIPT >> /var/log/budgetforge-backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v "budgetforge/docs/deploy/backup"; echo "$CRON_LINE" ) | crontab -
echo "  Cron installed: $CRON_LINE"
mkdir -p /opt/budgetforge-backups

# 4. First manual backup
echo ""
echo "--- Running first backup ---"
bash "$BACKUP_SCRIPT"

echo ""
echo "=== Setup complete ==="
echo ""
echo "UptimeRobot — add HTTP(s) monitor:"
echo "  URL: https://$DOMAIN/health"
echo "  Interval: 5 min"
echo "  Alert: your email"
