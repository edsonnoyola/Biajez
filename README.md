# Biajez - Asistente de Viajes por WhatsApp

Bot de WhatsApp con IA conversacional para buscar, reservar y gestionar vuelos y hoteles. Integrado con Duffel (vuelos LIVE), LiteAPI (hoteles), OpenAI GPT-4o y Meta WhatsApp Business API.

## URLs de Produccion

| Servicio | URL |
|----------|-----|
| Backend API | https://biajez-d08x.onrender.com |
| API Docs | https://biajez-d08x.onrender.com/docs |
| Health | https://biajez-d08x.onrender.com/health |
| Frontend | https://biajez-d08x.onrender.com (React SPA) |
| WhatsApp Bot | Configurado via Meta Business Suite |
| WhatsApp Webhook | https://biajez-d08x.onrender.com/v1/whatsapp/webhook |

---

## Comandos de WhatsApp

### Buscar Vuelos
| Ejemplo | Descripcion |
|---------|-------------|
| `vuelo de MEX a MIA el 15 de febrero` | Ida simple |
| `vuelo MEX a CUN del 10 al 15 de marzo` | Ida y vuelta |
| `vuelo MEX a MIA por American Airlines` | Filtro por aerolinea |
| `vuelo SDQ a JFK en la manana` | Filtro por horario |
| `vuelo MEX a MAD en business` | Filtro por clase |
| `vuelo MEX a MIA el 1 marzo, luego MIA a MAD el 5` | Multi-destino |

### Buscar Hoteles
| Ejemplo | Descripcion |
|---------|-------------|
| `hotel en Cancun del 20 al 25 febrero` | Busqueda basica |
| `hoteles en CDMX` | Pide fechas automaticamente |

### Gestion de Viajes
| Comando | Descripcion |
|---------|-------------|
| `itinerario` | Ver proximo viaje con detalles |
| `historial` | Ver viajes pasados |
| `mis vuelos` / `mis reservas` | Ver reservas activas |
| `equipaje` | Opciones de equipaje adicional |
| `checkin` | Status de check-in |
| `auto checkin` | Programar recordatorio de check-in |
| `cancelar vuelo` | Cancelar reserva con reembolso |
| `cambiar vuelo` | Buscar opciones de cambio |

### Otros Servicios
| Comando | Descripcion |
|---------|-------------|
| `visa US` | Verificar requisitos de visa |
| `alertas` | Ver alertas de precio activas |
| `crear alerta` | Crear alerta (despues de buscar) |
| `millas` | Ver programas de viajero frecuente |
| `registrar` | Registrar/actualizar perfil |
| `mi perfil` | Ver perfil y preferencias |
| `ayuda` | Menu de ayuda completo |
| `reset` | Limpiar sesion |

---

## Features Implementadas

