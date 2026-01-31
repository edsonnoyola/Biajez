# 🧪 GUÍA DE PRUEBAS - AIRLINE CREDITS

Esta guía te ayudará a probar todas las funcionalidades implementadas.

## 📋 Pre-requisitos

1. **Backend corriendo**:
   ```bash
   cd /Users/end/Downloads/Biajez
   uvicorn app.main:app --reload
   ```

2. **Frontend corriendo**:
   ```bash
   cd /Users/end/Downloads/Biajez/frontend
   npm run dev
   ```

---

## ✅ PRUEBA 1: Backend API Tests

### 1.1 Crear un crédito de prueba

```bash
curl -X POST http://localhost:8000/v1/credits/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "airline_iata_code": "AM",
    "amount": 150.00,
    "currency": "USD",
    "expires_days": 365
  }'
```

**Resultado esperado:**
```json
{
  "id": "acd_xxx",
  "user_id": "demo-user",
  "airline_iata_code": "AM",
  "credit_amount": 150.0,
  "credit_currency": "USD",
  "expires_at": "2027-01-09T..."
}
```

### 1.2 Listar créditos del usuario

```bash
curl http://localhost:8000/v1/credits/demo-user
```

**Resultado esperado:**
- Lista con el crédito creado
- `is_valid: true`
- `is_expired: false`

### 1.3 Obtener créditos para Aeroméxico

```bash
curl http://localhost:8000/v1/credits/available/demo-user/AM
```

**Resultado esperado:**
- Solo créditos de Aeroméxico (AM)
- Solo créditos válidos (no usados, no expirados)

### 1.4 Ver balance total

```bash
curl http://localhost:8000/v1/credits/balance/demo-user
```

**Resultado esperado:**
```json
{
  "balances": {
    "USD": 150.0
  }
}
```

---

## ✅ PRUEBA 2: Frontend - Ver Créditos

### 2.1 Abrir Modal de Créditos

1. Abre la app en el navegador: `http://localhost:5173`
2. Haz clic en **"My Trips"**
3. Haz clic en **"My Credits"** (botón verde con icono de wallet)

**Resultado esperado:**
- Modal se abre
- Muestra "1 available credit"
- Muestra balance total: "USD $150.00"
- Lista el crédito con:
  - Monto: USD $150.00
  - Aerolínea: AM
  - Fecha de expiración
  - Badge verde "ACTIVE"

### 2.2 Filtrar créditos usados

1. En el modal de créditos
2. Marca el checkbox "Show used and expired credits"

**Resultado esperado:**
- Si hay créditos usados, aparecen en sección separada
- Tienen badge gris "USED"
- Están atenuados visualmente

---

## ✅ PRUEBA 3: Frontend - Usar Crédito en Booking

### 3.1 Buscar vuelo de Aeroméxico

1. En el chat, escribe:
   ```
   Busca vuelos de Ciudad de México a Cancún para el 15 de febrero
   ```

2. Espera los resultados

3. **Filtra por Aeroméxico**:
   - Busca un vuelo con código de aerolínea "AM"
   - Si no aparece AM, busca otra ruta donde AM opere

### 3.2 Abrir Booking Modal

1. Haz clic en **"Book Now"** en un vuelo de Aeroméxico

**Resultado esperado:**
- Modal de booking se abre
- Muestra precio del vuelo (ej: $200)

### 3.3 Ver Sección de Créditos

En el modal de booking, busca la sección **"Available Credits"**

**Resultado esperado:**
- Sección aparece automáticamente
- Muestra el crédito de $150 AM
- Tiene checkbox para seleccionar
- Muestra fecha de expiración

### 3.4 Seleccionar Crédito

1. Marca el checkbox del crédito

**Resultado esperado:**
- Checkbox se marca
- Fondo cambia a verde
- Aparece checkmark ✓
- **Precio se actualiza**:
  ```
  Flight: $200
  Credit: -$150
  ─────────────
  Total: $50
  ```

### 3.5 Deseleccionar Crédito

1. Desmarca el checkbox

**Resultado esperado:**
- Precio vuelve a $200
- Fondo vuelve a gris
- Checkmark desaparece

---

## ✅ PRUEBA 4: Flujo Completo de Pago con Crédito

### 4.1 Preparación

