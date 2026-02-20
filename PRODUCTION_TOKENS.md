# Tokens de Produccion - Biajez

---

## Estado Actual del Sistema

| API | Token | Modo | Estado |
|-----|-------|------|--------|
| Duffel | `duffel_live_...` | LIVE | Activo en Render |
| OpenAI | `sk-proj-...` | Production | Activo en Render |
| WhatsApp | Meta token | Production | Activo en Render |
| Resend | `re_...` | Production | Activo en Render |
| Redis | Render internal | Production | Activo |
| LiteAPI | `sand_...` | Sandbox | Activo en Render |
| Stripe | `sk_test_...` | Test | Configurado |
| Amadeus | Test keys | Test | Configurado |

**PRODUCCION ACTIVA** - Duffel LIVE genera tickets y PNR reales.

---

## Duffel Production Token

**Token LIVE (activo en Render):**
```
duffel_live_onvO5hoirtsdyRkJ8bb3XCeiyW-ZXQbPFAaS1jmyqqc
```

**Token TEST (para desarrollo local):**
```
duffel_test_w1lARg3nw8-41NoEfYdAhwheuyGBXQu9sCDgQrr-O5W
```

**Webhook Secret:** Pendiente configurar en Render como DUFFEL_WEBHOOK_SECRET

---

## IMPORTANTE: Reservas LIVE

Cada reserva con token LIVE:
- Genera ticket verdadero con PNR real en aerolinea
- Duffel cobra comision ($0.50 - $15 por reserva)
- Email de confirmacion real al pasajero
- Cancelaciones pueden tener penalidad
- El sistema muestra condiciones de cambio/reembolso antes de reservar

---

## Costos Duffel por Reserva

| Tipo | Costo estimado |
|------|---------------|
| Vuelos domesticos | $0.50 - $3 |
| Vuelos internacionales | $5 - $15 |
| Multi-city | $10 - $20 |
| Busquedas | GRATIS |
| Cambios/Cancelaciones | Variable |

**Dashboard:** https://duffel.com/dashboard

---

## Tokens Pendientes

### Amadeus Production
```bash
AMADEUS_CLIENT_ID=<obtener de amadeus.com>
AMADEUS_CLIENT_SECRET=<obtener de amadeus.com>
AMADEUS_HOSTNAME=api.amadeus.com
```

### Stripe Live
```bash
STRIPE_SECRET_KEY=sk_live_<obtener de stripe.com>
```

### LiteAPI Production
```bash
LITEAPI_API_KEY=<obtener de liteapi.travel>
LITEAPI_SANDBOX=false
```

### Duffel Webhook Secret
```bash
DUFFEL_WEBHOOK_SECRET=<obtener de duffel.com/webhooks>
# Agregar en Render Dashboard → Environment
```

---

## Variables en Render

Verificar en: Render Dashboard → biajez-d08x → Environment

```
DATABASE_URL             ✅
REDIS_URL                ✅
DUFFEL_ACCESS_TOKEN      ✅ Live
OPENAI_API_KEY           ✅
WHATSAPP_ACCESS_TOKEN    ✅
WHATSAPP_PHONE_NUMBER_ID ✅
WHATSAPP_VERIFY_TOKEN    ✅
RESEND_API_KEY           ✅
BASE_URL                 ✅ https://biajez-d08x.onrender.com
ADMIN_SECRET             ✅
STRIPE_SECRET_KEY        ✅ Test
LITEAPI_API_KEY          ✅ Sandbox
AMADEUS_CLIENT_ID        ✅ Test
AMADEUS_CLIENT_SECRET    ✅ Test
DUFFEL_WEBHOOK_SECRET    ❌ PENDIENTE
```

---

**Ultima actualizacion: 2026-02-20**
