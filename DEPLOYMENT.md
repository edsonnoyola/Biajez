# Deployment Guide - Biajez

## Produccion Actual (Render)

**URL:** https://biajez-d08x.onrender.com

### Servicios en Render
- **Backend:** Web Service (Python/FastAPI) - auto-deploy desde GitHub main
- **Database:** PostgreSQL (Render)
- **Cache:** Redis (Render)
- **Repo:** edsonnoyola/Biajez (publico)

### Variables de Entorno (Render Dashboard)

```bash
# Database
DATABASE_URL=postgresql://...

# Cache
REDIS_URL=redis://...

# Vuelos (Duffel)
DUFFEL_ACCESS_TOKEN=duffel_live_...
DUFFEL_WEBHOOK_SECRET=whsec_...  # PENDIENTE - webhook signature skip sin esto

# AI
OPENAI_API_KEY=sk-...

# WhatsApp (Meta)
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=...

# Email (Resend)
RESEND_API_KEY=re_...
BASE_URL=https://biajez-d08x.onrender.com

# Pagos
STRIPE_SECRET_KEY=sk_test_...

# Admin
ADMIN_SECRET=...
```

### Webhooks Configurados

**WhatsApp (Meta Business Suite):**
- URL: `https://biajez-d08x.onrender.com/v1/whatsapp/webhook`
- Verify Token: configurado en WHATSAPP_VERIFY_TOKEN
- Eventos: messages

**Duffel (https://app.duffel.com/webhooks):**
- URL: `https://biajez-d08x.onrender.com/webhooks/duffel`
- Eventos:
  - order.airline_initiated_change_detected
  - order.cancelled
  - order.changed
  - payment.failed

### Endpoints Principales

```bash
# Health
GET /health
GET /admin/health

# Admin (requiere ?secret=ADMIN_SECRET)
GET  /admin/profiles
GET  /admin/profile/{phone}
GET  /admin/session/{phone}
GET  /admin/redis-status
GET  /admin/list-trips
GET  /admin/booking-errors
GET  /admin/webhook-log
POST /admin/clear-session/{phone}
POST /admin/fix-db
POST /admin/restart
GET  /admin/send-test?phone=X&msg=Y
GET  /scheduler/status
```

### Comandos WhatsApp
- `registrar` - Registro/actualizar perfil
- `mi perfil` - Ver perfil
- `mis vuelos` / `mis reservas` - Ver reservas
- `ayuda` - Menu completo
- `reset` - Limpiar sesion

---

## Desarrollo Local

### Requisitos
- Python 3.11+
- Node.js 16+
- Redis (opcional, usa fallback in-memory)

### Setup

```bash
# Clonar
git clone https://github.com/edsonnoyola/Biajez.git
cd Biajez

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar env
cp .env.production .env
# Editar .env con valores correctos

# Ejecutar backend
uvicorn app.main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

**URLs locales:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

---

## Deploy Manual (Servidor propio)

### 1. Server Setup
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx certbot python3-certbot-nginx -y
```

### 2. Clone y Setup
```bash
git clone https://github.com/edsonnoyola/Biajez.git
cd Biajez
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Nginx Config
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        root /path/to/Biajez/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /v1 {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /webhooks {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
```

### 4. Systemd Service
```ini
[Unit]
Description=Biajez API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Biajez
Environment="PATH=/path/to/Biajez/venv/bin"
ExecStart=/path/to/Biajez/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 5. SSL
```bash
sudo certbot --nginx -d yourdomain.com
```

---

## Troubleshooting

### Servidor no arranca
```bash
# Render
# Ver logs en Render Dashboard → Logs

# Local
uvicorn app.main:app --port 8000
# Revisar output de ENVIRONMENT VARIABLES CHECK
```

### WhatsApp no recibe mensajes
1. Verificar WHATSAPP_ACCESS_TOKEN no expirado
2. Verificar webhook URL en Meta Business Suite
3. Verificar WHATSAPP_VERIFY_TOKEN coincide
4. `GET /admin/send-test?secret=X&phone=Y` para probar envio

### Redis no conecta
1. `GET /admin/redis-status?secret=X` para diagnostico
2. Si Redis falla, usa fallback in-memory automaticamente
3. Verificar REDIS_URL en variables de entorno

### Emails no llegan
1. Verificar RESEND_API_KEY en Render
2. Verificar BASE_URL=https://biajez-d08x.onrender.com
3. Resend free tier: 100 emails/dia

### Webhooks Duffel no llegan
1. Verificar URL en https://app.duffel.com/webhooks
2. Verificar DUFFEL_WEBHOOK_SECRET (si no esta, signature skip)
3. `GET /admin/webhook-log?secret=X` para ver eventos

---

## Security Checklist

- [x] HTTPS (Render SSL automatico)
- [x] Variables de entorno en Render (no en codigo)
- [x] CORS configurado
- [x] ADMIN_SECRET para endpoints admin
- [x] Redis para sesiones (no in-memory en prod)
- [x] Webhook signature verification (Duffel HMAC-SHA256)
- [ ] DUFFEL_WEBHOOK_SECRET pendiente en Render
- [ ] Rate limiting (pendiente)

---

**Ultima actualizacion: 2026-02-20**