1. Asegúrate de tener un crédito de AM de $150
2. Busca un vuelo de Aeroméxico de ~$200

### 4.2 Proceso de Checkout

1. Selecciona el vuelo
2. En booking modal, selecciona el crédito
3. Verifica que precio muestra $50
4. Haz clic en **"Proceed to Payment"**
5. Completa el pago con tarjeta de prueba:
   - Número: `4242 4242 4242 4242`
   - Fecha: Cualquier fecha futura
   - CVC: Cualquier 3 dígitos

**Resultado esperado:**
- Pago de $50 (no $200)
- Booking exitoso
- Mensaje de confirmación

### 4.3 Verificar Crédito Usado

1. Cierra el modal de confirmación
2. Abre **"My Trips"** → **"My Credits"**
3. Marca "Show used and expired credits"

**Resultado esperado:**
- Crédito aparece en sección "Used Credits"
- Tiene badge "USED"
- Muestra fecha de uso
- Ya NO aparece en "Available Credits"

---

## ✅ PRUEBA 5: Validaciones

### 5.1 Crédito de Aerolínea Diferente

1. Crea un crédito de Delta (DL):
   ```bash
   curl -X POST http://localhost:8000/v1/credits/create \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "demo-user",
       "airline_iata_code": "DL",
       "amount": 100.00,
       "currency": "USD"
     }'
   ```

2. Busca un vuelo de Aeroméxico (AM)
3. Abre booking modal

**Resultado esperado:**
- Solo muestra crédito de AM ($150)
- NO muestra crédito de DL ($100)
- Validación automática por aerolínea

### 5.2 Crédito Mayor que Precio

1. Crea un crédito de $300
2. Busca un vuelo de $200
3. Selecciona el crédito

**Resultado esperado:**
- Total: $0.00 (no negativo)
- `Math.max(0, price - credit)` funciona

---

## ✅ PRUEBA 6: Cancelación con Crédito

### 6.1 Hacer una Reserva

1. Reserva cualquier vuelo
2. Completa el pago
3. Anota el PNR

### 6.2 Cancelar el Vuelo

1. Abre **"My Trips"**
2. Encuentra tu reserva
3. Haz clic en **"Cancel Trip"**
4. Confirma la cancelación

**Resultado esperado:**
- Vuelo cancelado
- **Crédito automático creado** con el monto del reembolso
- Mensaje: "✅ $XXX credit added to your account"

### 6.3 Verificar Crédito Creado

1. Abre **"My Credits"**

**Resultado esperado:**
- Nuevo crédito aparece
- Monto = refund amount
- Aerolínea = aerolínea del vuelo cancelado

---

## 🎯 Checklist de Pruebas

- [ ] Backend API responde correctamente
- [ ] Crear crédito funciona
- [ ] Listar créditos funciona
- [ ] Filtro por aerolínea funciona
- [ ] Modal "My Credits" se abre
- [ ] Créditos se muestran correctamente
- [ ] Sección de créditos aparece en booking
- [ ] Seleccionar crédito actualiza precio
- [ ] Pago con crédito funciona
- [ ] Crédito se marca como usado
- [ ] Validación por aerolínea funciona
- [ ] Cancelación genera crédito automático

---

## 🐛 Troubleshooting

### Error: "Connection refused"
**Solución:** Inicia el backend
```bash
uvicorn app.main:app --reload
```

### Error: "No credits shown"
**Solución:** Crea un crédito de prueba con curl

### Error: "Credit not applied"
**Solución:** Verifica que la aerolínea del crédito coincida con la del vuelo

### Error: "Price not updating"
**Solución:** Revisa la consola del navegador (F12) para errores

---

## 📊 Resultados Esperados

Si todas las pruebas pasan:

✅ **Backend**: Todos los endpoints funcionan
✅ **Frontend**: UI muestra créditos correctamente
✅ **Integración**: Créditos se aplican en checkout
✅ **Validación**: Solo créditos válidos se muestran
✅ **Persistencia**: Créditos se marcan como usados
✅ **Automatización**: Cancelaciones generan créditos

---

## 🚀 Script Automatizado

Para probar el backend automáticamente:

```bash
python3 test_credits_complete.py
```

**Nota:** Requiere que el servidor esté corriendo en localhost:8000
