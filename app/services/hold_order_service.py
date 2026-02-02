"""
Hold Order Service - Reserve flights without immediate payment (24h hold)
"""

import os
import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta

class HoldOrderService:
    """Create hold orders - reserve without paying for 24h"""

    def __init__(self):
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Duffel-Version": "v2"
        }

    async def check_hold_availability(self, offer_id: str) -> Dict:
        """
        Check if an offer supports hold/pay later

        Args:
            offer_id: Duffel offer ID

        Returns:
            Hold availability and conditions
        """
        try:
            url = f"{self.base_url}/air/offers/{offer_id}"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return {"available": False, "error": "No se pudo verificar el vuelo"}

                data = response.json().get("data", {})

                # Check payment requirements
                payment_requirements = data.get("payment_requirements", {})
                requires_instant_payment = payment_requirements.get("requires_instant_payment", True)
                price_guarantee_expires = payment_requirements.get("price_guarantee_expires_at")

                if requires_instant_payment:
                    return {
                        "available": False,
                        "message": "Este vuelo requiere pago inmediato, no permite reservar sin pagar."
                    }

                # Calculate hold duration
                hold_hours = 24
                if price_guarantee_expires:
                    try:
                        expires = datetime.fromisoformat(price_guarantee_expires.replace('Z', '+00:00'))
                        now = datetime.now(expires.tzinfo)
                        hours_remaining = (expires - now).total_seconds() / 3600
                        hold_hours = max(1, int(hours_remaining))
                    except:
                        pass

                return {
                    "available": True,
                    "hold_hours": hold_hours,
                    "expires_at": price_guarantee_expires,
                    "message": f"Puedes reservar este vuelo y pagar después (hasta {hold_hours}h)"
                }

        except Exception as e:
            print(f"Error checking hold: {e}")
            return {"available": False, "error": str(e)}

    async def create_hold_order(
        self,
        offer_id: str,
        passengers: list,
        metadata: Dict = None
    ) -> Dict:
        """
        Create a held order (reserve without paying)

        Args:
            offer_id: Duffel offer ID
            passengers: List of passenger details
            metadata: Optional booking metadata

        Returns:
            Hold order details
        """
        try:
            # First check if hold is available
            hold_check = await self.check_hold_availability(offer_id)
            if not hold_check.get("available"):
                return {"success": False, "error": hold_check.get("message", "Hold no disponible")}

            url = f"{self.base_url}/air/orders"
            payload = {
                "data": {
                    "type": "hold",  # This creates a hold order instead of instant payment
                    "selected_offers": [offer_id],
                    "passengers": passengers,
                }
            }

            if metadata:
                payload["data"]["metadata"] = metadata

            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code not in [200, 201]:
                    error_data = response.json()
                    error_msg = error_data.get("errors", [{}])[0].get("message", "Error al crear reserva")
                    return {"success": False, "error": error_msg}

                data = response.json().get("data", {})

                return {
                    "success": True,
                    "order_id": data.get("id"),
                    "booking_reference": data.get("booking_reference"),
                    "payment_required_by": data.get("payment_required_by"),
                    "total_amount": data.get("total_amount"),
                    "total_currency": data.get("total_currency"),
                    "message": f"Reserva creada. Debes pagar antes de: {data.get('payment_required_by', 'N/A')}"
                }

        except Exception as e:
            print(f"Error creating hold order: {e}")
            return {"success": False, "error": str(e)}

    async def pay_held_order(self, order_id: str, payment_info: Dict) -> Dict:
        """
        Complete payment for a held order

        Args:
            order_id: Duffel order ID
            payment_info: Payment details

        Returns:
            Payment result
        """
        try:
            url = f"{self.base_url}/air/payments"
            payload = {
                "data": {
                    "order_id": order_id,
                    "payment": {
                        "type": "balance",  # Use Duffel balance
                        "currency": payment_info.get("currency", "USD"),
                        "amount": payment_info.get("amount")
                    }
                }
            }

            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code not in [200, 201]:
                    error_data = response.json()
                    error_msg = error_data.get("errors", [{}])[0].get("message", "Error de pago")
                    return {"success": False, "error": error_msg}

                return {
                    "success": True,
                    "message": "Pago completado. Tu reserva está confirmada."
                }

        except Exception as e:
            print(f"Error paying order: {e}")
            return {"success": False, "error": str(e)}

    async def get_held_orders(self, user_id: str, db) -> list:
        """Get user's held orders that need payment"""
        from app.models.models import Trip, TripStatusEnum

        trips = db.query(Trip).filter(
            Trip.user_id == user_id,
            Trip.status == TripStatusEnum.PENDING  # Assuming PENDING = held
        ).all()

        return [
            {
                "order_id": t.duffel_order_id,
                "pnr": t.booking_reference,
                "route": f"{t.departure_city} → {t.arrival_city}",
                "amount": t.total_amount,
                "created_at": t.created_at
            }
            for t in trips if t.duffel_order_id
        ]

    def format_hold_for_whatsapp(self, hold_info: Dict) -> str:
        """Format hold order info for WhatsApp"""
        if hold_info.get("error"):
            return f"❌ {hold_info['error']}"

        if not hold_info.get("success"):
            return f"❌ No se pudo crear la reserva: {hold_info.get('error', 'Error desconocido')}"

        msg = "✅ *Reserva creada (pendiente de pago)*\n\n"
        msg += f"PNR: *{hold_info.get('booking_reference', 'N/A')}*\n"
        msg += f"Total: ${hold_info.get('total_amount', 'N/A')} {hold_info.get('total_currency', '')}\n\n"

        payment_by = hold_info.get('payment_required_by', '')
        if payment_by:
            try:
                dt = datetime.fromisoformat(payment_by.replace('Z', '+00:00'))
                msg += f"⏰ *Pagar antes de:* {dt.strftime('%d/%m/%Y %H:%M')}\n\n"
            except:
                msg += f"⏰ *Pagar antes de:* {payment_by}\n\n"

        msg += "_Si no pagas a tiempo, la reserva se cancelará automáticamente._\n\n"
        msg += "Para pagar escribe: 'pagar [PNR]'"

        return msg
