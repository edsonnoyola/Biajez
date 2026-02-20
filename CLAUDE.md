# Biajez - Instrucciones para Claude Code

## Que es Biajez
Agente de viajes por WhatsApp. El usuario manda mensajes a WhatsApp, el bot busca vuelos/hoteles, muestra opciones, y reserva con Duffel API. Todo en espanol MX.

## Stack
- **Backend:** FastAPI 0.124 + Python 3.11 + Uvicorn
- **DB:** PostgreSQL (Render prod), SQLite (local dev)
- **ORM:** SQLAlchemy 2.0 (raw SQL para operaciones criticas en Render)
- **AI:** OpenAI GPT-4o para conversacion natural
- **APIs:** Duffel (vuelos + hoteles), Stripe (pagos), Meta WhatsApp Business API
- **Frontend:** React 19 + TypeScript + Vite + Tailwind (en /frontend)
- **Deploy:** Render (biajez-d08x.onrender.com)
- **Cache:** Redis (sesiones WhatsApp), in-memory fallback

## Estructura

### Backend (app/)
```
app/
  main.py                    # FastAPI app, migrations, routers, scheduler
  config.py                  # Environment validation
  db/database.py             # SQLAlchemy engine + SessionLocal
  models/models.py           # Todas las tablas ORM
  api/
    whatsapp_meta.py         # ARCHIVO PRINCIPAL - Webhook WhatsApp Meta (3500+ lineas)
    routes.py                # API REST: search, book, profile, history
    webhooks.py              # Duffel webhook receiver
    flight_changes.py        # Cambios de vuelo post-booking
    hotel_cancellations.py   # Cancelaciones de hotel
    baggage.py               # Equipaje post-booking
    itinerary.py             # Itinerario completo
    checkin.py               # Auto check-in
    loyalty.py               # Programas de viajero frecuente
    ancillary.py             # Servicios adicionales (comida, wifi)
    hold_orders.py           # Reservar sin pagar
    price_alerts.py          # Alertas de precio
    order_endpoints.py       # Historial de ordenes
  services/
    flight_engine.py         # Busqueda de vuelos multi-proveedor (Duffel principal)
    booking_execution.py     # Ejecutar reservas (vuelos + hoteles)
    duffel_stays.py          # Duffel Stays API (4 pasos: search > rates > quote > book)
    order_management.py      # Ver/cancelar ordenes Duffel
    order_change_service.py  # Cambiar vuelos (4 pasos Duffel)
    hold_order_service.py    # Apartar vuelos sin pagar
    baggage_service.py       # Agregar maletas post-booking
    seat_selection_service.py # Elegir asientos
    checkin_service.py       # Auto check-in + recordatorios
    loyalty_service.py       # Millas/viajero frecuente
    ancillary_service.py     # Servicios adicionales
    airline_credits_service.py # Creditos de aerolinea
    email_service.py         # Emails HTML via Resend
    push_notification_service.py # Notificaciones proactivas WhatsApp
    ticket_generator.py      # Generar HTML tickets
    profile_manager.py       # CRUD perfiles
    payment_service.py       # Stripe pagos
    scheduler_service.py     # APScheduler cron jobs
    webhook_service.py       # Procesar webhooks Duffel
    conversation_manager.py  # Estado de conversacion WhatsApp
    whatsapp_redis.py        # Redis session manager
    visa_service.py          # Requisitos de visa
    weather_service.py       # Clima del destino
    price_alert_service.py   # Monitoreo de precios
    currency_service.py      # Tipo de cambio
    flight_status_service.py # Status de vuelo en tiempo real
    hotel_engine.py          # Busqueda hoteles multi-proveedor
    liteapi_hotels.py        # LiteAPI hoteles
    batch_search_service.py  # Busqueda batch
    travelpayouts_flights.py # Travelpayouts API
```

### Base de datos (tablas principales)
- `profiles` - Usuarios (nombre legal, pasaporte, DOB, telefono, email)
- `trips` - Reservas (PNR, duffel_order_id, status, montos, ciudades, fechas)
- `payments` - Pagos Stripe
- `loyalty_programs` - Numeros de viajero frecuente
- `airline_credits` - Creditos de aerolinea por cancelaciones
- `notifications` - Notificaciones
- `webhook_events` - Eventos Duffel
- `auto_checkins` - Check-ins automaticos programados
- `price_alerts` - Alertas de precio activas
- `booking_errors` - Log de errores de reserva

## Duffel API (proveedor principal)

### Headers requeridos en TODAS las llamadas:
```python
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
    "Duffel-Version": "v2"
}
```

