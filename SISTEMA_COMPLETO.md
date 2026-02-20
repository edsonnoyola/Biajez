# Sistema Biajez - Memoria de Sesion

## ARCHIVO A LEER AL INICIO DE CADA SESION

---

## ESTADO: 100% FUNCIONAL Y VERIFICADO

### Modo de Operacion
- **Vuelos:** Duffel LIVE (precios reales, PNR reales)
- **Hoteles:** LiteAPI Sandbox
- **WhatsApp:** Meta Business API v18.0 (webhook en Render)
- **AI:** OpenAI GPT-4o con function calling + LangChain
- **Backend:** FastAPI en Render (https://biajez-d08x.onrender.com)
- **Frontend:** React + Vite + TypeScript
- **Sesiones:** Redis (persistentes entre mensajes)
- **Emails:** Resend (confirmaciones, cancelaciones, cambios)

---

## Resumen de Sesiones Recientes

### Sesion 2026-02-20 (Duffel Best Practices + WhatsApp)

**Cambios realizados:**

1. **Emails y Notificaciones** (commit c10241a)
   - Reescrito email_service.py con 5 templates HTML en espanol
   - Wired WhatsApp push en booking, cancelacion, cambio, y webhooks
   - Configurado RESEND_API_KEY y BASE_URL en Render

2. **Duffel Search Best Practices** (commit 05fbdad)
   - `return_offers=true` para respuestas mas rapidas
   - `supplier_timeout=20000` para timeout controlado
   - `max_connections=1` para limitar escalas
   - `departure_time` filter nativo (no solo post-filter)
   - `Accept-Encoding: gzip` header

3. **Condiciones en WhatsApp** (commit 09272d7)
   - Resultados de vuelo ahora muestran: aerolinea, numero de vuelo, escalas
   - Condiciones de cambio (Cambio gratis / Cambio: $X / Sin cambios)
   - Condiciones de reembolso (Reembolsable)

4. **URLs de produccion fijadas**
   - TicketCard.tsx: localhost:8000 → API_URL dinamico
   - frontend/.env.production: biajez.onrender.com → biajez-d08x.onrender.com

### Sesion 2026-02-09 (Webhooks + Cancelacion + Cambios)

1. **Duffel Webhooks** implementados y verificados (ping OK)
2. **Cancelacion de vuelo** con reembolso real
3. **Cambio de vuelo** con busqueda de opciones + confirmacion
4. **Fix booking amount** (pasaba 0 a Duffel)

### Sesion 2026-02-04 (Migracion Render)

1. **Migracion** a nuevo servicio Render (biajez-d08x)
2. **Fix API keys** con saltos de linea
3. **Fix OpenAI** key expirada
4. **Fix AI** que preguntaba cosas obvias ("del X al Y" = ida y vuelta)

### Sesion 2026-02-03 (Filtros)

1. **Fix filtros fallback** para time_of_day y cabin
2. **Reserva verificada:** PNR ZGV351, AA 2099 SDQ→MIA

---

## Features Implementadas

### Vuelos
- [x] Busqueda Duffel LIVE con precios reales
- [x] Filtro por aerolinea (AA, AM, DL, UA, AV, CM, IB, Y4, VB, B6)
- [x] Filtro por horario (MORNING, AFTERNOON, EVENING, NIGHT)
- [x] Filtro por clase (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
- [x] Vuelos ida y vuelta
- [x] Multi-destino (2-3 tramos)
- [x] Reservacion con PNR real
- [x] Multiples pasajeros
- [x] Fallback de filtros del mensaje
- [x] Condiciones de cambio/reembolso en resultados
- [x] Duffel search best practices (max_connections, supplier_timeout, departure_time)

### Gestion de Ordenes
- [x] Cancelacion con reembolso via Duffel
- [x] Cambio de vuelo (buscar + confirmar)
- [x] Hold orders
- [x] Seleccion de asientos
- [x] Equipaje adicional
- [x] E-ticket HTML

### Webhooks Duffel
- [x] order.airline_initiated_change
- [x] order.cancelled
- [x] order.changed
- [x] payment.failed
- [x] Verificacion HMAC-SHA256
- [x] Notificacion automatica WhatsApp + Email

### Notificaciones
- [x] 5 templates de email HTML (Resend)
- [x] WhatsApp push en todos los eventos
- [x] Formato WhatsApp con condiciones de vuelo

### Hoteles
- [x] LiteAPI (sandbox)
- [x] Duffel Stays (sandbox)

### Servicios
- [x] Visa, Alertas, Check-in, Millas, Itinerario, Historial
- [x] Registro conversacional por WhatsApp
- [x] Sesiones Redis persistentes

---

## Formato WhatsApp de Vuelos

Ejemplo de como se ven los resultados en WhatsApp:
```
✈️ *Vuelos encontrados:*

*1.* $245 USD
   AA1234 08:30 MEX→CUN
   Directo | Cambio gratis | Reembolsable

*2.* $189 USD
   VB456 14:15 MEX→CUN
   Directo | Sin cambios

*3.* $310 USD
   AM789 19:00 MEX→CUN
   1 escala | Cambio: $50

Responde con el numero para reservar
```

---

## Sistema de Filtros

### Horario (time_of_day)
| Filtro | Horas | Palabras clave |
|--------|-------|----------------|
| MORNING | 6am-12pm | manana, temprano |
| AFTERNOON | 12pm-6pm | tarde, mediodia |
| EVENING | 6pm-10pm | noche, nocturno |
| NIGHT | 10pm-6am | muy tarde, red eye, madrugada |

### Clase de Cabina
| Filtro | Palabras clave |
|--------|----------------|
| ECONOMY | economica, turista |
| PREMIUM_ECONOMY | premium |
| BUSINESS | business, ejecutiva |
| FIRST | primera, first class |

### Aerolinea
| Codigo | Aerolinea |
|--------|-----------|
| AA | American Airlines |
| AM | Aeromexico |
| DL | Delta |
| UA | United |
| AV | Avianca |
| CM | Copa |
| IB | Iberia |
| Y4 | Volaris |
| VB | VivaAerobus |
| B6 | JetBlue |

---

## APIs y Tokens

| API | Estado | Modo | Variable |
|-----|--------|------|----------|
| Duffel | OK | LIVE | DUFFEL_ACCESS_TOKEN |
| Duffel Webhooks | OK | LIVE | DUFFEL_WEBHOOK_SECRET (pendiente en Render) |
| LiteAPI | OK | Sandbox | LITEAPI_API_KEY |
| OpenAI | OK | Production | OPENAI_API_KEY |
| WhatsApp | OK | Production | WHATSAPP_ACCESS_TOKEN |
| Stripe | OK | Test | STRIPE_SECRET_KEY |
| Resend | OK | Production | RESEND_API_KEY |
| Redis | OK | Production | REDIS_URL |

---

## Deployment

### Render (Backend)
- URL: https://biajez-d08x.onrender.com
- Repo: edsonnoyola/Biajez (publico)
- Auto-deploy desde GitHub (main branch)

### WhatsApp Webhook
- URL: https://biajez-d08x.onrender.com/v1/whatsapp/webhook
- Configurado en Meta Business Suite

### Frontend
- .env.production: VITE_API_URL=https://biajez-d08x.onrender.com

---

## Archivos Clave

```
app/api/whatsapp_meta.py       # WhatsApp webhook principal + fallback filters
app/ai/agent.py                # AI con tools (GPT-4o + LangChain)
app/services/flight_engine.py  # Motor de busqueda (Duffel + Amadeus)
app/services/booking_execution.py   # Orquestador de reservas
app/services/order_management.py    # Cancelaciones
app/services/order_change_service.py # Cambios de vuelo
app/services/webhook_service.py     # Procesamiento de webhooks Duffel
app/services/email_service.py       # 5 templates email HTML (Resend)
app/services/push_notification_service.py # WhatsApp push
app/services/whatsapp_redis.py      # Sesiones Redis
app/api/whatsapp_handler.py         # WhatsApp Twilio (deshabilitado)
```

---

## Commits Recientes

```
09272d7 Show flight conditions (change/refund) in WhatsApp search results
05fbdad Apply Duffel search best practices: max_connections, departure_time, supplier_timeout
c10241a Add booking confirmation emails, WhatsApp notifications, and fix production URLs
3a65894 Add cancellation webhook handlers and fix event type names
3a87211 Fix Duffel webhooks: signature verification, event parsing, and admin registration
8b48d6c Fix flight change flow: payment amount, departure_date, session cleanup
679fcb3 Fix 3 critical production bugs: booking amount, cancellation, and AI agent
8541492 Only show changeable flights, extract Duffel conditions, fix ticket URL
```

---

## Pendiente

- [ ] DUFFEL_WEBHOOK_SECRET en Render env vars (webhook signature skip en prod)
- [ ] LiteAPI produccion (requiere fondeo)
- [ ] Stripe pagos en produccion
- [ ] Deploy frontend a dominio propio
- [ ] Amadeus cuenta nueva (opcional, Duffel es principal)

---

## Notas para Proxima Sesion

1. **Leer este archivo primero** (`SISTEMA_COMPLETO.md`)
2. El fix de filtros esta en `app/api/whatsapp_meta.py`
3. El backend se inicia con: `source .venv/bin/activate && uvicorn app.main:app --port 8000`
4. Para WhatsApp: todo funciona, formato mejorado con condiciones
5. Email service tiene 5 templates: booking, cancelacion, cambio, cambio aerolinea, hotel

---

**Ultima actualizacion: 2026-02-20**
**Sistema 100% operacional**
**URL: https://biajez-d08x.onrender.com**
