# Production Deployment Guide

## 🚀 Current Production Setup (Render)

**Live URL:** https://biajez-ah0g.onrender.com

### Services
- **Backend:** Render Web Service (Python/FastAPI)
- **Database:** Render PostgreSQL (biajez_db)
- **Cache:** Render Redis
- **Keep-alive:** GitHub Actions (pings every 5 minutes)

### Environment Variables (Render)
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
DUFFEL_ACCESS_TOKEN=duffel_live_...
OPENAI_API_KEY=sk-...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=...
RESEND_API_KEY=...
ADMIN_SECRET=biajez_admin_2026
```

### Admin Endpoints
```bash
# Health check
GET /health
GET /admin/health

# Profile management
GET /admin/profiles?secret=ADMIN_SECRET
GET /admin/profile/{phone}?secret=ADMIN_SECRET
GET /admin/profile-by-userid/{user_id}?secret=ADMIN_SECRET
POST /admin/fix-profile-phone?secret=ADMIN_SECRET&user_id=X&new_phone=Y

# Database fixes
POST /admin/fix-db?secret=ADMIN_SECRET

# Server management
POST /admin/restart?secret=ADMIN_SECRET
GET /admin/logs?secret=ADMIN_SECRET
GET /scheduler/status
```

### WhatsApp Bot Commands
- **registrar** - Register/update profile
- **mi perfil** - View profile and preferences
- **preferencias** - View preferences only
- **mis vuelos** / **mis reservas** - View bookings
- **ayuda** - Show all commands
- **reset** - Clear session

---

## 🚀 Alternative: Manual Server Deployment

### Prerequisites

1. **Server Requirements:**
   - Python 3.9+
   - Node.js 16+
   - SQLite 3 (or PostgreSQL for production)
   - Nginx (recommended)
   - SSL certificate (Let's Encrypt)

2. **API Keys:**
   - Duffel API production token
   - Stripe production keys
   - Duffel webhook secret

---

## 📋 Step-by-Step Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3-pip python3-venv nginx certbot python3-certbot-nginx -y

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Clone and Setup Project

```bash
# Clone repository
git clone https://github.com/yourusername/biajez.git
cd biajez

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
npm run build
cd ..
```

### 3. Configure Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit with production values
nano .env
```

**Required variables:**
```bash
ENVIRONMENT=production
DUFFEL_ACCESS_TOKEN=duffel_live_your_token
STRIPE_SECRET_KEY=sk_live_your_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_key
DUFFEL_WEBHOOK_SECRET=whsec_your_secret
DATABASE_URL=postgresql://user:pass@localhost/biajez  # Recommended for production
```

### 4. Database Setup

```bash
# For PostgreSQL (recommended)
sudo apt install postgresql postgresql-contrib
sudo -u postgres createdb biajez
sudo -u postgres createuser biajez_user -P

# Run migrations
python migrate_webhooks.py
python migrate_notifications_metadata.py
```

### 5. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/biajez
```

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Frontend
    location / {
        root /path/to/biajez/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /v1 {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Webhooks
    location /webhooks {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/biajez /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. SSL Certificate

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 7. Setup Systemd Service

```bash
sudo nano /etc/systemd/system/biajez.service
```

```ini
[Unit]
Description=Biajez API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/biajez
Environment="PATH=/path/to/biajez/venv/bin"
ExecStart=/path/to/biajez/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable biajez
sudo systemctl start biajez
sudo systemctl status biajez
```

### 8. Setup Database Backups

```bash
# Make backup script executable
chmod +x backup_db.sh

# Add to crontab (daily at 2 AM)
crontab -e
```

Add line:
```
0 2 * * * /path/to/biajez/backup_db.sh
```

### 9. Configure Duffel Webhooks

1. Go to https://app.duffel.com/webhooks
2. Add webhook URL: `https://yourdomain.com/webhooks/duffel`
3. Select events:
   - order.airline_initiated_change_detected
   - order.cancelled
   - order.changed
   - payment.failed
4. Copy webhook secret to `.env`

### 10. Test Deployment

```bash
# Check API
curl https://yourdomain.com/v1/

# Check frontend
curl https://yourdomain.com/

# Check logs
sudo journalctl -u biajez -f
```

---

## 🔒 Security Checklist

- [ ] HTTPS enabled (SSL certificate)
- [ ] Environment variables secured
- [ ] Database credentials secured
- [ ] CORS configured for specific domains
- [ ] Rate limiting enabled
- [ ] Firewall configured
- [ ] Regular backups scheduled
- [ ] Monitoring setup

---

## 📊 Monitoring

### Setup Logging

```python
# Already configured in error_handler.py
# Logs will be in /var/log/biajez/
```

### Recommended Tools

- **Uptime monitoring:** UptimeRobot, Pingdom
- **Error tracking:** Sentry
- **Analytics:** Google Analytics, Plausible
- **Performance:** New Relic, Datadog

---

## 🔄 Updates & Maintenance

### Deploying Updates

```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# Restart service
sudo systemctl restart biajez
```

### Database Migrations

```bash
# Run migration scripts
python new_migration.py

# Restart service
sudo systemctl restart biajez
```

---

## 🆘 Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u biajez -n 50

# Check configuration
python -c "import app.config"
```

### Database connection issues

```bash
# Check PostgreSQL
sudo systemctl status postgresql

# Test connection
psql -U biajez_user -d biajez
```

### Nginx errors

```bash
# Check config
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log
```

---

## 📞 Support

For issues or questions:
- Check logs: `sudo journalctl -u biajez -f`
- Review configuration: `app/config.py`
- Test endpoints: `curl https://yourdomain.com/v1/`

---

## ✅ Post-Deployment Checklist

- [ ] API responding correctly
- [ ] Frontend loading
- [ ] Payments working (test mode first!)
- [ ] Webhooks receiving events
- [ ] Database backups running
- [ ] SSL certificate valid
- [ ] Monitoring active
- [ ] Error tracking configured
- [ ] Documentation updated
- [ ] Team notified

🎉 **Deployment Complete!**
