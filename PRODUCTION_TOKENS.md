# 🔑 Tokens de Producción - Biajez

Este archivo guarda los tokens de PRODUCCIÓN para cuando estés listo para activar el sistema real.

---

## 🚀 Duffel Production Token

**Token LIVE:**
```
duffel_live_onvO5hoirtsdyRkJ8bb3XCeiyW-ZXQbPFAaS1jmyqqc
```

**Para activar producción:**

1. Abre `.env`
2. Cambia:
   ```bash
   # De:
   DUFFEL_ACCESS_TOKEN=duffel_test_w1lARg3nw8-41NoEfYdAhwheuyGBXQu9sCDgQrr-O5W
   
   # A:
   DUFFEL_ACCESS_TOKEN=duffel_live_onvO5hoirtsdyRkJ8bb3XCeiyW-ZXQbPFAaS1jmyqqc
   ```

3. En `app/api/whatsapp_meta.py`, comenta las líneas 447-474 (mock booking)

4. Reinicia backend:
   ```bash
   pkill -f "uvicorn app.main:app"
   uvicorn app.main:app --port 8000
   ```

---

## ⚠️ IMPORTANTE AL ACTIVAR PRODUCCIÓN

**Cada reserva será REAL:**
- ✈️ Se genera ticket verdadero
- 💰 Duffel cobra comisión ($0.50 - $15 por reserva)
- 📧 Email de confirmación real al pasajero
- 🎫 PNR válido en aerolínea
- ❌ Cancelaciones tienen penalidad

**Recomendaciones:**
1. Prueba primero con vuelos domésticos baratos
2. Verifica que Stripe esté configurado para cobrar
3. Ten políticas de cancelación claras
4. Monitorea costos de Duffel en dashboard

---

## 📝 Estado Actual

**Sistema:**
- Token: `duffel_test_` (TEST)
- Mock booking: ACTIVO
- Reservas: SIMULADAS
- Perfecto para: Desarrollo y demos

**Cuando activar producción:**
- Tienes clientes reales listos
- Stripe configurado y probado
- Políticas de servicio definidas
- Soporte al cliente listo

---

## 💰 Costos Estimados de Duffel

**Por reserva:**
- Vuelos domésticos: ~$0.50 - $3
- Vuelos internacionales: ~$5 - $15
- Multi-city: ~$10 - $20

**Plus:**
- Búsquedas: GRATIS
- Cambios/Cancelaciones: Variable

**Dashboard:** https://duffel.com/dashboard

---

## 🔐 Otros Tokens de Producción (Pendientes)

### Amadeus Production
```bash
AMADEUS_CLIENT_ID=<obtener de amadeus.com>
AMADEUS_CLIENT_SECRET=<obtener de amadeus.com>
AMADEUS_HOSTNAME=api.amadeus.com
```

### Stripe Live
```bash
STRIPE_SECRET_KEY=sk_live_<obtener de stripe.com>
STRIPE_PUBLISHABLE_KEY=pk_live_<obtener de stripe.com>
```

### DuffelStays Production
```bash
DUFFEL_STAYS_TOKEN=stays_live_<obtener de duffel.com>
```

---

**Archivo creado:** 2026-02-01  
**Sistema:** Biajez WhatsApp Travel Bot
