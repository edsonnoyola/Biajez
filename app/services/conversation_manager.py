"""
WhatsApp Conversation State Manager
Handles multi-step conversations for booking flows
"""

class ConversationState:
    """Manages conversation state for WhatsApp users"""
    
    STATES = {
        "IDLE": "idle",
        "ASKING_DESTINATION": "asking_destination",
        "ASKING_DATES": "asking_dates",
        "ASKING_RETURN_DATE": "asking_return_date",
        "ASKING_TRIP_TYPE": "asking_trip_type",
        "SHOWING_FLIGHTS": "showing_flights",
        "CONFIRMING_FLIGHT": "confirming_flight",
        "ASKING_HOTEL": "asking_hotel",
        "ASKING_HOTEL_DATES": "asking_hotel_dates",
        "SHOWING_HOTELS": "showing_hotels",
        "CONFIRMING_HOTEL": "confirming_hotel"
    }
    
    def __init__(self):
        self.state = self.STATES["IDLE"]
        self.data = {}
    
    def set_state(self, state: str, data: dict = None):
        """Set conversation state and optional data"""
        self.state = state
        if data:
            self.data.update(data)
    
    def get_state(self) -> str:
        """Get current state"""
        return self.state
    
    def get_data(self, key: str = None):
        """Get conversation data"""
        if key:
            return self.data.get(key)
        return self.data
    
    def clear(self):
        """Clear conversation state"""
        self.state = self.STATES["IDLE"]
        self.data = {}
    
    def is_idle(self) -> bool:
        """Check if conversation is idle"""
        return self.state == self.STATES["IDLE"]


def parse_destination(text: str) -> str:
    """Extract destination from natural language"""
    text_lower = text.lower()
    
    # Common patterns
    patterns = [
        "quiero ir a ",
        "viajar a ",
        "vuelo a ",
        "vuelos a ",
        "ir a ",
        "a "
    ]
    
    for pattern in patterns:
        if pattern in text_lower:
            destination = text_lower.split(pattern)[1].strip()
            # Get first word (city name)
            destination = destination.split()[0] if destination else ""
            return destination.title()
    
    return None


def parse_date(text: str) -> str:
    """Parse date from natural language to YYYY-MM-DD"""
    from datetime import datetime, timedelta
    import re
    
    text_lower = text.lower().strip()
    
    # Handle relative dates
    if "mañana" in text_lower or "mañana" in text_lower:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    if "pasado mañana" in text_lower:
        return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    if "próxima semana" in text_lower or "proxima semana" in text_lower:
        return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Handle "el 15" or "15"
    day_match = re.search(r'\b(\d{1,2})\b', text_lower)
    if day_match:
        day = int(day_match.group(1))
        # Assume current month if day > today, else next month
        now = datetime.now()
        if day >= now.day:
            date = datetime(now.year, now.month, day)
        else:
            # Next month
            next_month = now.month + 1 if now.month < 12 else 1
            year = now.year if now.month < 12 else now.year + 1
            date = datetime(year, next_month, day)
        return date.strftime("%Y-%m-%d")
    
    # Handle month names
    months = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }
    
    for month_name, month_num in months.items():
        if month_name in text_lower:
            day_match = re.search(r'\b(\d{1,2})\b', text_lower)
            if day_match:
                day = int(day_match.group(1))
                year = datetime.now().year
                # If month has passed, use next year
                if month_num < datetime.now().month:
                    year += 1
                date = datetime(year, month_num, day)
                return date.strftime("%Y-%m-%d")
    
    return None


def format_date_spanish(date_str: str) -> str:
    """Format YYYY-MM-DD to Spanish readable format"""
    from datetime import datetime
    
    months_es = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }
    
    date = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{date.day}-{months_es[date.month]}"
