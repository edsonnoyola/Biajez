# Guia de Pruebas - Biajez

## Pre-requisitos

### Local
```bash
cd /Users/end/Desktop/Biajez
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Produccion
- URL: https://biajez-d08x.onrender.com
- WhatsApp: Enviar mensaje al bot

---

## Pruebas de WhatsApp

### Vuelos Basicos

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Ida simple | `vuelo de MEX a MIA el 15 feb` | Lista con precio, aerolinea, escalas, condiciones |
| Redondo | `vuelo MEX a CUN del 10 al 15 marzo` | Vuelos ida y vuelta |
| Manana | `vuelo SDQ a JFK en la manana` | Solo vuelos 6am-12pm |
| Tarde | `vuelo MEX a LAX en la tarde` | Solo vuelos 12pm-6pm |
| Noche | `vuelo BOG a MIA en la noche` | Solo vuelos 6pm-12am |

### Filtros de Aerolinea

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| American | `vuelo SDQ a MIA por American Airlines` | Solo vuelos AA |
| Aeromexico | `vuelo MEX a MAD por Aeromexico` | Solo vuelos AM |
| Copa | `vuelo PTY a BOG por Copa` | Solo vuelos CM |

### Clase de Cabina

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Business | `vuelo MEX a LAX en business` | Vuelos clase business |
| Primera | `vuelo MEX a JFK en primera` | Vuelos primera clase |

### Multi-destino

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| 2 tramos | `vuelo MEX a MIA el 1 marzo, luego MIA a MAD el 5` | Itinerario multi-ciudad |
| 3 tramos | `MEX a MIA el 1, MIA a JFK el 5, JFK a LAX el 10` | 3 segmentos |

### Formato de Resultados WhatsApp
Cada vuelo debe mostrar:
```
*1.* $245 USD
   AA1234 08:30 MEX→CUN
   Directo | Cambio gratis | Reembolsable
```
- Precio con moneda
- Codigo aerolinea + numero vuelo + hora + ruta
- Escalas (Directo / 1 escala / 2 escalas)
- Condiciones (Cambio gratis / Cambio: $X / Sin cambios / Reembolsable)

---

## Pruebas de Reserva

| Test | Paso | Resultado Esperado |
|------|------|-------------------|
| Seleccionar vuelo | Responder con numero (ej: `1`) | Muestra confirmacion con precio y ruta |
| Confirmar | Responder `si` | Reserva creada, PNR generado |
| Email | - | Email de confirmacion enviado |
| WhatsApp push | - | Notificacion de confirmacion |
| Ver reservas | `mis vuelos` | Lista de reservas activas |

---

## Pruebas de Cancelacion

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Iniciar | `cancelar vuelo` | Muestra viajes para cancelar |
| Confirmar | Seleccionar vuelo + confirmar | Cancelacion procesada |
| Reembolso | - | Monto de reembolso mostrado |
| Email | - | Email de cancelacion enviado |
| WhatsApp | - | Notificacion de cancelacion |

---

## Pruebas de Cambio de Vuelo

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Iniciar | `cambiar vuelo` | Muestra viajes para cambiar |
| Buscar opciones | Seleccionar + nueva fecha | Lista de opciones de cambio |
| Confirmar | Seleccionar opcion | Cambio confirmado |
| Email | - | Email de cambio enviado |
| WhatsApp | - | Notificacion de cambio |

---

## Pruebas de Hoteles

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Basico | `hotel en Cancun del 20 al 25 feb` | Lista de hoteles |
| Ciudad | `hoteles en CDMX` | Pide fechas |
| Con fechas | `hotel Punta Cana 15 al 20 marzo` | Lista con precios |

---

## Pruebas de Servicios

### Gestion de Viajes

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Itinerario | `itinerario` | Proximo viaje o "no tienes viajes" |
| Historial | `historial` | Lista de viajes pasados |
| Equipaje | `equipaje` | Opciones de equipaje adicional |

### Check-in

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Status | `checkin` | Status actual de check-in |
| Auto | `auto checkin` | Programa recordatorio |

### Visa

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| USA | `visa US` | Requisitos para USA |
| Espana | `visa ES` | Requisitos para Espana |

### Alertas

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Ver | `alertas` | Lista de alertas activas |
| Crear | `crear alerta` | Crea alerta (despues de buscar) |

### Perfil y Registro

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Registrar | `registrar` | Inicia flujo de registro |
| Mi perfil | `mi perfil` | Muestra datos del perfil |
| Reset | `reset` | Limpia sesion |

---

## Pruebas API (curl)

### Busqueda de Vuelos
```bash
curl "https://biajez-d08x.onrender.com/v1/search?origin=MEX&destination=MIA&date=2026-03-15"
```

### Con Filtros
```bash
# Con aerolinea
curl "https://biajez-d08x.onrender.com/v1/search?origin=SDQ&destination=MIA&date=2026-03-15&airline=AA"

