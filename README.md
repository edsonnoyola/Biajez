# Biajez - Tu Asistente de Viajes por WhatsApp

Bot de WhatsApp con IA conversacional para buscar y reservar vuelos y hoteles.

## URLs de Produccion

| Servicio | URL |
|----------|-----|
| Backend API | https://biajez.onrender.com |
| API Docs | https://biajez.onrender.com/docs |
| WhatsApp Bot | Configurado via Meta Business |

---

## Comandos de WhatsApp

### Vuelos y Hoteles
| Comando | Ejemplo |
|---------|---------|
| Buscar vuelo | `vuelo de MEX a MIA el 15 de febrero` |
| Con aerolinea | `vuelo MEX a MIA por American Airlines` |
| En la manana | `vuelo SDQ a JFK en la manana` |
| Clase business | `vuelo MEX a MAD en business` |
| Redondo | `vuelo MEX a CUN del 10 al 15 de marzo` |
| Multi-destino | `vuelo MEX a MIA el 1 de marzo, luego MIA a MAD el 5` |
| Hoteles | `hotel en Cancun del 20 al 25 de febrero` |

### Mis Viajes
| Comando | Descripcion |
|---------|-------------|
| `itinerario` | Ver proximo viaje con detalles |
| `historial` | Ver viajes pasados |
| `equipaje` | Opciones de equipaje adicional |
| `checkin` | Status de check-in |
| `auto checkin` | Programar recordatorio de check-in |

### Otros Servicios
| Comando | Descripcion |
|---------|-------------|
| `visa US` | Verificar requisitos de visa |
| `alertas` | Ver alertas de precio activas |
| `crear alerta` | Crear alerta (despues de buscar) |
| `ayuda` | Menu de ayuda completo |

---

## Features Implementadas

- [x] Busqueda de vuelos (Duffel LIVE)
- [x] Busqueda de hoteles (LiteAPI/Duffel Stays)
- [x] Filtros: aerolinea, horario, clase cabin
- [x] Vuelos multi-destino (2-3 tramos)
- [x] Reservacion con PNR real
- [x] Itinerario de viajes proximos
- [x] Historial de viajes pasados
- [x] Equipaje adicional via Duffel
- [x] Check-in automatico con recordatorio
- [x] Verificacion de requisitos de visa
- [x] Alertas de precio (notifica cuando baja)
- [x] Notificaciones push por WhatsApp
- [x] Background scheduler (APScheduler)
- [x] AI conversacional con GPT-4o

---

## Scheduler Jobs

| Job | Frecuencia | Funcion |
|-----|------------|---------|
| `process_auto_checkins` | 15 min | Check-ins pendientes |
| `check_price_alerts` | 6 horas | Verificar precios y notificar |
| `refresh_visa_cache` | 3 AM | Actualizar cache de visa |
| `send_trip_reminders` | 8 AM | Recordatorios de viaje |

---

## Tech Stack

**Backend:**
- FastAPI (Python 3.11+)
- SQLAlchemy + SQLite/PostgreSQL
- APScheduler (background jobs)
- Redis (sessions, opcional)
- Render (deployment)

**APIs Integradas:**
- Duffel (vuelos - LIVE)
- LiteAPI (hoteles - sandbox)
- OpenAI GPT-4o (AI)
- Meta WhatsApp Business API
- Stripe (pagos)

---

## Desarrollo Local

```bash
# Clonar e instalar
git clone https://github.com/edsonnoyola/Biajez.git
cd Biajez
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar .env (ver .env.example)
cp .env.example .env

# Ejecutar
uvicorn app.main:app --reload --port 8000
```

**URLs locales:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Scheduler Status: http://localhost:8000/scheduler/status

---

## Variables de Entorno

```bash
# APIs de Vuelos/Hoteles
DUFFEL_ACCESS_TOKEN=duffel_live_xxx
LITEAPI_API_KEY=sand_xxx
AMADEUS_CLIENT_ID=xxx
AMADEUS_CLIENT_SECRET=xxx

# AI
OPENAI_API_KEY=sk-xxx

# WhatsApp
WHATSAPP_ACCESS_TOKEN=xxx
WHATSAPP_PHONE_NUMBER_ID=xxx
WHATSAPP_VERIFY_TOKEN=xxx

# Database
DATABASE_URL=sqlite:///./antigravity.db

# Pagos (opcional)
STRIPE_SECRET_KEY=sk_test_xxx
```

---

## Estructura del Proyecto

```
Biajez/
├── app/
│   ├── api/              # Endpoints
│   │   ├── routes.py     # API REST
│   │   └── whatsapp_meta.py  # WhatsApp webhook
│   ├── ai/
│   │   └── agent.py      # AI Agent con tools
│   ├── db/
│   │   └── database.py   # SQLAlchemy config
│   ├── models/
│   │   └── models.py     # Modelos DB + DTOs
│   └── services/
│       ├── flight_engine.py    # Busqueda vuelos
│       ├── hotel_engine.py     # Busqueda hoteles
│       ├── booking_execution.py # Reservaciones
│       ├── itinerary_service.py # Itinerarios
│       ├── baggage_service.py   # Equipaje
│       ├── checkin_service.py   # Check-in
│       ├── visa_service.py      # Visa
│       ├── price_alert_service.py # Alertas
│       ├── scheduler_service.py  # Background jobs
│       └── push_notification_service.py # WhatsApp push
├── requirements.txt
├── Procfile
└── render.yaml
```

---

## Deployment (Render)

```yaml
# render.yaml
services:
  - type: web
    name: biajez
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**WhatsApp Webhook:**
- URL: `https://biajez.onrender.com/v1/whatsapp/webhook`
- Verify Token: configurado en `WHATSAPP_VERIFY_TOKEN`
- Eventos: `messages`

---

## Documentacion

| Archivo | Contenido |
|---------|-----------|
| `DEPLOYMENT.md` | Guia de deployment |
| `TESTING_GUIDE.md` | Guia de pruebas |
| `STRIPE_SETUP.md` | Configuracion de pagos |

---

## Autor

Desarrollado con Claude Code
