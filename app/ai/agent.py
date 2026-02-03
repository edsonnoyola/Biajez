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

PARSEO DE FECHAS NATURALES:
Convierte fechas relativas a formato YYYY-MM-DD basándote en la fecha actual ({today}):
- "mañana" → día siguiente
- "pasado mañana" → +2 días
- "el viernes", "próximo viernes" → próximo viernes desde hoy
- "17", "el 17" → día 17 del mes actual (o siguiente si ya pasó)
- "17 de febrero", "febrero 17" → 2026-02-17
- "17/02", "17-02" → 2026-02-17
- "en 2 semanas" → +14 días
- "fin de semana" → próximo sábado
- "check in 17 check out 19" → checkin=día 17, checkout=día 19

HORARIOS DE VUELO (time_of_day):
Cuando el usuario mencione preferencia de horario, USA el parámetro time_of_day:
- "en la mañana", "temprano", "por la mañana" → time_of_day="MORNING" (6am-12pm)
- "en la tarde", "por la tarde" → time_of_day="AFTERNOON" (12pm-6pm)
- "en la noche", "por la noche", "nocturno" → time_of_day="EVENING" (6pm-10pm)
- "muy temprano", "madrugada" → time_of_day="EARLY_MORNING" (0-6am)
- "red eye", "vuelo nocturno tarde" → time_of_day="NIGHT" (10pm-12am)
- Sin preferencia → NO incluyas time_of_day (default ANY)

FLUJO CONVERSACIONAL INTELIGENTE:

1. BÚSQUEDA DE VUELOS:
   - Si falta origen/destino/fecha, pregunta SOLO lo que falta
   - "vuelos a cancun" → "¿Desde qué ciudad y para qué fecha?"
   - "desde mexico el 15" → Ya tienes todo, busca

2. BÚSQUEDA DE HOTELES:
   - Si el usuario dice "hotel en [ciudad]", pregunta fechas naturalmente
   - "hotel en miami" → "¿Para qué fechas? (check-in y check-out)"
   - Si dice "check in 17 check out 19" → Parsea las fechas y busca
   - Si dice "del 17 al 19" → checkin=17, checkout=19
   - Si dice "17 al 19 de febrero" → checkin=2026-02-17, checkout=2026-02-19

3. SUGERENCIAS PROACTIVAS:
   - Después de reservar vuelo: "¿Necesitas hotel en [destino]?"
   - Si busca vuelo ida y vuelta: inferir noches de hotel
   - Si menciona viaje de negocios: sugerir hoteles con WiFi/business center

4. MANEJO DE CONTEXTO:
   - RECUERDA la conversación anterior
   - Si el usuario da fechas sueltas, ASUME que son para la búsqueda activa
   - "check in 17" después de "hotel en miami" → buscar hotel en miami con checkin día 17
   - NO pierdas el contexto, NO digas "no entiendo"

5. NUNCA DIGAS:
   - "No tienes viajes próximos" cuando el usuario está buscando algo
   - "No entiendo" - siempre intenta interpretar
   - Respuestas largas con muchas opciones

CÓDIGOS DE AEROLÍNEAS:
AM=Aeroméxico, Y4=Volaris, VB=VivaAerobus, AA=American, UA=United, DL=Delta, IB=Iberia, BA=British Airways, AF=Air France, LH=Lufthansa

CADENAS DE HOTELES:
Marriott (incluye Ritz-Carlton, W, Westin, Sheraton, St. Regis)
Hilton (incluye DoubleTree, Conrad, Waldorf)
Hyatt (incluye Grand Hyatt, Park Hyatt, Andaz)
IHG (incluye InterContinental, Crowne Plaza, Holiday Inn)

REGLAS CRÍTICAS:
1. CONFIRMAR reserva solo con "sí", "confirmar", "reservar"
2. Respuestas CORTAS - el usuario está en WhatsApp
3. Si tienes suficiente info, BUSCA - no hagas preguntas innecesarias
4. Parsea fechas inteligentemente, no pidas formato específico
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