### Vuelos (Duffel LIVE)
- [x] Busqueda con precios reales y PNR reales
- [x] Filtro por aerolinea (AA, AM, DL, UA, AV, CM, IB, Y4, VB, B6)
- [x] Filtro por horario (MORNING, AFTERNOON, EVENING, NIGHT)
- [x] Filtro por clase (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
- [x] Vuelos ida y vuelta
- [x] Multi-destino (2-3 tramos)
- [x] Reservacion con PNR real via Duffel
- [x] Multiples pasajeros (1-9)
- [x] Condiciones de cambio/reembolso visibles en resultados
- [x] Best practices Duffel: max_connections, departure_time, supplier_timeout
- [x] Fallback de filtros (detecta del mensaje si AI no los pasa)

### Gestion de Ordenes (Duffel)
- [x] Cancelacion con reembolso real
- [x] Cambio de vuelo (buscar opciones + confirmar)
- [x] Hold orders (reserva temporal)
- [x] Seleccion de asientos
- [x] Equipaje adicional
- [x] E-ticket HTML generado al reservar

### Webhooks (Duffel)
- [x] Cambios iniciados por aerolinea (order.airline_initiated_change)
- [x] Cancelaciones confirmadas (order.cancelled)
- [x] Cambios confirmados (order.changed)
- [x] Pagos fallidos (payment.failed)
- [x] Verificacion de firma HMAC-SHA256
- [x] Registro de eventos en DB

### Notificaciones
- [x] Email de confirmacion de reserva (HTML completo con segmentos)
- [x] Email de cancelacion con monto de reembolso
- [x] Email de cambio de vuelo confirmado
- [x] Email de alerta por cambio de aerolinea
- [x] WhatsApp push: confirmacion de reserva
- [x] WhatsApp push: cancelacion
- [x] WhatsApp push: cambio confirmado
- [x] WhatsApp push: cambio por aerolinea

### Hoteles
- [x] Busqueda con LiteAPI (sandbox)
- [x] Duffel Stays (sandbox)
- [x] Reservacion de hotel
- [x] Cancelacion de hotel

### Servicios Adicionales
- [x] Verificacion de visa por pais
- [x] Alertas de precio (notifica cuando baja)
- [x] Check-in automatico con recordatorio
- [x] Programa de millas/viajero frecuente
- [x] Registro conversacional por WhatsApp
- [x] AI conversacional con GPT-4o + function calling
- [x] Sesiones Redis (persistentes entre mensajes)

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
- FastAPI + Python 3.11+
- SQLAlchemy + PostgreSQL (Render) / SQLite (local)
- APScheduler (background jobs)
- Redis (sesiones WhatsApp)
- Render (deployment con auto-deploy desde GitHub)

**APIs Integradas:**
- Duffel v2 (vuelos LIVE + webhooks + ordenes)
- LiteAPI (hoteles sandbox)
- Amadeus (flight search alternativo)
- OpenAI GPT-4o (AI agent con function calling)
- Meta WhatsApp Business API v18.0
- Stripe (pagos)
- Resend (emails transaccionales)

**Frontend:**
- React 18 + TypeScript
- Vite + Tailwind CSS
- SPA con modales (sin rutas)

---

## Estructura del Proyecto

```
Biajez/
├── app/
│   ├── main.py                    # FastAPI app + routers + admin endpoints
│   ├── api/                       # 16 endpoint files
│   │   ├── whatsapp_meta.py       # Meta WhatsApp webhook (ACTIVO)
│   │   ├── whatsapp_handler.py    # Twilio WhatsApp (deshabilitado)
│   │   ├── routes.py              # API REST principal
│   │   ├── webhooks.py            # Duffel webhooks
│   │   ├── flight_changes.py      # Cambios de vuelo
│   │   ├── order_endpoints.py     # Gestion de ordenes
│   │   ├── hotel_routes.py        # Hoteles
│   │   ├── hotel_cancellations.py # Cancelacion hoteles
│   │   ├── hold_orders.py         # Hold orders
│   │   ├── baggage.py             # Equipaje
│   │   ├── itinerary.py           # Itinerarios
│   │   ├── visa.py                # Visa
│   │   ├── checkin.py             # Check-in
│   │   ├── loyalty.py             # Viajero frecuente
│   │   ├── ancillary.py           # Servicios adicionales
│   │   └── price_alerts.py        # Alertas de precio
│   ├── ai/
│   │   └── agent.py               # AI Agent (GPT-4o + LangChain)
│   ├── db/
│   │   └── database.py            # SQLAlchemy config
│   ├── models/
│   │   └── models.py              # Modelos DB (Profile, Trip, Payment, etc.)
│   ├── services/                  # 31 service files
│   │   ├── flight_engine.py       # Motor de busqueda (Duffel + Amadeus)
│   │   ├── booking_execution.py   # Orquestador de reservas
│   │   ├── order_management.py    # Cancelaciones
│   │   ├── order_change_service.py # Cambios de vuelo
│   │   ├── webhook_service.py     # Procesamiento de webhooks
│   │   ├── email_service.py       # Emails via Resend (5 templates)
│   │   ├── push_notification_service.py # WhatsApp push
│   │   ├── whatsapp_redis.py      # Sesiones Redis
│   │   ├── ticket_generator.py    # E-ticket HTML
│   │   ├── seat_selection_service.py # Seleccion de asientos
│   │   ├── hotel_engine.py        # Motor de hoteles
│   │   ├── liteapi_hotels.py      # LiteAPI
│   │   ├── duffel_stays.py        # Duffel Stays
│   │   ├── payment_service.py     # Stripe
│   │   ├── scheduler_service.py   # APScheduler
│   │   ├── baggage_service.py     # Equipaje
│   │   ├── checkin_service.py     # Check-in
│   │   ├── visa_service.py        # Visa
│   │   ├── price_alert_service.py # Alertas
│   │   ├── itinerary_service.py   # Itinerarios
│   │   ├── loyalty_service.py     # Millas
│   │   ├── profile_manager.py     # Perfiles
│   │   ├── conversation_manager.py # Conversaciones
│   │   ├── ancillary_service.py   # Servicios extras
│   │   ├── hold_order_service.py  # Hold orders
│   │   ├── batch_search_service.py # Busqueda batch
│   │   ├── currency_service.py    # Conversiones
│   │   ├── flight_status_service.py # Status vuelo
│   │   ├── airline_credits_service.py # Creditos
│   │   ├── weather_service.py     # Clima
│   │   └── travelpayouts_flights.py # Travelpayouts
│   └── utils/
│       ├── date_parser.py         # Parser de fechas en espanol
│       ├── encryption.py          # Encriptacion
│       └── error_handler.py       # Manejo de errores
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # App principal
│   │   ├── components/            # 28 componentes React
│   │   └── config/api.ts          # URL de API
│   └── .env.production            # VITE_API_URL
├── requirements.txt
├── Procfile
├── render.yaml
├── SISTEMA_COMPLETO.md
├── DEPLOYMENT.md
├── TESTING_GUIDE.md
└── PRODUCTION_TOKENS.md
```

---

## Desarrollo Local

```bash
# Clonar e instalar
git clone https://github.com/edsonnoyola/Biajez.git
cd Biajez
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar .env
cp .env.production .env  # O crear desde cero

# Ejecutar backend
uvicorn app.main:app --reload --port 8000

# Ejecutar frontend
cd frontend
npm install
npm run dev
```

**URLs locales:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Scheduler: http://localhost:8000/scheduler/status

---

## Variables de Entorno

```bash
# Vuelos (Duffel)
DUFFEL_ACCESS_TOKEN=duffel_live_xxx
DUFFEL_WEBHOOK_SECRET=whsec_xxx

# Vuelos (Amadeus)
AMADEUS_CLIENT_ID=xxx
AMADEUS_CLIENT_SECRET=xxx

# Hoteles (LiteAPI)
LITEAPI_API_KEY=sand_xxx

# AI
OPENAI_API_KEY=sk-xxx

# WhatsApp (Meta)
WHATSAPP_ACCESS_TOKEN=xxx
WHATSAPP_PHONE_NUMBER_ID=xxx
WHATSAPP_VERIFY_TOKEN=xxx

# Database
DATABASE_URL=postgresql://xxx  # o sqlite:///./biajez.db

# Cache
REDIS_URL=redis://xxx

# Email
RESEND_API_KEY=re_xxx
BASE_URL=https://biajez-d08x.onrender.com

# Pagos
STRIPE_SECRET_KEY=sk_test_xxx

# Admin
ADMIN_SECRET=xxx
```

---

## Admin Endpoints

Todos requieren `?secret=ADMIN_SECRET`

| Endpoint | Descripcion |
|----------|-------------|
| `GET /health` | Health check |
| `GET /admin/health` | Health check con info de sistema |
| `GET /admin/profiles?secret=X` | Listar perfiles |
| `GET /admin/profile/{phone}?secret=X` | Perfil por telefono |
| `GET /admin/profile-by-userid/{uid}?secret=X` | Perfil por user_id |
| `GET /admin/session/{phone}?secret=X` | Ver sesion Redis |
| `GET /admin/redis-status?secret=X` | Estado de Redis |
| `GET /admin/list-trips?secret=X` | Listar viajes |
| `GET /admin/booking-errors?secret=X` | Errores de booking |
| `GET /admin/webhook-log?secret=X` | Log de webhooks |
| `POST /admin/clear-session/{phone}?secret=X` | Limpiar sesion |
| `POST /admin/fix-db?secret=X` | Agregar columnas faltantes |
| `POST /admin/restart?secret=X` | Reiniciar servidor |
| `GET /admin/send-test?secret=X&phone=Y` | Enviar WhatsApp de prueba |

---

## Deployment (Render)

- **Repo:** edsonnoyola/Biajez (publico)
- **Branch:** main (auto-deploy)
- **URL:** https://biajez-d08x.onrender.com
- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**WhatsApp Webhook:**
- URL: `https://biajez-d08x.onrender.com/v1/whatsapp/webhook`
- Verify Token: configurado en Meta Business Suite
- Eventos: `messages`

**Duffel Webhooks:**
- URL: `https://biajez-d08x.onrender.com/webhooks/duffel`
- Eventos: order.airline_initiated_change, order.cancelled, order.changed, payment.failed

---

## Documentacion

| Archivo | Contenido |
|---------|-----------|
| `README.md` | Este archivo - overview completo |
| `SISTEMA_COMPLETO.md` | Memoria de sesion y estado del sistema |
| `DEPLOYMENT.md` | Guia de deployment |
| `TESTING_GUIDE.md` | Guia de pruebas |
| `PRODUCTION_TOKENS.md` | Tokens de produccion |
| `STRIPE_SETUP.md` | Configuracion de pagos |

---

**Ultima actualizacion: 2026-02-20**
**Desarrollado con Claude Code**
