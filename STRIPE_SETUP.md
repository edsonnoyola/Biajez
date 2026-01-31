# Guía de Configuración de Stripe

## 🎯 Objetivo
Configurar Stripe para procesar pagos en tu aplicación.

---

## 📋 Pasos para Obtener las Keys

### 1. Crear/Acceder a Cuenta de Stripe

**Si NO tienes cuenta:**
1. Ve a https://dashboard.stripe.com/register
2. Completa el registro
3. Verifica tu email

**Si YA tienes cuenta:**
1. Ve a https://dashboard.stripe.com/login
2. Inicia sesión

---

### 2. Obtener Test Keys (Desarrollo)

1. En el Dashboard de Stripe, ve a **Developers** → **API keys**
2. Asegúrate de estar en modo **Test** (toggle arriba a la derecha)
3. Verás dos keys:
   - **Publishable key** (empieza con `pk_test_...`)
   - **Secret key** (empieza con `sk_test_...`, click "Reveal test key")

**Copia estas keys:**
```
Publishable key: pk_test_51...
Secret key: sk_test_51...
```

---

### 3. Configurar en el Backend

Edita tu archivo `.env`:

```bash
# Backend .env
STRIPE_SECRET_KEY=sk_test_tu_key_aqui
STRIPE_PUBLISHABLE_KEY=pk_test_tu_key_aqui
```

---

### 4. Configurar en el Frontend

Crea o edita `frontend/.env`:

```bash
# Frontend .env
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_tu_key_aqui
```

---

### 5. Reiniciar Servidores

```bash
# Backend (Ctrl+C y luego)
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Ctrl+C y luego)
cd frontend && npm run dev
```

---

## 🧪 Probar Pagos en Modo Test

### Tarjetas de Prueba

Stripe proporciona tarjetas de prueba:

**Pago Exitoso:**
- Número: `4242 4242 4242 4242`
- Fecha: Cualquier fecha futura (ej: 12/34)
- CVC: Cualquier 3 dígitos (ej: 123)
- ZIP: Cualquier código postal

**Pago Rechazado:**
- Número: `4000 0000 0000 0002`
- Fecha: Cualquier fecha futura
- CVC: Cualquier 3 dígitos

**Requiere Autenticación 3D Secure:**
- Número: `4000 0025 0000 3155`
- Fecha: Cualquier fecha futura
- CVC: Cualquier 3 dígitos

---

## 🚀 Para Producción (Cuando estés listo)

### 1. Activar Cuenta

1. En Stripe Dashboard, completa la información de tu negocio
2. Proporciona información bancaria para recibir pagos
3. Verifica tu identidad

### 2. Obtener Production Keys

1. Cambia el toggle a **Live mode**
2. Ve a **Developers** → **API keys**
3. Copia las Live keys:
   - `pk_live_...`
   - `sk_live_...`

### 3. Actualizar .env para Producción

```bash
# Backend .env (PRODUCCIÓN)
STRIPE_SECRET_KEY=sk_live_tu_key_aqui
STRIPE_PUBLISHABLE_KEY=pk_live_tu_key_aqui
ENVIRONMENT=production

# Frontend .env (PRODUCCIÓN)
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_tu_key_aqui
```

---

## ⚠️ Importante

### Seguridad
- ❌ **NUNCA** compartas tu Secret Key
- ❌ **NUNCA** pongas Secret Key en el frontend
- ✅ Solo usa Publishable Key en el frontend
- ✅ Mantén .env en .gitignore

### Testing
- Usa **Test mode** para desarrollo
- Usa tarjetas de prueba de Stripe
- No uses tarjetas reales en test mode

### Producción
- Activa **Live mode** solo cuando estés listo
- Completa toda la información de tu negocio
- Configura webhooks de Stripe (opcional)

---

## 🔍 Verificar Configuración

### Backend
```bash
# Verificar que las keys están cargadas
python3 -c "from app.config import STRIPE_SECRET_KEY; print('✅ Stripe configurado' if STRIPE_SECRET_KEY else '❌ Falta configurar')"
```

### Frontend
```bash
# Verificar archivo .env
cat frontend/.env | grep STRIPE
```

---

## 🆘 Troubleshooting

### Error: "Stripe API key not configured"
- Verifica que `.env` existe
- Verifica que las keys están correctas
- Reinicia el servidor backend

### Error: "Invalid API Key"
- Verifica que copiaste la key completa
- Verifica que no hay espacios extras
- Verifica que usas test key en desarrollo

### Pagos no funcionan
- Verifica que el frontend tiene la publishable key
- Abre la consola del navegador para ver errores
- Verifica que el backend está corriendo

---

## ✅ Checklist

- [ ] Cuenta de Stripe creada
- [ ] Test keys obtenidas
- [ ] Backend .env configurado
- [ ] Frontend .env configurado
- [ ] Servidores reiniciados
- [ ] Pago de prueba exitoso

---

## 📞 Recursos

- Dashboard: https://dashboard.stripe.com
- Documentación: https://stripe.com/docs
- Tarjetas de prueba: https://stripe.com/docs/testing
- Soporte: https://support.stripe.com

---

¡Listo! Una vez configurado, podrás procesar pagos en tu aplicación. 🎉