# Business class
curl "https://biajez-d08x.onrender.com/v1/search?origin=MEX&destination=LAX&date=2026-03-20&cabin=BUSINESS"

# En la manana
curl "https://biajez-d08x.onrender.com/v1/search?origin=MEX&destination=MIA&date=2026-03-18&time_of_day=MORNING"
```

### Health y Status
```bash
# Health check
curl "https://biajez-d08x.onrender.com/health"

# Scheduler status
curl "https://biajez-d08x.onrender.com/scheduler/status"

# Admin health
curl "https://biajez-d08x.onrender.com/admin/health"
```

### Admin
```bash
# Ver perfiles
curl "https://biajez-d08x.onrender.com/admin/profiles?secret=ADMIN_SECRET"

# Ver sesion
curl "https://biajez-d08x.onrender.com/admin/session/525610016226?secret=ADMIN_SECRET"

# Redis status
curl "https://biajez-d08x.onrender.com/admin/redis-status?secret=ADMIN_SECRET"

# Webhook log
curl "https://biajez-d08x.onrender.com/admin/webhook-log?secret=ADMIN_SECRET"

# Enviar test WhatsApp
curl "https://biajez-d08x.onrender.com/admin/send-test?secret=ADMIN_SECRET&phone=525610016226"
```

---

## Pruebas de Webhooks

### Duffel Ping Test
```bash
# En Duffel dashboard: https://app.duffel.com/webhooks
# Click "Send test event" → Seleccionar ping
# Verificar en logs o admin/webhook-log
```

### Verificar Webhook Processing
```bash
curl "https://biajez-d08x.onrender.com/admin/webhook-log?secret=ADMIN_SECRET&n=5"
```

---

## Checklist de Pruebas

### Vuelos
- [ ] Busqueda basica funciona
- [ ] Formato WhatsApp muestra condiciones (cambio/reembolso)
- [ ] Vuelos redondos funcionan
- [ ] Filtro por aerolinea funciona
- [ ] Filtro por horario funciona
- [ ] Clase business funciona
- [ ] Multi-destino funciona
- [ ] Reservacion genera PNR real

### Notificaciones
- [ ] Email de confirmacion llega
- [ ] WhatsApp push de confirmacion llega
- [ ] Email de cancelacion llega
- [ ] WhatsApp push de cancelacion llega

### Gestion
- [ ] Cancelacion funciona con reembolso
- [ ] Cambio de vuelo funciona
- [ ] Itinerario muestra viaje proximo
- [ ] Historial muestra viajes pasados

### Servicios
- [ ] Check-in funciona
- [ ] Visa muestra requisitos
- [ ] Alertas se crean y listan
- [ ] Registro por WhatsApp funciona

### Admin
- [ ] /health responde
- [ ] /admin/redis-status funciona
- [ ] /scheduler/status muestra jobs
- [ ] /admin/send-test envia WhatsApp

---

## Troubleshooting

### "No encontre vuelos"
- Verificar fecha es futura (minimo 2 dias)
- Verificar codigos IATA validos (3 letras)
- Revisar logs del servidor

### "Error de conexion"
- Verificar servidor corriendo
- Verificar URL: https://biajez-d08x.onrender.com

### WhatsApp no responde
- Verificar token no expirado en Meta Business
- Verificar webhook URL correcta
- `GET /admin/send-test` para probar envio directo

### Emails no llegan
- Verificar RESEND_API_KEY en Render
- Verificar perfil tiene email real (no @whatsapp.temp)
- Resend free: 100 emails/dia

---

## Resultados Esperados

| Ruta | Vuelos Tipicos |
|------|---------------|
| SDQ → MIA | 20-30 |
| MEX → MAD | 20-30 |
| MEX → CUN | 30+ |
| BOG → JFK | 20-30 |

---

**Ultima actualizacion: 2026-02-20**
