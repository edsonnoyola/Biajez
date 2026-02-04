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
- [x] Filtro por aerolinea (AA, CM, AM, DL, AV, etc.)
- [x] Filtro por horario (MORNING, AFTERNOON, EVENING, NIGHT)
- [x] Filtro por clase (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
- [x] Vuelos redondos (ida y vuelta)
- [x] Multi-destino (2-3 tramos)
- [x] Reservacion con PNR real
- [x] Multiples pasajeros (1-9)

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
- [x] Millas/Viajero frecuente

---

## Comandos WhatsApp

### Vuelos
```
vuelo de MEX a MIA el 15 de febrero
vuelo MEX a MAD por Aeromexico
vuelo SDQ a JFK en la manana
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

## Filtros Disponibles

### Horario (time_of_day)
| Filtro | Horas | Palabras clave |
|--------|-------|----------------|
| MORNING | 6am-12pm | manana, temprano, madrugada |
| AFTERNOON | 12pm-6pm | tarde, despues del mediodia |
| EVENING | 6pm-10pm | noche, en la noche, nocturno |
| NIGHT | 10pm-6am | muy tarde, red eye |

### Clase de Cabina
| Filtro | Palabras clave |
|--------|----------------|
| ECONOMY | economica, turista |
| PREMIUM_ECONOMY | premium |
| BUSINESS | business, ejecutiva, bussines |
| FIRST | primera, first class |

### Aerolineas
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

---

## Usuarios Autorizados

```python
AUTHORIZED_NUMBERS = [
    "525610016226",  # Admin
    "525572461012",  # User
    "18098601748",   # Monnyka (RD)
]
```

---

## Pruebas Exhaustivas Realizadas

### Vuelos Largos/Dificiles
| Ruta | Precio | Escalas |
|------|--------|---------|
| MEX → TYO | $1,106 | Directo |
| MEX → SYD | $1,748 | 1 |
| BOG → DXB | $1,235 | 1 |
| SDQ → FCO | $835 | 1 |
| SYD → JFK | $1,876 | 1 |
| EZE → NRT | $1,239 | 1 |

### Vuelos Regionales
| Ruta | Precio |
|------|--------|
| MEX → GDL | $27 |
| BOG → MDE | $65 |
| LIM → CUZ | $92 |

### Filtros Aerolinea (todos OK)
| Aerolinea | Vuelos |
|-----------|--------|
| AA | 30 |
| AM | 25 |
| CM | 27 |
| DL | 14 |
| AV | 30 |

### Clases de Cabina
| Clase | Precio MEX-LAX |
|-------|----------------|
| Business | $732 |
| First | $9,791 |
| Premium Eco | $403 |

### Multi-destino
| Ruta | Precio | Opciones |
|------|--------|----------|
| MEX→MIA→MAD | $882 | 246 |
| MEX→MIA→JFK→LAX | $1,387 | 80 |
| BOG→PTY→MIA→MAD | $1,229 | 4,112 |

### Multiples Pasajeros (MEX-CUN)
| Pax | Total |
|-----|-------|
| 1 | $59 |
| 2 | $119 |
| 3 | $178 |
| 4 | $238 |

---

## Bugs Arreglados

### 2026-02-03

1. **Filtro aerolinea no funcionaba**
   - Problema: Pedir AA mostraba Copa
   - Fix: Agregar filtro real en flight_engine.py (no solo boost de score)

2. **AI inventaba precios falsos**
   - Problema: Mostraba $250, $270, $290 inventados
   - Fix: Usar intro simple cuando hay vuelos, no dejar que AI genere texto

3. **Hoteles confundidos con vuelos**
   - Problema: AI pensaba que hoteles eran vuelos
   - Fix: Handler directo de hoteles en whatsapp_meta.py

4. **"No autorizado" para Monnyka**
   - Fix: Agregar 18098601748 a AUTHORIZED_NUMBERS

5. **AI no parseaba "en la noche" ni "business"**
   - Problema: Pedir vuelos en la noche en business mostraba todo el dia
   - Fix: Mejorar prompt del AI con deteccion de typos (bussinwss)

---

## Estructura de Archivos

```
app/
├── api/
│   ├── routes.py           # API REST
│   ├── whatsapp_meta.py    # WhatsApp webhook
│   ├── price_alerts.py     # Alertas de precio
│   ├── loyalty.py          # Viajero frecuente
│   ├── itinerary.py        # Itinerarios
│   ├── visa.py             # Verificacion visa
│   ├── checkin.py          # Check-in
│   └── baggage.py          # Equipaje
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
    ├── loyalty_service.py
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

### Frontend
- URL local: http://localhost:5173
- API URL: Configurable en .env (localhost o Render)

---

## Commits Recientes

```
e689b19 Fix AI parsing for time_of_day and cabin_class filters
1044f59 Fix frontend API URLs to point to correct Render service
c5d4347 Update TESTING_GUIDE.md with comprehensive tests
4b1c6b5 Update SISTEMA_COMPLETO.md with current status
dabc23e Update README with complete feature documentation
bd99e8b Add price alerts scheduler job
01dec33 Add Monnyka (RD) to authorized numbers whitelist
c5713fb Add direct hotel handler - bypass AI for hotel searches
6efbf89 Make AI more aggressive about hotel detection
ab7757b Fix AI to distinguish hotel vs flight searches
16c3b7e Fix: Prevent AI from inventing flight data
```

---

## Proximos Pasos (Opcionales)

- [ ] Activar LiteAPI produccion (requiere fondeo)
- [ ] Activar Amadeus (crear cuenta nueva)
- [ ] Seleccion de asientos
- [ ] Pagos con Stripe en produccion
- [ ] Deploy frontend a Vercel

---

**Sistema 100% operacional - Ultima actualizacion: 2026-02-03**
