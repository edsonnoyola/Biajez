# Biatriz - Tu Asistente de Viajes

Bot de WhatsApp + Web App para reservaciones de vuelos y hoteles con IA conversacional.

## URLs en Produccion

| Servicio | URL |
|----------|-----|
| Backend API | https://biajez-ah0g.onrender.com |
| Frontend Web | https://frontend-1wqjie9nz-edsons-projects-2a12b3a9.vercel.app |
| WhatsApp Bot | https://wa.me/5215651861011 |
| API Docs | https://biajez-ah0g.onrender.com/docs |

---

## Comandos de WhatsApp

| Comando | Descripcion |
|---------|-------------|
| `ayuda` | Menu de ayuda con todos los comandos |
| `vuelos de X a Y fecha Z` | Buscar vuelos |
| `hoteles en X fecha Y` | Buscar hoteles |
| `itinerario` | Ver proximos viajes |
| `historial` | Ver viajes pasados y estadisticas |
| `equipaje` | Opciones de equipaje adicional |
| `checkin` | Check-in automatico |
| `visa` | Verificar requisitos de visa |

---

## Features

- [x] Busqueda de vuelos (Duffel API)
- [x] Busqueda de hoteles (LiteAPI)
- [x] Reservacion de vuelos con PNR
- [x] Reservacion de hoteles
- [x] Ver itinerario de viajes proximos
- [x] Historial de viajes pasados
- [x] Informacion de equipaje adicional
- [x] Check-in automatico
- [x] Verificacion de requisitos de visa
- [x] Notificaciones push por WhatsApp
- [x] Scheduler para tareas en background
- [x] AI conversacional con GPT-4o

---

## Tech Stack

**Frontend:**
- React 18 + TypeScript
- Vite
- TailwindCSS
- Vercel (deployment)

**Backend:**
- FastAPI (Python)
- PostgreSQL + SQLAlchemy
- APScheduler (background jobs)
- Render (deployment)

**APIs:**
- Duffel (vuelos)
- LiteAPI (hoteles)
- OpenAI GPT-4o (AI)
- Meta WhatsApp Business API
- Stripe (pagos)

---

## Desarrollo Local

### Backend
```bash
cd /path/to/Biajez
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

**URLs locales:**
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Variables de Entorno

### Backend (.env)
```bash
DATABASE_URL=postgresql://user:pass@host/db
DUFFEL_ACCESS_TOKEN=duffel_test_xxx
OPENAI_API_KEY=sk-xxx
LITEAPI_API_KEY=sand_xxx
WHATSAPP_ACCESS_TOKEN=xxx
WHATSAPP_PHONE_NUMBER_ID=xxx
WHATSAPP_VERIFY_TOKEN=xxx
```

### Frontend (.env.production)
```bash
VITE_API_URL=https://biajez-ah0g.onrender.com
```

---

## Deployment

### Backend (Render)
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`

### Frontend (Vercel)
- Root: `frontend`
- Build: `npm run build`
- Output: `dist`

### WhatsApp Webhook
- URL: `https://biajez-ah0g.onrender.com/whatsapp/webhook`
- Verify Token: configurado en WHATSAPP_VERIFY_TOKEN
- Eventos: `messages`

---

## Estructura del Proyecto

```
Biajez/
├── app/
│   ├── api/           # Endpoints (routes, webhooks, whatsapp)
│   ├── ai/            # Agente AI con tools
│   ├── db/            # Database config
│   ├── models/        # SQLAlchemy models
│   └── services/      # Business logic
├── frontend/          # React app
├── tickets/           # Tickets HTML generados
├── requirements.txt
├── Procfile
└── render.yaml
```

---

## Documentacion Adicional

- `DEPLOYMENT.md` - Guia de deployment completa
- `SISTEMA_COMPLETO.md` - Estado del sistema
- `TESTING_GUIDE.md` - Guia de pruebas

---

## Contacto

WhatsApp: +52 1 56 5186 1011
