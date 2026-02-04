# Sistema Biajez - Memoria de Sesión

## ARCHIVO A LEER AL INICIO DE CADA SESIÓN
**Nombre:** `SISTEMA_COMPLETO.md`
**Ubicación:** `/Users/end/Downloads/Biajez/SISTEMA_COMPLETO.md`

---

## ESTADO: 100% FUNCIONAL Y VERIFICADO

### Modo de Operación
- **Vuelos:** Duffel LIVE (precios reales, PNR reales)
- **Hoteles:** LiteAPI Sandbox
- **WhatsApp:** Meta Business API (webhook en Render)
- **AI:** OpenAI GPT-4o con function calling
- **Backend:** FastAPI en Render (https://biajez.onrender.com)
- **Frontend:** React + Vite (localhost:5173 o Vercel)

---

## Resumen de Última Sesión (2026-02-03)

### Problema Principal Resuelto
**Bug:** Usuario pedía "vuelo en la noche en business" pero el sistema mostraba vuelos de todo el día (07:00, 11:01, 15:19) en lugar de solo vuelos nocturnos (18:00-22:00).

**Causa:** El AI reconocía la intención ("horarios nocturnos") pero NO pasaba `time_of_day="EVENING"` en los argumentos del tool call.

**Solución:** Agregué funciones fallback en `whatsapp_meta.py`:
```python
detect_time_of_day_from_text(msg)  # "en la noche" → EVENING
detect_cabin_from_text(msg)         # "business" → BUSINESS
```

### Verificación del Fix
```
Test: "vuelo MEX a MIA en la noche en business el 20 febrero"
AI Arguments: cabin=BUSINESS, time_of_day=EVENING ✅
Resultado: 122 ofertas → 2 vuelos filtrados (19:00) ✅
```

### Reserva Verificada contra Datos Reales
```
PNR: ZGV351 - $818.47 USD
AA 2099: SDQ→MIA 11:01→12:39
Verificado contra Airportia: Datos correctos ✅
```

---

## Features Implementadas

### Vuelos
- [x] Búsqueda con Duffel LIVE
- [x] Filtro por aerolínea (AA, CM, AM, DL, AV, etc.)
- [x] Filtro por horario (MORNING, AFTERNOON, EVENING, NIGHT)
- [x] Filtro por clase (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
- [x] Vuelos redondos (ida y vuelta)
- [x] Multi-destino (2-3 tramos)
- [x] Reservación con PNR real
- [x] Múltiples pasajeros (1-9)
- [x] **Fallback de filtros** (detecta filtros del mensaje si AI falla)

### Hoteles
- [x] Búsqueda con LiteAPI
- [x] Duffel Stays (sandbox)
- [x] Filtro por fechas
- [x] Reservación

### Gestión de Viajes
- [x] Itinerario (próximo viaje)
- [x] Historial (viajes pasados)
- [x] Equipaje adicional
- [x] Check-in automático
- [x] Recordatorio de check-in

### Servicios Adicionales
- [x] Verificación de visa
- [x] Alertas de precio
- [x] Notificaciones push WhatsApp
- [x] Background scheduler (APScheduler)
- [x] Millas/Viajero frecuente

---

## Comandos WhatsApp

### Vuelos
```
vuelo de MEX a MIA el 15 de febrero
vuelo MEX a MAD por Aeromexico
vuelo SDQ a JFK en la mañana
vuelo MEX a LAX en business
vuelo SDQ a MIA por AA en la noche en business
vuelo MEX a CUN del 10 al 15 marzo (redondo)
```

### Multi-destino
```
vuelo MEX a MIA el 1 marzo, luego MIA a MAD el 5
multicity MEX MIA MAD
```

### Hoteles
```
hotel en Cancun del 20 al 25 febrero
hoteles en CDMX
```

### Millas
```
millas
agregar millas AM 123456789
eliminar millas AM
```

### Servicios
```
itinerario
historial
equipaje
checkin
auto checkin
visa US
alertas
crear alerta
ayuda
```

---

## Sistema de Filtros

### Filtro por Horario (time_of_day)
| Filtro | Horas | Palabras clave |
|--------|-------|----------------|
| MORNING | 6am-12pm | mañana, temprano, en la mañana |
| AFTERNOON | 12pm-6pm | tarde, en la tarde, mediodía |
| EVENING | 6pm-10pm | noche, en la noche, nocturno |
| NIGHT | 10pm-6am | muy tarde, red eye, madrugada |

### Filtro por Clase de Cabina
| Filtro | Palabras clave |
|--------|----------------|
| ECONOMY | económica, turista |
| PREMIUM_ECONOMY | premium, premium economy |
| BUSINESS | business, bussines, bussinwss, ejecutiva |
| FIRST | primera, first class |

### Filtro por Aerolínea
| Código | Aerolínea |
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

### Sistema de Fallback (IMPORTANTE)
Si el AI no pasa los filtros correctamente, el sistema los detecta automáticamente del mensaje original:
```python
# app/api/whatsapp_meta.py (líneas 46-118)
detect_time_of_day_from_text(msg)  # "en la noche" → EVENING
detect_cabin_from_text(msg)         # "business" → BUSINESS
```

---

## Scheduler Jobs

| Job | Frecuencia | Descripción |
|-----|------------|-------------|
| process_auto_checkins | 15 min | Procesa check-ins pendientes |
| check_price_alerts | 6 horas | Verifica precios y notifica |
| refresh_visa_cache | 3 AM | Actualiza cache de visa |
| send_trip_reminders | 8 AM | Recordatorios de viaje |

---

## APIs y Tokens

| API | Estado | Modo | Variable de Entorno |
|-----|--------|------|---------------------|
| Duffel | OK | LIVE | DUFFEL_ACCESS_TOKEN |
| LiteAPI | OK | Sandbox | LITEAPI_KEY |
| OpenAI | OK | Production | OPENAI_API_KEY |
| WhatsApp | OK | Production | WHATSAPP_ACCESS_TOKEN |
| Stripe | OK | Test | STRIPE_SECRET_KEY |

---

## Usuarios Autorizados

```python
# app/api/whatsapp_meta.py
AUTHORIZED_NUMBERS = [
    "525610016226",  # Admin
    "525572461012",  # User
    "18098601748",   # Monnyka (RD)
]
```

---

## Bugs Arreglados (2026-02-03)

1. **Filtro aerolínea no funcionaba**
   - Fix: Filtro real en flight_engine.py (no solo boost de score)

2. **AI inventaba precios falsos**
   - Fix: Intro simple cuando hay vuelos, no dejar que AI genere texto

3. **Hoteles confundidos con vuelos**
   - Fix: Handler directo de hoteles en whatsapp_meta.py

4. **"No autorizado" para Monnyka**
   - Fix: Agregar 18098601748 a AUTHORIZED_NUMBERS

5. **AI no parseaba "en la noche" ni "business"**
   - Fix: Mejorar prompt + funciones fallback

6. **AI no pasaba time_of_day en tool call** ⭐ CRÍTICO
   - Problema: AI entendía "en la noche" pero no pasaba time_of_day="EVENING"
   - Respuesta decía "horarios nocturnos" pero mostraba vuelos de 07:00
   - Fix: Fallback `detect_time_of_day_from_text()` y `detect_cabin_from_text()`
   - Verificado: 122 ofertas → 2 vuelos (19:00) ✅

---

## Estructura de Archivos Clave

```
app/
├── api/
│   ├── whatsapp_meta.py    # WhatsApp webhook + fallback filters ⭐
│   ├── routes.py           # API REST
│   ├── price_alerts.py     # Alertas de precio
│   ├── loyalty.py          # Viajero frecuente
│   ├── itinerary.py        # Itinerarios
│   ├── visa.py             # Verificación visa
│   ├── checkin.py          # Check-in
│   └── baggage.py          # Equipaje
├── ai/
│   └── agent.py            # AI con tools (GPT-4o)
├── models/
│   └── models.py           # DB models (SQLAlchemy)
└── services/
    ├── flight_engine.py    # Motor de búsqueda + filtros
    ├── hotel_engine.py
    ├── booking_execution.py
    ├── scheduler_service.py # APScheduler jobs
    └── ...
```

---

## Deployment

### Render (Backend)
- URL: https://biajez.onrender.com
- Auto-deploy desde GitHub (main branch)
- Variables de entorno configuradas en Render Dashboard

### WhatsApp Webhook
- URL: https://biajez.onrender.com/v1/whatsapp/webhook
- Verify Token: biajez_verify_token_123
- Configurado en Meta Business Suite

### Frontend
- Local: http://localhost:5173
- Producción: Pendiente deploy a Vercel
- API URL en `.env`: VITE_API_URL

---

## Commits Recientes

```
44b68a5 Update docs with WhatsApp filter test results
fdef882 Update SISTEMA_COMPLETO.md with verified booking and filter docs
7802797 Update SISTEMA_COMPLETO.md with fallback filter fix
9ed0054 Fix: Add fallback filter detection for time_of_day and cabin ⭐
e689b19 Fix AI parsing for time_of_day and cabin_class filters
1044f59 Fix frontend API URLs to point to correct Render service
```

---

## Próximos Pasos (Opcionales)

- [ ] Activar LiteAPI producción (requiere fondeo)
- [ ] Activar Amadeus (crear cuenta nueva)
- [ ] Selección de asientos
- [ ] Pagos con Stripe en producción
- [ ] Deploy frontend a Vercel
- [ ] Monitorear logs en Render para verificar filtros

---

## Notas para Próxima Sesión

1. **Leer este archivo primero** (`SISTEMA_COMPLETO.md`)
2. El fix de filtros está en `app/api/whatsapp_meta.py` (funciones `detect_time_of_day_from_text` y `detect_cabin_from_text`)
3. Si hay problemas de filtros, revisar los logs de Render para ver qué argumentos pasa el AI
4. El backend local se inicia con: `source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000`
5. Los logs locales están en `/tmp/backend.log`

---

**Última actualización: 2026-02-03**
**Sistema 100% operacional y verificado**