### Flujos implementados:
1. **Buscar vuelos:** POST /air/offer_requests → GET /air/offers
2. **Reservar vuelo:** POST /air/orders (type: instant, payment: balance)
3. **Cancelar:** POST /air/order_cancellations → POST .../confirm
4. **Cambiar vuelo:** POST /air/order_change_requests → select offer → POST /air/order_changes (pending) → POST .../confirm
5. **Equipaje post-booking:** GET /air/orders/{id}/available_services → POST /air/orders/{id}/services
6. **Hold orders:** POST /air/orders (type: hold, sin payments) → POST /air/payments
7. **Stays (hoteles):** POST /stays/search → GET .../rates → POST /stays/quotes → POST /stays/bookings

### Status codes:
- POST endpoints pueden devolver 200 O 201 - siempre aceptar ambos

## Convenciones

### Idioma
- **TODO en espanol MX** - mensajes, errores, UI
- Nunca exponer JSON crudo, stack traces, o mensajes en ingles al usuario
- Errores al usuario: mensajes limpios y amigables en espanol
- Errores tecnicos: solo en `print()` para logs del servidor

### WhatsApp (archivo principal: whatsapp_meta.py)
- Formateo con markdown de WhatsApp: *bold*, _italic_, ```code```
- Emojis para visual (✅ ❌ ✈️ 🏨 💰 📅 🎫)
- Mensajes concisos - WhatsApp tiene limite de ~4000 chars
- Botones interactivos via `send_interactive_message()` (max 3 botones)
- Sesion en Redis con `session_manager.save_session()`

### Base de datos
- Raw SQL para operaciones criticas (`save_trip_sql()`, queries en whatsapp_meta.py)
- ORM para lecturas simples (`db.query(Trip).filter(...)`)
- Siempre `conn.commit()` despues de write con raw SQL
- No usar `created_at` en trips (no existe) - usar `departure_date` o `confirmed_at`

### Errores
- NUNCA enviar `resp.text`, `str(e)`, o JSON de APIs al WhatsApp del usuario
- Siempre: `print(f"ERROR: {detalles}")` + mensaje limpio al usuario
- Patron correcto:
```python
if resp.status_code not in [200, 201]:
    print(f"Error: {resp.status_code} - {resp.text[:300]}")
    send_whatsapp_message(from_number, "No se pudo completar. Intenta de nuevo.")
```

## Environment Variables
```
DUFFEL_ACCESS_TOKEN      # Duffel API (vuelos + hoteles)
OPENAI_API_KEY           # GPT-4o
WHATSAPP_ACCESS_TOKEN    # Meta WhatsApp Business API
WHATSAPP_PHONE_NUMBER_ID # Meta phone number ID
WHATSAPP_VERIFY_TOKEN    # Webhook verification
DATABASE_URL             # PostgreSQL (Render)
REDIS_URL                # Redis sessions
STRIPE_SECRET_KEY        # Pagos
RESEND_API_KEY           # Emails
AMADEUS_API_KEY          # Busqueda alternativa
AMADEUS_API_SECRET       # Busqueda alternativa
LITEAPI_API_KEY          # Hoteles alternativa
BASE_URL                 # https://biajez-d08x.onrender.com
```

## Scheduler (cron jobs)
- `process_auto_checkins` - cada 15 min
- `check_price_alerts` - cada 6 horas
- `refresh_visa_cache` - diario 3 AM
- `send_trip_reminders` - diario 8 AM

## Registro de perfil (9 pasos via WhatsApp)
1. Nombre completo (legal)
2. Email
3. Fecha nacimiento
4. Género (M/F)
5. Pasaporte (opcional: número, país, vencimiento)
6. Global Entry / TSA PreCheck - KTN (opcional)
7. Aerolínea preferida (opcional, código IATA)
8. Asiento preferido (ventana/pasillo/cualquiera)
9. Clase preferida (economy/business/primera)

Campos editables post-registro: `cambiar asiento ventana`, `cambiar clase business`, `cambiar aerolinea AM`, `cambiar ktn 12345`

Al reservar, booking_execution.py envía a Duffel: pasaporte, KTN, loyalty programs (match por aerolínea), datos personales.

## Notas importantes
- Tickets HTML se guardan en DB (ticket_html column en trips) + cache en memoria
- Hotel booking via WhatsApp usa flujo completo Duffel Stays (search > rates > quote > book)
- booking_execution.py `_book_hotel()` tiene legacy Amadeus code (solo se usa para MOCK hotels de prueba)
- Siempre aceptar status 200 Y 201 en POST requests a Duffel
- Solo vuelos flexibles (cambiables o cancelables) se muestran al usuario
