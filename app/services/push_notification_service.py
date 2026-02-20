"""
Push Notification Service - Proactive WhatsApp message sending
"""
import os
import requests
from typing import Optional


class PushNotificationService:
    """Service for sending proactive WhatsApp notifications"""

    def __init__(self):
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to WhatsApp format"""
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))

        # Handle Mexican numbers (521... → 52...)
        if phone.startswith("521") and len(phone) == 13:
            phone = "52" + phone[3:]

        return phone

    async def send_message(self, phone_number: str, message: str) -> dict:
        """
        Send a simple text message via WhatsApp

        Args:
            phone_number: Recipient phone number
            message: Message text

        Returns:
            Dict with send result
        """
        if not self.access_token or not self.phone_number_id:
            print("WhatsApp credentials not configured")
            return {"success": False, "error": "WhatsApp not configured"}

        phone = self._normalize_phone(phone_number)

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message}
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                return {"success": True, "message_id": response.json().get("messages", [{}])[0].get("id")}
            else:
                print(f"WhatsApp send error: {response.text}")
                return {"success": False, "error": response.text}

        except Exception as e:
            print(f"WhatsApp send exception: {e}")
            return {"success": False, "error": str(e)}

    async def send_checkin_notification(
        self,
        phone_number: str,
        pnr: str,
        seat: Optional[str] = None,
        boarding_pass_url: Optional[str] = None
    ) -> dict:
        """Send check-in confirmation notification - Spanish"""
        message = f"*Check-in listo*\n\n{pnr}"

        if seat:
            message += f"\nAsiento: {seat}"

        if boarding_pass_url:
            message += f"\n\nTu pase de abordar esta listo."

        message += "\n\nBuen viaje!"

        return await self.send_message(phone_number, message)

    async def send_checkin_reminder(
        self,
        phone_number: str,
        pnr: str,
        airline: str,
        checkin_url: Optional[str] = None
    ) -> dict:
        """Send check-in window open reminder with airline link - Spanish"""
        message = f"*Check-in disponible*\n\n"
        message += f"PNR: {pnr}\n"
        message += f"Aerolinea: {airline}\n\n"

        if checkin_url:
            message += f"Haz check-in aqui:\n{checkin_url}\n\n"

        message += "Recuerda:\n"
        message += "- Llegar 2-3h antes al aeropuerto\n"
        message += "- Llevar ID/pasaporte"

        return await self.send_message(phone_number, message)

    async def send_flight_change_alert(
        self,
        phone_number: str,
        pnr: str,
        change_type: str,
        details: dict
    ) -> dict:
        """Send airline-initiated flight change notification - Spanish"""
        message = f"*Cambio en tu vuelo*\n\n{pnr}\n\n"

        if change_type == "schedule_change":
            message += "La aerolinea modifico el horario.\n"
            if details.get("new_departure_time"):
                message += f"Nueva salida: {details['new_departure_time']}\n"
        elif change_type == "cancellation":
            message += "El vuelo fue cancelado.\n"
        else:
            message += "Hubo un cambio en tu reserva.\n"

        message += "\nEscribe 'itinerario' para ver detalles."

        return await self.send_message(phone_number, message)

    async def send_trip_reminder(
        self,
        phone_number: str,
        trip_pnr: str,
        departure_city: str,
        arrival_city: str,
        departure_date: str
    ) -> dict:
        """Send upcoming trip reminder - Spanish"""
        message = (
            f"*Tu vuelo es manana*\n\n"
            f"{departure_city} → {arrival_city}\n"
            f"PNR: {trip_pnr}\n\n"
            f"Recuerda:\n"
            f"- Hacer check-in\n"
            f"- Llegar 2-3h antes\n"
            f"- Llevar ID/pasaporte"
        )

        return await self.send_message(phone_number, message)

    async def send_booking_confirmation(
        self,
        phone_number: str,
        pnr: str,
        route: str,
        departure_date: str,
        total_amount: float,
        currency: str = "USD"
    ) -> dict:
        """Send booking confirmation notification - Spanish"""
        message = (
            f"*Reserva confirmada*\n\n"
            f"{route}\n"
            f"{departure_date}\n"
            f"PNR: {pnr}\n\n"
            f"Total: ${total_amount:.0f} {currency}"
        )

        return await self.send_message(phone_number, message)
