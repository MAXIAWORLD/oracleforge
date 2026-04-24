# BudgetForge Deployment Guide

## Production Deployment

### Prerequisites
- Python 3.12+
- SQLite (included) or PostgreSQL
- Domain with SSL certificate
- VPS/Cloud server

### Environment Variables

Create `.env` file:
```bash
# Required for production
APP_ENV=production
APP_URL=https://your-domain.com
ADMIN_API_KEY=your-secure-admin-key
PORTAL_SECRET=your-portal-secret

# LLM Provider API Keys (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...

# SMTP for email alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=alerts@your-domain.com

# Stripe (optional, for billing)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Installation Steps

1. **Clone repository**
```bash
git clone https://github.com/maxia-lab/budgetforge
cd budgetforge/backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Initialize database**
```bash
python -c "from core.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

6. **Run tests**
```bash
python -m pytest tests/ -v
```

7. **Start application**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Production Setup with Systemd

Create `/etc/systemd/system/budgetforge.service`:
```ini
[Unit]
Description=BudgetForge API
After=network.target

[Service]
Type=simple
User=budgetforge
WorkingDirectory=/opt/budgetforge/backend
Environment=PYTHONPATH=/opt/budgetforge/backend
ExecStart=/opt/budgetforge/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable budgetforge
sudo systemctl start budgetforge
```

### Nginx Configuration

Create `/etc/nginx/sites-available/budgetforge`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/private.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/budgetforge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Docker Deployment

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  budgetforge:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - APP_URL=https://your-domain.com
      - ADMIN_API_KEY=${ADMIN_API_KEY}
      - PORTAL_SECRET=${PORTAL_SECRET}
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - budgetforge
    restart: unless-stopped
```

Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Deploy:
```bash
docker-compose up -d
```

### Monitoring & Logging

#### Health Checks
```bash
curl https://your-domain.com/health
```

#### Logs
```bash
# Systemd logs
sudo journalctl -u budgetforge -f

# Application logs
tail -f /opt/budgetforge/backend/budgetforge.log
```

#### Performance Monitoring
Install and configure:
- **Prometheus** for metrics
- **Grafana** for dashboards
- **Sentry** for error tracking

### Backup Strategy

#### Database Backup
```bash
# SQLite
cp budgetforge.db budgetforge.db.backup.$(date +%Y%m%d)

# PostgreSQL
pg_dump budgetforge > backup_$(date +%Y%m%d).sql
```

#### Automated Backup Script
Create `/opt/budgetforge/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/budgetforge/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp /opt/budgetforge/backend/budgetforge.db $BACKUP_DIR/budgetforge_$DATE.db

# Backup configuration
cp /opt/budgetforge/backend/.env $BACKUP_DIR/env_$DATE

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "env_*" -mtime +30 -delete
```

Add to crontab:
```bash
0 2 * * * /opt/budgetforge/backup.sh
```

### Security Checklist

- [ ] SSL certificate installed and valid
- [ ] Admin API key is strong and secure
- [ ] Portal secret is unique and secure
- [ ] Rate limiting is enabled
- [ ] Security headers are configured
- [ ] Database is not exposed to internet
- [ ] Regular backups are running
- [ ] Logs are monitored for suspicious activity
- [ ] Dependencies are up to date

### Troubleshooting

#### Common Issues

**Database locked**
```bash
# Stop application, backup, restart
sudo systemctl stop budgetforge
cp budgetforge.db budgetforge.db.backup
sudo systemctl start budgetforge
```

**Port already in use**
```bash
# Find process using port 8000
sudo lsof -i :8000
# Kill process if necessary
sudo kill -9 <PID>
```

**Permission denied**
```bash
# Fix permissions
sudo chown -R budgetforge:budgetforge /opt/budgetforge
```

### Support

For deployment issues:
- Check logs: `sudo journalctl -u budgetforge`
- Verify environment variables
- Test connectivity: `curl https://your-domain.com/health`
- Contact support: ceo@maxiaworld.app