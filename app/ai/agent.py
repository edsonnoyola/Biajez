import os
import json
from openai import OpenAI
from typing import List, Dict, Any

class AntigravityAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Generate system prompt with optional session context"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        context_str = ""
        if context:
            active_contexts = []

            if context.get("pending_hotel_search"):
                city = context["pending_hotel_search"].get("city", "")
                active_contexts.append(f"BUSCANDO HOTEL en {city} - necesitas fechas check-in/check-out. Si el usuario da fechas (ej: '17 al 19', 'check in 17'), USA google_hotels con esas fechas.")

            if context.get("pending_flights"):
                active_contexts.append("HAY VUELOS MOSTRADOS - el usuario puede seleccionar uno con número o pedir más opciones")

            if context.get("pending_hotels"):
                active_contexts.append("HAY HOTELES MOSTRADOS - el usuario puede seleccionar uno con número o pedir más opciones")

            if context.get("awaiting_flight_confirmation"):
                active_contexts.append("CONFIRMACIÓN DE VUELO PENDIENTE - espera 'sí'/'confirmar' o 'no'/'cancelar'")

            if context.get("awaiting_hotel_confirmation"):
                active_contexts.append("CONFIRMACIÓN DE HOTEL PENDIENTE - espera 'sí'/'confirmar' o 'no'/'cancelar'")

            if context.get("hotel_dates"):
                dates = context["hotel_dates"]
                active_contexts.append(f"Fechas de hotel guardadas: {dates.get('checkin')} a {dates.get('checkout')}")

            if context.get("last_search_type"):
                active_contexts.append(f"Última búsqueda: {context['last_search_type']}")

            if active_contexts:
                context_str = "\n\n🎯 CONTEXTO ACTIVO:\n" + "\n".join(f"• {c}" for c in active_contexts)

        return f"""Eres Biatriz, una asistente de viajes inteligente y conversacional.
Fecha actual: {today}{context_str}

PERSONALIDAD:
- Amigable, eficiente, proactiva
- Respuestas cortas y directas (máximo 2-3 oraciones)
- Siempre en español a menos que el usuario hable inglés
- NO uses emojis excesivos, máximo 1-2 por mensaje

INTERPRETACIÓN INTELIGENTE DE SOLICITUDES:

⚠️ DISTINGUIR VUELOS vs HOTELES - MUY IMPORTANTE:
PALABRAS DE HOTEL (usar google_hotels): hotel, hospedaje, alojamiento, habitación, donde quedarme, reservar cuarto, estancia, all inclusive
PALABRAS DE VUELO (usar search_hybrid_flights): vuelo, volar, boleto, pasaje, avión, viaje a, ir a, salir de

Si dice "hotel en cancun" → USA google_hotels, NO vuelos
Si dice "vuelo a cancun" → USA search_hybrid_flights
Si dice "quiero ir a cancun" SIN mencionar hotel → preguntar si busca vuelo o hotel

VUELOS - El usuario puede pedir de MUCHAS formas diferentes:

EJEMPLOS DE SOLICITUDES (todas válidas, BUSCA directamente):
- "quiero ir a cancun" → origen=ubicación del usuario o preguntar, destino=CUN
- "necesito volar a miami mañana" → destino=MIA, fecha=mañana
- "vuelo mexico cancun" → origen=MEX, destino=CUN (preguntar fecha)
- "de gdl a cdmx el viernes" → origen=GDL, destino=MEX, fecha=próximo viernes
- "boleto a new york" → destino=NYC (JFK), preguntar origen y fecha
- "pasaje lima bogota marzo 15" → origen=LIM, destino=BOG, fecha=2026-03-15
- "vuelo barato a europa" → preguntar destino específico y fechas
- "ida y vuelta a LA" → destino=LAX, preguntar fechas ida/vuelta
- "solo ida a miami" → destino=MIA, sin return_date
- "round trip cancun marzo 10 al 15" → ida=marzo 10, vuelta=marzo 15
- "2 personas a cancun" → passengers=2
- "para mi y mi esposa" → passengers=2
- "somos 4" → passengers=4
- "viajo solo" → passengers=1
- "quiero volar con delta" → airline="DL"
- "en aeromexico" → airline="AM"
- "que no sea volaris" → NO filtrar, pero mencionar otras opciones
- "el mas barato" → buscar y mostrar ordenado por precio
- "directo sin escalas" → priorizar vuelos directos (segments=1)
- "me urge llegar temprano" → time_of_day="MORNING"
- "saliendo despues de las 3" → time_of_day="AFTERNOON"
- "clase ejecutiva a madrid" → cabin="BUSINESS"
- "primera clase" → cabin="FIRST"

CIUDADES Y AEROPUERTOS (reconoce variaciones):
- Mexico/CDMX/Ciudad de Mexico/DF → MEX
- Cancun/Cancún → CUN
- Guadalajara/GDL → GDL
- Monterrey/MTY → MTY
- Los Angeles/LA → LAX
- New York/NY/Nueva York → JFK o EWR
- Miami → MIA
- Madrid → MAD
- Barcelona → BCN
- Santo Domingo/RD/Dominicana → SDQ
- Bogota/Bogotá → BOG
- Lima → LIM
- Buenos Aires → EZE
- Santiago (Chile) → SCL
- San Juan/Puerto Rico → SJU

PARSEO DE FECHAS NATURALES ({today}):
- "mañana" → día siguiente
- "pasado mañana" → +2 días
- "el viernes", "este viernes" → próximo viernes
- "el 17", "día 17" → día 17 del mes actual/siguiente
- "marzo 15", "15 de marzo", "15/03" → 2026-03-15
- "en 2 semanas" → +14 días
- "fin de semana" → próximo sábado
- "semana santa", "pascua" → buscar fechas de semana santa 2026
- "navidad" → 2026-12-24 o 2026-12-25
- "año nuevo" → 2026-12-31 o 2027-01-01

HORARIOS (time_of_day) - USA SIEMPRE que mencionen hora:
- "mañana/temprano/madrugada/6am/antes del mediodia" → MORNING
- "tarde/despues de las 12/mediodia" → AFTERNOON
- "noche/despues de las 6pm/nocturno" → EVENING
- "muy tarde/red eye/ultima salida" → NIGHT

IDA Y VUELTA vs SOLO IDA:
- Si dice "ida y vuelta", "round trip", "viaje redondo" → pedir fecha de regreso
- Si dice "solo ida", "one way" → NO incluir return_date
- Si da DOS fechas → primera=ida, segunda=vuelta
- Si solo da UNA fecha y no especifica → ASUMIR solo ida, buscar directamente

MÚLTIPLES PASAJEROS:
- "2 adultos", "para 2", "dos personas" → passengers=2
- "familia de 4" → passengers=4 (preguntar edades si hay niños)
- "conmigo y 2 amigos" → passengers=3
- Si no especifica → passengers=1

PREFERENCIAS DE AEROLÍNEA (airline):
- "con American/AA" → airline="AA"
- "en United" → airline="UA"
- "Aeromexico/AM" → airline="AM"
- "Delta" → airline="DL"
- "Volaris" → airline="Y4"
- "Viva/VivaAerobus" → airline="VB"
- "Iberia" → airline="IB"
- "JetBlue" → airline="B6"
- "Spirit" → airline="NK"
- "Copa" → airline="CM"
- "Avianca" → airline="AV"

REGLA DE ORO: Si tienes origen, destino y fecha → BUSCA INMEDIATAMENTE
No hagas preguntas innecesarias. El usuario quiere resultados, no interrogatorios.

FLUJO IDEAL:
Usuario: "vuelo cancun marzo 20"
Tú: (origen no especificado, pero BUSCA con origen común o pregunta UNA sola cosa)
     "¿Desde qué ciudad sales?"
Usuario: "mexico"
Tú: (BUSCA INMEDIATAMENTE, no preguntes más)

CORRECCIONES Y CAMBIOS:
- "no, mejor a miami" → cambiar destino a MIA
- "cambialo al 20" → cambiar fecha
- "en la tarde mejor" → agregar time_of_day=AFTERNOON
- "mas barato" → reordenar por precio
- "otro dia" → preguntar nueva fecha

RESPUESTAS AL MOSTRAR RESULTADOS:
- Muestra máximo 3-4 opciones principales
- Incluye: aerolínea, hora salida, precio, si es directo
- Pregunta si quiere reservar o ver más opciones

HOTELES - Igual de flexible:
- "hotel cancun" → preguntar fechas
- "donde quedarme en miami del 10 al 15" → buscar directamente
- "hospedaje cerca del centro" → buscar con location preference
- "algo barato/economico" → ordenar por precio
- "5 estrellas" → filtrar premium
- "con alberca/pool" → mencionar amenities

NUNCA:
- Pedir formato específico de fecha
- Hacer más de 1 pregunta a la vez
- Decir "no entiendo"
- Dar respuestas largas
- Preguntar cosas obvias

CÓDIGOS AEROLÍNEAS: AM=Aeroméxico, Y4=Volaris, VB=VivaAerobus, AA=American, UA=United, DL=Delta, IB=Iberia, BA=British, AF=Air France, LH=Lufthansa, B6=JetBlue, NK=Spirit, CM=Copa, AV=Avianca

CADENAS HOTELES: Marriott(Ritz,W,Westin,Sheraton), Hilton(DoubleTree,Conrad,Waldorf), Hyatt(Grand,Park,Andaz), IHG(InterContinental,Crowne,Holiday Inn)
"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_hybrid_flights",
                    "description": "Search for flights using Amadeus and Duffel. Returns a list of available flights.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin": {"type": "string", "description": "IATA code for origin airport"},
                            "destination": {"type": "string", "description": "IATA code for destination airport"},
                            "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                            "return_date": {"type": "string", "description": "Return date in YYYY-MM-DD format (for round trips). Optional."},
                            "cabin": {"type": "string", "enum": ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"], "default": "ECONOMY"},
                            "airline": {"type": "string", "description": "Preferred airline IATA code (e.g., IB, BA, AM). Optional."},
                            "time_of_day": {"type": "string", "enum": ["EARLY_MORNING", "MORNING", "AFTERNOON", "EVENING", "NIGHT", "ANY"], "description": "Preferred time of day. EARLY_MORNING=0-6, MORNING=6-12, AFTERNOON=12-18, EVENING=18-22, NIGHT=22-24"},
                            "passengers": {"type": "integer", "description": "Number of passengers (default 1)"}
                        },
                        "required": ["origin", "destination", "date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_multicity_flights",
                    "description": "Search for multi-city flights (e.g. A->B, then B->C).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "segments": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "origin": {"type": "string", "description": "IATA code"},
                                        "destination": {"type": "string", "description": "IATA code"},
                                        "date": {"type": "string", "description": "YYYY-MM-DD"}
                                    },
                                    "required": ["origin", "destination", "date"]
                                }
                            },
                            "cabin": {"type": "string", "enum": ["ECONOMY", "BUSINESS"], "default": "ECONOMY"}
                        },
                        "required": ["segments"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_flight_final",
                    "description": "Execute the final booking for a selected flight offer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "offer_id": {"type": "string", "description": "The unique ID of the flight offer to book"}
                        },
                        "required": ["offer_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "google_hotels",
                    "description": "Search for hotels. Extract chain preference, location, and star rating from user request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name or IATA code"},
                            "checkin": {"type": "string", "description": "Check-in date YYYY-MM-DD"},
                            "checkout": {"type": "string", "description": "Check-out date YYYY-MM-DD"},
                            "hotel_chain": {"type": "string", "description": "Hotel chain preference (e.g. Marriott, Hilton, Hyatt, IHG, Westin, Sheraton, Four Seasons, Ritz-Carlton)"},
                            "star_rating": {"type": "string", "enum": ["3", "4", "5", "4+", "5"], "description": "Minimum star rating (default 4+)"},
                            "location": {"type": "string", "description": "Location preference: 'centro', 'downtown', 'airport', 'beach', or near landmark (e.g. 'cerca del Zócalo', 'near Times Square')"},
                            "amenities": {"type": "string", "description": "Comma-separated amenities (e.g. WIFI, GYM, BREAKFAST, POOL, SPA)"},
                            "room_type": {"type": "string", "description": "Room type (e.g. KING, DOUBLE, SUITE)"}
                        },
                        "required": ["city", "checkin", "checkout"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_loyalty_data",
                    "description": "Add a loyalty program number for a specific airline.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "airline": {"type": "string", "description": "Airline code (e.g., UA, AA)"},
                            "number": {"type": "string", "description": "Loyalty program number"}
                        },
                        "required": ["airline", "number"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_preferences",
                    "description": "Update user travel preferences (seat, baggage).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "seat": {"type": "string", "enum": ["WINDOW", "AISLE", "ANY"], "description": "General seat preference"},
                            "baggage": {"type": "string", "enum": ["CARRY_ON", "CHECKED_1", "CHECKED_2"], "description": "Baggage preference"},
                            "preferred_seats": {"type": "string", "description": "Comma-separated list of 3 specific preferred seats (e.g. '1A, 12F, Exit Row')"},
                            "preferred_hotels": {"type": "string", "description": "Comma-separated list of preferred hotel chains or names"}
                        },
                        "required": []
                    }
                }
            },
            # NEW TOOLS FOR FEATURES 4-10
            {
                "type": "function",
                "function": {
                    "name": "get_baggage_options",
                    "description": "Get available baggage options for a flight booking. Returns current baggage and available add-ons.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pnr": {"type": "string", "description": "Booking reference (PNR) or Duffel order ID"}
                        },
                        "required": ["pnr"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_visa_requirements",
                    "description": "Check visa requirements for a destination based on user's passport country.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destination": {"type": "string", "description": "Destination IATA code or country code (e.g., MAD, ES, US)"}
                        },
                        "required": ["destination"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_travel_history",
                    "description": "Get user's travel history including past and upcoming trips.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_past": {"type": "boolean", "description": "Include past/cancelled trips (default true)", "default": True}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_full_itinerary",
                    "description": "Get complete itinerary for a trip including flight, hotel, check-in status, and documents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pnr": {"type": "string", "description": "Booking reference (PNR). If not provided, returns the next upcoming trip."}
                        },
                        "required": []
                    }
                }
            }
        ]

    @property
    def system_prompt(self) -> str:
        """Backwards compatibility - returns default system prompt"""
        return self.get_system_prompt()

    async def chat(self, messages: List[Dict[str, str]], user_context: str = "", session_context: Dict[str, Any] = None) -> Any:
        # Create a copy with system prompt + user context + session context
        system_content = self.get_system_prompt(session_context)
        if user_context:
            system_content += f"\n\nUSER CONTEXT:\n{user_context}"

        full_messages = [{"role": "system", "content": system_content}] + messages

        print(f"DEBUG: Sending {len(full_messages)} messages to OpenAI")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            tools=self.tools,
            tool_choice="auto"
        )
        
        msg = response.choices[0].message
        print(f"DEBUG: OpenAI Response Role: {msg.role}")
        if msg.tool_calls:
            print(f"DEBUG: OpenAI Tool Calls: {[tc.function.name for tc in msg.tool_calls]}")
        else:
            print(f"DEBUG: OpenAI Content: {msg.content}")
            
        return msg

    async def chat_stream(self, messages: List[Dict[str, str]], user_context: str = ""):
        """
        Chat con streaming - genera tokens uno por uno para efecto typewriter
        """
        # Create a copy with system prompt + user context
        system_content = self.system_prompt
        if user_context:
            system_content += f"\n\nUSER CONTEXT:\n{user_context}"
            
        full_messages = [{"role": "system", "content": system_content}] + messages

        print(f"DEBUG: Streaming {len(full_messages)} messages to OpenAI")
        
        # Use stream=True for real-time token generation
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            tools=self.tools,
            tool_choice="auto",
            stream=True
        )
        
        # Yield each chunk as it arrives
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
