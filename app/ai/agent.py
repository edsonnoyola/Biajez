import os
import json
from anthropic import Anthropic
from typing import List, Dict, Any

class AntigravityAgent:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"  # Claude Sonnet 4

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
• Filter: Only 4+ star hotels in safe business districts

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
        """Tools in Anthropic format"""
        return [
            {
                "name": "search_hybrid_flights",
                "description": "Search for flights using Amadeus and Duffel. Returns a list of available flights.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "description": "IATA code for origin airport"},
                        "destination": {"type": "string", "description": "IATA code for destination airport"},
                        "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                        "return_date": {"type": "string", "description": "Return date in YYYY-MM-DD format (for round trips). Optional."},
                        "cabin": {"type": "string", "enum": ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"], "description": "Cabin class. Default: ECONOMY"},
                        "airline": {"type": "string", "description": "Preferred airline IATA code (e.g., IB, BA, AM). Optional."},
                        "time_of_day": {"type": "string", "enum": ["EARLY_MORNING", "MORNING", "AFTERNOON", "EVENING", "NIGHT", "ANY"], "description": "Preferred time of day. EARLY_MORNING=0-6, MORNING=6-12, AFTERNOON=12-18, EVENING=18-22, NIGHT=22-24"},
                        "passengers": {"type": "integer", "description": "Number of passengers. Default: 1"}
                    },
                    "required": ["origin", "destination", "date"]
                }
            },
            {
                "name": "search_multicity_flights",
                "description": "Search for multi-city flights (e.g. A->B, then B->C).",
                "input_schema": {
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
                        "cabin": {"type": "string", "enum": ["ECONOMY", "BUSINESS"], "description": "Cabin class. Default: ECONOMY"},
                        "passengers": {"type": "integer", "description": "Number of passengers. Default: 1"}
                    },
                    "required": ["segments"]
                }
            },
            {
                "name": "book_flight_final",
                "description": "Execute the final booking for a selected flight offer.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "offer_id": {"type": "string", "description": "The unique ID of the flight offer to book"}
                    },
                    "required": ["offer_id"]
                }
            },
            {
                "name": "google_hotels",
                "description": "Search for hotels meeting the 4-star+ criteria.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name or IATA code"},
                        "checkin": {"type": "string", "description": "Check-in date YYYY-MM-DD"},
                        "checkout": {"type": "string", "description": "Check-out date YYYY-MM-DD"},
                        "amenities": {"type": "string", "description": "Comma-separated amenities (e.g. WIFI, GYM, BREAKFAST, POOL)"},
                        "room_type": {"type": "string", "description": "Room type (e.g. DOUBLE QUEEN, SINGLE, SUITE)"},
                        "landmark": {"type": "string", "description": "Near specific landmark (e.g. Prado Museum, Airport, City Center)"}
                    },
                    "required": ["city", "checkin", "checkout"]
                }
            },
            {
                "name": "add_loyalty_data",
                "description": "Add a loyalty program number for a specific airline.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "airline": {"type": "string", "description": "Airline code (e.g., UA, AA)"},
                        "number": {"type": "string", "description": "Loyalty program number"}
                    },
                    "required": ["airline", "number"]
                }
            },
            {
                "name": "update_preferences",
                "description": "Update user travel preferences (seat, baggage).",
                "input_schema": {
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
        ]

    async def chat(self, messages: List[Dict[str, str]], user_context: str = "") -> Any:
        """
        Chat with Claude - returns a response compatible with the existing code structure
        """
        # Build system content
        system_content = self.system_prompt
        if user_context:
            system_content += f"\n\nUSER CONTEXT:\n{user_context}"

        # Convert messages from OpenAI format to Anthropic format
        # Filter out system messages (Anthropic handles system separately)
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                continue  # Skip system messages, we handle them separately

            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle tool results (Anthropic format)
            if role == "tool":
                # Convert OpenAI tool result to Anthropic format
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content
                    }]
                })
            elif role == "assistant" and msg.get("tool_calls"):
                # Convert assistant message with tool calls
                content_blocks = []
                if content:
                    content_blocks.append({"type": "text", "text": content})
                for tc in msg.get("tool_calls", []):
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "input": json.loads(tc.get("function", {}).get("arguments", "{}"))
                    })
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            else:
                # Regular message
                if content:
                    anthropic_messages.append({"role": role, "content": content})

        print(f"DEBUG: Sending {len(anthropic_messages)} messages to Claude")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_content,
            messages=anthropic_messages,
            tools=self.tools
        )

        print(f"DEBUG: Claude Response stop_reason: {response.stop_reason}")

        # Convert Claude response to OpenAI-compatible format for existing code
        return ClaudeResponseAdapter(response)


class ClaudeResponseAdapter:
    """
    Adapter to make Claude responses compatible with existing OpenAI-based code
    """
    def __init__(self, claude_response):
        self._response = claude_response
        self._tool_calls = None
        self._content = None
        self._parse_response()

    def _parse_response(self):
        """Parse Claude response into OpenAI-compatible format"""
        tool_calls = []
        text_parts = []

        for block in self._response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                # Convert to OpenAI tool_call format
                tool_calls.append(ToolCallAdapter(
                    id=block.id,
                    name=block.name,
                    arguments=json.dumps(block.input)
                ))

        self._content = "\n".join(text_parts) if text_parts else None
        self._tool_calls = tool_calls if tool_calls else None

        if self._tool_calls:
            print(f"DEBUG: Claude Tool Calls: {[tc.function.name for tc in self._tool_calls]}")
        else:
            print(f"DEBUG: Claude Content: {self._content}")

    @property
    def role(self) -> str:
        return "assistant"

    @property
    def content(self) -> str:
        return self._content or ""

    @property
    def tool_calls(self):
        return self._tool_calls


class ToolCallAdapter:
    """Adapter to make Claude tool_use blocks look like OpenAI tool_calls"""
    def __init__(self, id: str, name: str, arguments: str):
        self.id = id
        self.function = ToolFunction(name=name, arguments=arguments)


class ToolFunction:
    """Adapter for tool function data"""
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments
