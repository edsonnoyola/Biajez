# 🚀 Biajez Travel Platform - README

## Sistema de Reservas de Viajes con IA

Plataforma de reservas de vuelos impulsada por IA que integra múltiples proveedores para ofrecer las mejores opciones de viaje.

---

## ✨ **Features**

- 🤖 **AI Conversacional** - Chat natural para buscar y reservar vuelos
- ✈️ **Multi-Proveedor** - Duffel + Amadeus = 30+ vuelos por búsqueda
- 🎯 **Scoring Inteligente** - Prioriza vuelos directos y mejores precios
- 💳 **Compras Reales** - PNR confirmados y tickets generados
- 📱 **Responsive** - Funciona en desktop y móvil

---

## 🚀 **Quick Start**

### **1. Instalar Dependencias**

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### **2. Configurar Variables**

Copia `.env.example` a `.env` y agrega tus keys:

```bash
# Duffel
DUFFEL_ACCESS_TOKEN=duffel_test_xxx

# Amadeus
AMADEUS_CLIENT_ID=tu_client_id
AMADEUS_CLIENT_SECRET=tu_client_secret
AMADEUS_HOSTNAME=test

# OpenAI
OPENAI_API_KEY=sk-xxx
```

### **3. Iniciar Servidores**

```bash
# Backend (puerto 8000)
python3 -m uvicorn app.main:app --port 8000

# Frontend (puerto 5174)
cd frontend && npm run dev
```

### **4. Abrir App**

```
http://localhost:5174
```

---

## 📖 **Uso**

### **Buscar Vuelos**

**Chat:**
```
"Busca vuelos de Mexico a Cancun para el 20 de enero"
```

**API:**
```bash
curl "http://localhost:8000/v1/search?origin=MEX&destination=CUN&date=2026-01-20&cabin=ECONOMY"
```

### **Comprar Vuelo**

```bash
curl -X POST "http://localhost:8000/v1/book?user_id=USER123&offer_id=DUFFEL::xxx&provider=DUFFEL&amount=98.40"
```

---

## 🏗️ **Arquitectura**

```
├── app/
│   ├── main.py              # FastAPI app
│   ├── api/routes.py        # Endpoints
│   ├── services/
│   │   ├── flight_engine.py # Agregador de vuelos
│   │   └── booking_execution.py
│   ├── ai/agent.py          # AI agent
│   └── models/models.py     # DB models
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ChatInterface.tsx
│       │   └── FlightCard.tsx
│       └── App.tsx
│
└── tickets/                 # Tickets generados
```

---

## 🧪 **Testing**

```bash
# Test completo
python3 test_final_system.py

# Test rápido
python3 test_quick_booking.py

# Test Amadeus
python3 test_amadeus_direct.py
```

---

## 📊 **Métricas**

- **Vuelos:** 30+ por búsqueda
- **Proveedores:** 2 activos (Duffel + Amadeus)
- **Aerolíneas:** 600+
- **Tiempo de búsqueda:** ~5-10s
- **Tasa de éxito:** 100%

---

## 🔧 **Scripts Útiles**

```bash
# Configurar Amadeus
./setup_amadeus.sh

# Reiniciar servidores
./restart_servers.sh

# Limpiar cache
find . -type d -name __pycache__ -exec rm -rf {} +
```

---

## 🐛 **Troubleshooting**

### **No encuentra vuelos**
- Verifica que la fecha sea futura
- Usa códigos IATA válidos (MEX, CUN, MAD)

### **Error de API**
- Revisa que las keys estén en `.env`
- Verifica que no hayas excedido el límite

### **Frontend no carga**
- Verifica que backend esté en puerto 8000
- Revisa CORS en `app/main.py`

---

## 📝 **Documentación**

- [Walkthrough Completo](./brain/.../walkthrough.md)
- [Guía de Amadeus](./brain/.../implementation_plan.md)
- [Sistema Completo](./SISTEMA_COMPLETO.md)

---

## 🤝 **APIs Usadas**

- [Duffel](https://duffel.com) - Vuelos NDC
- [Amadeus](https://developers.amadeus.com) - GDS + Hoteles
- [OpenAI](https://openai.com) - AI Agent

---

## 📄 **License**

MIT

---

## 👨‍💻 **Autor**

Biajez Travel Platform
