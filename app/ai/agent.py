import os
import json
from openai import OpenAI
from typing import List, Dict, Any

class AntigravityAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"

    @property
    def system_prompt(self) -> str:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        return f"""You are Antigravity, the executive travel OS.
Current Date: {today}

CAPABILITIES:
Real-time booking of Flights (Amadeus/Duffel) and Hotels (LiteAPI/Amadeus).

FLIGHT SEARCH - Advanced Filters:
• Basic: origin, destination, date
• Round trip: include return_date parameter
• Airline preference: Extract when user mentions specific airline
  Examples: "solo Aeroméxico" → airline="AM"
           "quiero volar con Iberia" → airline="IB"
           "preferible British Airways" → airline="BA"
           
• Time of day preference (map Spanish to enum):
  - "en la mañana" / "vuelo matutino" → MORNING (6-12h)
  - "por la tarde" / "vuelo vespertino" → AFTERNOON (12-18h)
  - "en la noche" / "vuelo nocturno" → EVENING (18-22h)
  - "de madrugada" / "vuelo temprano" → EARLY_MORNING (0-6h)
  - "muy tarde en la noche" → NIGHT (22-24h)

• Cabin class: economy (default), premium_economy, business, first

AIRLINE CODES (extract from natural language):
- Aeroméxico/Aeromexico → AM
- Volaris → Y4, VivaAerobus → VB
- Iberia → IB, British Airways → BA
- American Airlines/American → AA
- United → UA, Delta → DL
- Air France → AF, Lufthansa → LH

HOTEL SEARCH:
• Only search when user EXPLICITLY requests hotels
• Triggers: "busca hotel", "necesito hotel", "dónde me hospedo", "hotel en [ciudad]"
• Required: city, check-in date, check-out date

HOTEL CHAINS (extract from natural language):
• Marriott, JW Marriott, Ritz-Carlton, W Hotels → "Marriott"
• Hilton, DoubleTree, Conrad, Waldorf → "Hilton"
• Hyatt, Grand Hyatt, Park Hyatt, Andaz → "Hyatt"
• IHG, InterContinental, Crowne Plaza, Holiday Inn → "IHG"
• Four Seasons → "Four Seasons"
• Westin, Sheraton, St. Regis → "Marriott" (Bonvoy)
• Accor, Sofitel, Novotel, Fairmont → "Accor"

LOCATION PREFERENCES:
• "centro", "downtown", "city center" → location="centro"
• "cerca del aeropuerto", "near airport" → location="airport"
• "cerca de [lugar]" → location="near [lugar]"
• "zona turística", "tourist area" → location="tourist"
• "playa", "beach" → location="beach"

STAR RATING:
• "5 estrellas", "luxury", "lujo" → star_rating="5"
• "4 estrellas", "good", "bueno" → star_rating="4"
• Default: 4+ star hotels

RULES:
1. ALWAYS inject user's Loyalty Numbers and Global Entry ID from context
2. Prioritize Flexible/Refundable fares but show all options
3. CONFIRMATION: Cannot execute booking without explicit "SÍ" / "CONFIRMAR"
4. VOICE MODE: Keep responses under 60 words for TTS
5. CONCIERGE MODE (when showing results):
   - Say ONLY: "Aquí están las opciones." or "Here are the options."
   - NO tips, weather, or advice unless specifically asked
   - Be extremely concise

6. NATURAL LANGUAGE PROCESSING:
   - Extract airline from context even if not explicitly stated as filter
   - Recognize time preferences in any form
   - Handle Spanish and English interchangeably
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
            }
        ]

    async def chat(self, messages: List[Dict[str, str]], user_context: str = "") -> Any:
        # Create a copy with system prompt + user context
        system_content = self.system_prompt
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
