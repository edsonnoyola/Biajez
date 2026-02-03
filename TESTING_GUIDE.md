# Guia de Pruebas - Biajez

## Pre-requisitos

### Local
```bash
cd /Users/end/Downloads/Biajez
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Produccion
- URL: https://biajez.onrender.com
- WhatsApp: Enviar mensaje al bot

---

## Pruebas de WhatsApp

### Vuelos Basicos

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Ida simple | `vuelo de MEX a MIA el 15 feb` | Lista de vuelos con precios |
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
| Espana | `visa MAD` | Requisitos para Espana |
| India | `visa IN` | Requisitos e-visa |

### Alertas

| Test | Mensaje | Resultado Esperado |
|------|---------|-------------------|
| Ver | `alertas` | Lista de alertas activas |
| Crear | `crear alerta` | Crea alerta (despues de buscar) |

---

## Pruebas API (curl)

### Busqueda de Vuelos
```bash
curl "https://biajez.onrender.com/v1/search?origin=MEX&destination=MIA&date=2026-02-15"
```

### Con Filtros
```bash
# Con aerolinea
curl "https://biajez.onrender.com/v1/search?origin=SDQ&destination=MIA&date=2026-02-15&airline=AA"

# Business class
curl "https://biajez.onrender.com/v1/search?origin=MEX&destination=LAX&date=2026-02-20&cabin=BUSINESS"

# En la manana
curl "https://biajez.onrender.com/v1/search?origin=MEX&destination=MIA&date=2026-02-18&time_of_day=MORNING"
```

### Scheduler Status
```bash
curl "https://biajez.onrender.com/scheduler/status"
```

---

## Pruebas de Python

### Test de Vuelos
```python
from dotenv import load_dotenv
load_dotenv()

import asyncio
from app.services.flight_engine import FlightAggregator

async def test():
    fa = FlightAggregator()

    # Basico
    results = await fa.search_hybrid_flights('MEX', 'MIA', '2026-02-15')
    print(f"Vuelos: {len(results)}")

    # Con filtro
    results = await fa.search_hybrid_flights('SDQ', 'MIA', '2026-02-15', airline='AA')
    print(f"Vuelos AA: {len(results)}")

asyncio.run(test())
```

### Test de Hoteles
```python
from app.services.liteapi_hotels import LiteAPIHotels

api = LiteAPIHotels()
hotels = api.search_hotels("Cancun", "2026-02-20", "2026-02-25")
print(f"Hoteles: {len(hotels)}")
```

---

## Checklist de Pruebas

### Vuelos
- [ ] Busqueda basica funciona
- [ ] Vuelos redondos funcionan
- [ ] Filtro por aerolinea funciona
- [ ] Filtro por horario funciona
- [ ] Clase business funciona
- [ ] Multi-destino 2 tramos funciona
- [ ] Multi-destino 3 tramos funciona

### Hoteles
- [ ] Busqueda basica funciona
- [ ] Fechas se parsean correctamente

### Servicios
- [ ] Itinerario muestra viaje proximo
- [ ] Historial muestra viajes pasados
- [ ] Equipaje muestra opciones
- [ ] Check-in muestra status
- [ ] Auto check-in programa recordatorio
- [ ] Visa muestra requisitos
- [ ] Alertas se crean y listan

### Scheduler
- [ ] Jobs estan programados
- [ ] /scheduler/status responde

---

## Troubleshooting

### "No encontre vuelos"
- Verificar fecha es futura
- Verificar codigos IATA validos
- Revisar logs del servidor

### "Error de conexion"
- Verificar servidor esta corriendo
- Verificar URL correcta

### "Aerolinea no encontrada"
- Usar codigo IATA (AA, AM, CM)
- No todos los vuelos tienen todas las aerolineas

---

## Resultados Esperados

| Ruta | Vuelos Tipicos |
|------|---------------|
| SDQ → MIA | 20-30 |
| MEX → MAD | 20-30 |
| MEX → CUN | 30+ |
| BOG → JFK | 20-30 |
| PTY → SCL | 20-30 |

| Ciudad | Hoteles Tipicos |
|--------|----------------|
| Cancun | 5-10 |
| CDMX | Variable |
| Punta Cana | 5-10 |
