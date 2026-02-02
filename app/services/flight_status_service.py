"""
Flight Status Service - Track real-time flight status
Uses AviationStack API (free tier: 100 requests/month)
Fallback: FlightAware or mock data
"""

import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta
import os

class FlightStatusService:
    """Track real-time flight status"""

    def __init__(self):
        self.api_key = os.getenv("AVIATIONSTACK_API_KEY")
        self.base_url = "http://api.aviationstack.com/v1"

    async def get_flight_status(self, flight_number: str, date: str = None) -> Dict:
        """
        Get real-time status for a flight

        Args:
            flight_number: Flight number (e.g., "AM123", "AA100")
            date: Date in YYYY-MM-DD format (optional, defaults to today)

        Returns:
            Flight status data
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Extract airline code and flight number
        airline_code = ""
        number = flight_number

        for i, char in enumerate(flight_number):
            if char.isdigit():
                airline_code = flight_number[:i].upper()
                number = flight_number[i:]
                break

        # If no API key, return mock/estimated data
        if not self.api_key:
            return self._get_mock_status(flight_number, airline_code, number, date)

        try:
            url = f"{self.base_url}/flights"
            params = {
                "access_key": self.api_key,
                "flight_iata": flight_number.upper(),
                "flight_date": date
            }

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    return self._get_mock_status(flight_number, airline_code, number, date)

                data = response.json()
                flights = data.get("data", [])

                if not flights:
                    return {"error": f"No se encontró el vuelo {flight_number}"}

                flight = flights[0]

                return {
                    "flight_number": flight_number.upper(),
                    "airline": flight.get("airline", {}).get("name", "N/A"),
                    "status": self._translate_status(flight.get("flight_status", "scheduled")),
                    "departure": {
                        "airport": flight.get("departure", {}).get("airport", "N/A"),
                        "iata": flight.get("departure", {}).get("iata", "N/A"),
                        "scheduled": flight.get("departure", {}).get("scheduled", "N/A"),
                        "actual": flight.get("departure", {}).get("actual"),
                        "terminal": flight.get("departure", {}).get("terminal"),
                        "gate": flight.get("departure", {}).get("gate"),
                    },
                    "arrival": {
                        "airport": flight.get("arrival", {}).get("airport", "N/A"),
                        "iata": flight.get("arrival", {}).get("iata", "N/A"),
                        "scheduled": flight.get("arrival", {}).get("scheduled", "N/A"),
                        "actual": flight.get("arrival", {}).get("actual"),
                        "terminal": flight.get("arrival", {}).get("terminal"),
                        "gate": flight.get("arrival", {}).get("gate"),
                    }
                }

        except Exception as e:
            print(f"Flight status API error: {e}")
            return self._get_mock_status(flight_number, airline_code, number, date)

    def _get_mock_status(self, flight_number: str, airline: str, number: str, date: str) -> Dict:
        """Generate mock flight status when API is unavailable"""

        # Airline names
        airlines = {
            "AM": "Aeroméxico", "Y4": "Volaris", "VB": "VivaAerobus",
            "AA": "American Airlines", "UA": "United Airlines", "DL": "Delta",
            "IB": "Iberia", "BA": "British Airways", "AF": "Air France"
        }

        airline_name = airlines.get(airline, f"{airline} Airlines")

        return {
            "flight_number": flight_number.upper(),
            "airline": airline_name,
            "status": "En horario",
            "departure": {
                "airport": "Consulta en aerolínea",
                "iata": "---",
                "scheduled": f"{date}T08:00:00",
                "actual": None,
                "terminal": "Consultar",
                "gate": "Consultar",
            },
            "arrival": {
                "airport": "Consulta en aerolínea",
                "iata": "---",
                "scheduled": f"{date}T12:00:00",
                "actual": None,
                "terminal": "Consultar",
                "gate": "Consultar",
            },
            "note": "Para información exacta, consulta la app de la aerolínea"
        }

    def _translate_status(self, status: str) -> str:
        """Translate flight status to Spanish"""
        translations = {
            "scheduled": "Programado",
            "active": "En vuelo",
            "landed": "Aterrizó",
            "cancelled": "Cancelado",
            "incident": "Incidente",
            "diverted": "Desviado",
            "delayed": "Retrasado",
        }
        return translations.get(status.lower(), status)

    def format_for_whatsapp(self, status: Dict) -> str:
        """Format flight status for WhatsApp"""
        if status.get("error"):
            return f"No pude obtener el estado: {status['error']}"

        flight = status.get("flight_number", "N/A")
        airline = status.get("airline", "N/A")
        flight_status = status.get("status", "N/A")
        dep = status.get("departure", {})
        arr = status.get("arrival", {})

        # Status emoji
        status_emoji = {
            "Programado": "🟢", "En horario": "🟢",
            "En vuelo": "✈️", "Aterrizó": "🛬",
            "Retrasado": "🟡", "Cancelado": "🔴", "Desviado": "🟠"
        }
        emoji = status_emoji.get(flight_status, "⚪")

        msg = f"*Estado del vuelo {flight}*\n"
        msg += f"{airline}\n\n"
        msg += f"{emoji} *{flight_status}*\n\n"

        # Departure
        msg += f"*Salida:* {dep.get('iata', 'N/A')}\n"
        scheduled = dep.get('scheduled', '')
        if scheduled and 'T' in scheduled:
            try:
                dt = datetime.fromisoformat(scheduled.replace('Z', '+00:00'))
                msg += f"Programado: {dt.strftime('%H:%M')}\n"
            except:
                msg += f"Programado: {scheduled}\n"
        if dep.get('terminal'):
            msg += f"Terminal: {dep['terminal']}\n"
        if dep.get('gate'):
            msg += f"Puerta: {dep['gate']}\n"

        msg += "\n"

        # Arrival
        msg += f"*Llegada:* {arr.get('iata', 'N/A')}\n"
        scheduled = arr.get('scheduled', '')
        if scheduled and 'T' in scheduled:
            try:
                dt = datetime.fromisoformat(scheduled.replace('Z', '+00:00'))
                msg += f"Programado: {dt.strftime('%H:%M')}\n"
            except:
                msg += f"Programado: {scheduled}\n"
        if arr.get('terminal'):
            msg += f"Terminal: {arr['terminal']}\n"
        if arr.get('gate'):
            msg += f"Puerta: {arr['gate']}\n"

        if status.get("note"):
            msg += f"\n_{status['note']}_"

        return msg
