# Sistema Biajez - Estado Actual

## ESTADO: 100% FUNCIONAL

### Modo de Operacion
- **Vuelos:** Duffel LIVE (precios reales)
- **Hoteles:** LiteAPI Sandbox
- **WhatsApp:** Meta Business API
- **AI:** OpenAI GPT-4o

---

## Features Implementadas

### Vuelos
- [x] Busqueda con Duffel LIVE
- [x] Filtro por aerolinea (AA, CM, AM, etc.)
- [x] Filtro por horario (manana, tarde, noche)
- [x] Filtro por clase (economy, business)
- [x] Vuelos redondos
- [x] Multi-destino (2-3 tramos)
- [x] Reservacion con PNR real

### Hoteles
- [x] Busqueda con LiteAPI
- [x] Duffel Stays (sandbox)
- [x] Filtro por fechas
- [x] Reservacion

### Gestion de Viajes
- [x] Itinerario (proximo viaje)
- [x] Historial (viajes pasados)
- [x] Equipaje adicional
- [x] Check-in automatico
- [x] Recordatorio de check-in

### Servicios Adicionales
- [x] Verificacion de visa
- [x] Alertas de precio
- [x] Notificaciones push WhatsApp
- [x] Background scheduler

---

## Comandos WhatsApp

### Vuelos
```
vuelo de MEX a MIA el 15 de febrero
vuelo MEX a MAD por Aeromexico
vuelo SDQ a JFK en la manana
vuelo MEX a LAX en business
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

## Scheduler Jobs

| Job | Frecuencia | Descripcion |
|-----|------------|-------------|
| process_auto_checkins | 15 min | Procesa check-ins pendientes |
| check_price_alerts | 6 horas | Verifica precios y notifica |
| refresh_visa_cache | 3 AM | Actualiza cache de visa |
| send_trip_reminders | 8 AM | Recordatorios de viaje |

---

## APIs y Tokens

### Activos
| API | Estado | Modo |
|-----|--------|------|
| Duffel | OK | LIVE |
| LiteAPI | OK | Sandbox |
| OpenAI | OK | Production |
| WhatsApp | OK | Production |
| Stripe | OK | Test |

### Variables de Entorno
```bash
DUFFEL_ACCESS_TOKEN=duffel_live_xxx  # LIVE
LITEAPI_API_KEY=sand_xxx             # Sandbox
OPENAI_API_KEY=sk-xxx                # Production
WHATSAPP_ACCESS_TOKEN=xxx            # Production
STRIPE_SECRET_KEY=sk_test_xxx        # Test
```

---

## Usuarios Autorizados

Numeros con acceso a reservaciones:
```python
AUTHORIZED_NUMBERS = [
    "525610016226",  # Admin
    "525572461012",  # User
    "18098601748",   # Monnyka (RD)
]
```

---

## Pruebas Realizadas

### Vuelos (todos OK)
| Ruta | Tipo | Resultados |
|------|------|------------|
| SDQ → MIA | Ida | 30 vuelos |
| MEX → MAD | Internacional | 30 vuelos |
| GDL → LAX | Redondo | 30 vuelos |
| MEX→MIA→MAD | Multi 2 | 261 vuelos |
| MEX→MIA→JFK→LAX | Multi 3 | 80 vuelos |
| SDQ→MIA (AA) | Filtro aerolinea | 20 vuelos |
| MEX→MIA (AM) | Filtro horario | 30 vuelos |
| MEX→LAX | Business | 30 vuelos |

### Hoteles
| Ciudad | Resultados |
|--------|------------|
| Cancun | 7 hoteles |
| CDMX | Variable |

---

## Estructura de Archivos

```
app/
├── api/
│   ├── routes.py           # API REST
│   └── whatsapp_meta.py    # WhatsApp webhook
├── ai/
│   └── agent.py            # AI con tools
├── models/
│   └── models.py           # DB models
└── services/
    ├── flight_engine.py
    ├── hotel_engine.py
    ├── booking_execution.py
    ├── itinerary_service.py
    ├── baggage_service.py
    ├── checkin_service.py
    ├── visa_service.py
    ├── price_alert_service.py
    ├── scheduler_service.py
    └── push_notification_service.py
```

---

## Deployment

### Render
- URL: https://biajez.onrender.com
- Auto-deploy desde GitHub
- Redis disponible

### WhatsApp Webhook
- URL: https://biajez.onrender.com/v1/whatsapp/webhook
- Verify Token: biajez_verify_token_123

---

## Proximos Pasos (Opcionales)

- [ ] Activar LiteAPI produccion (requiere fondeo)
- [ ] Activar Amadeus (crear cuenta nueva)
- [ ] Seleccion de asientos
- [ ] Pagos con Stripe en produccion
- [ ] Frontend web

---

**Sistema 100% operacional**
