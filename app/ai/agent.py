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
• Triggers: "busca hotel", "necesito hotel", "dónde me hospedo"
• Required: city, check-in date, check-out date
• Optional: amenities, room type, landmark proximity

TONE & STYLE:
• Executive, efficient, professional.
• Concise responses (WhatsApp style).
• Use emojis for readability (✈️, 🏨, 📅).
• Confirm all details before booking.
• If details are missing, ask for them specifically.

IMPORTANT: NEVER invent flights. Only use the tools provided.
"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_multicity",
                    "description": "Search for multi-city or round-trip flights or one-way flights.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "segments": {
                                "type": "array", 
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "origin": {"type": "string", "description": "IATA code (e.g. MEX)"},
                                        "destination": {"type": "string", "description": "IATA code (e.g. MAD)"},
                                        "date": {"type": "string", "description": "YYYY-MM-DD"}
                                    },
                                    "required": ["origin", "destination", "date"]
                                }
                            },
                            "cabin": {"type": "string", "enum": ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]},
                            "passengers": {"type": "integer", "description": "Number of passengers (default 1)"}
                        },
                        "required": ["segments"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_hotels",
                    "description": "Search for hotels in a specific city/location.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name or IATA code"},
                            "checkin": {"type": "string", "description": "YYYY-MM-DD"},
                            "checkout": {"type": "string", "description": "YYYY-MM-DD"},
                            "guests": {"type": "integer", "description": "Number of guests (default 2)"}
                        },
                        "required": ["city", "checkin", "checkout"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_flight",
                    "description": "Book a specific flight offer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "offer_id": {"type": "string", "description": "The ID of the flight offer to book (e.g., DUFFEL::...)"},
                            "travelers": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "given_name": {"type": "string"},
                                        "family_name": {"type": "string"},
                                        "dob": {"type": "string", "description": "YYYY-MM-DD"},
                                        "gender": {"type": "string", "enum": ["m", "f"]},
                                        "title": {"type": "string", "enum": ["mr", "ms", "mrs"]}
                                    },
                                    "required": ["given_name", "family_name", "dob", "gender"]
                                }
                            }
                        },
                        "required": ["offer_id"]
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
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                tools=self.tools,
                tool_choice="auto"
            )
            return response.choices[0].message
        except Exception as e:
            print(f"❌ OpenAI Error: {e}")
            raise e
