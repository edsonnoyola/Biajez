"""
Hold Order Service - Reserve flights without immediate payment
Duffel docs: Holding Orders and Paying Later
"""

import os
import httpx
from typing import Dict, Optional
from datetime import datetime


class HoldOrderService:
    """Create hold orders - reserve without paying, pay later before expiry"""

    def __init__(self):
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Duffel-Version": "v2"
        }

    async def check_hold_availability(self, offer_id: str) -> Dict:
        """
        Check if an offer supports hold/pay later.
        Checks payment_requirements.requires_instant_payment on the offer.
        """
        try:
            url = f"{self.base_url}/air/offers/{offer_id}"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return {"available": False, "error": "No se pudo verificar el vuelo"}

                data = response.json().get("data", {})

                # Check payment_requirements per Duffel docs
                payment_req = data.get("payment_requirements", {})
                requires_instant = payment_req.get("requires_instant_payment", True)
                price_guarantee = payment_req.get("price_guarantee_expires_at")
                payment_required_by = payment_req.get("payment_required_by")

                if requires_instant:
                    return {
                        "available": False,
                        "message": "Este vuelo requiere pago inmediato."
                    }

                # Calculate hold duration from payment_required_by
                hold_hours = 24
                deadline_str = ""
                if payment_required_by:
                    try:
                        expires = datetime.fromisoformat(payment_required_by.replace('Z', '+00:00'))
                        now = datetime.now(expires.tzinfo)
                        hours_remaining = (expires - now).total_seconds() / 3600
                        hold_hours = max(1, int(hours_remaining))
                        deadline_str = expires.strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        pass

                has_price_guarantee = price_guarantee is not None

                return {
                    "available": True,
                    "hold_hours": hold_hours,
                    "payment_required_by": payment_required_by,
                    "price_guarantee_expires_at": price_guarantee,
                    "has_price_guarantee": has_price_guarantee,
                    "deadline_str": deadline_str,
                    "message": f"Puedes apartar este vuelo y pagar despues ({hold_hours}h)"
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
        Create a held order (type: "hold", no payments key).
        Per Duffel docs: omit payments key entirely for hold orders.
        """
        try:
            url = f"{self.base_url}/air/orders"
            payload = {
                "data": {
                    "type": "hold",
                    "selected_offers": [offer_id],
                    "passengers": passengers,
                }
            }

            if metadata:
                payload["data"]["metadata"] = metadata

            print(f"🔒 Creating hold order for offer {offer_id}")

            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code not in [200, 201]:
                    error_data = response.json()
                    errors = error_data.get("errors", [{}])
                    error_msg = errors[0].get("message", "Error al crear reserva") if errors else "Error desconocido"
                    print(f"❌ Hold order failed: {error_msg}")
                    return {"success": False, "error": error_msg}

                data = response.json().get("data", {})

                # payment_status is where Duffel puts hold order timing info
                payment_status = data.get("payment_status", {})

                result = {
                    "success": True,
                    "order_id": data.get("id"),
                    "booking_reference": data.get("booking_reference"),
                    "total_amount": data.get("total_amount"),
                    "total_currency": data.get("total_currency"),
                    "awaiting_payment": payment_status.get("awaiting_payment", True),
                    "payment_required_by": payment_status.get("payment_required_by"),
                    "price_guarantee_expires_at": payment_status.get("price_guarantee_expires_at"),
                }

                print(f"✅ Hold order created: {result['order_id']} PNR: {result['booking_reference']}")
                return result

        except Exception as e:
            print(f"Error creating hold order: {e}")
            return {"success": False, "error": str(e)}

    async def pay_held_order(self, order_id: str) -> Dict:
        """
        Pay for a held order.
        Per Duffel docs: ALWAYS re-fetch order to get latest price before paying.
        Uses POST /air/payments with order's current total_amount and total_currency.
        """
        try:
            # Step 1: Re-fetch order to get latest price (required by Duffel)
            order_url = f"{self.base_url}/air/orders/{order_id}"
            async with httpx.AsyncClient(timeout=30) as client:
                order_resp = await client.get(order_url, headers=self.headers)

                if order_resp.status_code != 200:
                    return {"success": False, "error": "No se pudo obtener la orden"}

                order_data = order_resp.json().get("data", {})
                payment_status = order_data.get("payment_status", {})

                # Check if still awaiting payment
                if not payment_status.get("awaiting_payment", False):
                    return {"success": False, "error": "Esta orden ya fue pagada o expirada."}

                # Get latest price from order
                latest_amount = order_data.get("total_amount")
                latest_currency = order_data.get("total_currency")

                if not latest_amount or not latest_currency:
                    return {"success": False, "error": "No se pudo obtener el precio actual"}

                print(f"💳 Paying held order {order_id}: ${latest_amount} {latest_currency}")

            # Step 2: Create payment with latest price
            pay_url = f"{self.base_url}/air/payments"
            pay_payload = {
                "data": {
                    "order_id": order_id,
                    "payment": {
                        "type": "balance",
                        "amount": latest_amount,
                        "currency": latest_currency
                    }
                }
            }

            async with httpx.AsyncClient(timeout=60) as client:
                pay_resp = await client.post(pay_url, headers=self.headers, json=pay_payload)

                if pay_resp.status_code not in [200, 201]:
                    error_data = pay_resp.json()
                    errors = error_data.get("errors", [{}])
                    error_msg = errors[0].get("message", "Error de pago") if errors else "Error desconocido"

                    # Handle price_changed error per Duffel docs
                    error_type = errors[0].get("type", "") if errors else ""
                    if "price_changed" in error_type.lower():
                        return {
                            "success": False,
                            "error": "El precio cambio. Intenta de nuevo.",
                            "price_changed": True
                        }

                    return {"success": False, "error": error_msg}

                # Step 3: Verify payment by re-fetching order
                verify_resp = await client.get(order_url, headers=self.headers)
                documents = []
                if verify_resp.status_code == 200:
                    verify_data = verify_resp.json().get("data", {})
                    documents = verify_data.get("documents", [])

                print(f"✅ Payment completed for {order_id}")

                return {
                    "success": True,
                    "order_id": order_id,
                    "amount_paid": latest_amount,
                    "currency": latest_currency,
                    "documents": documents,
                    "booking_reference": order_data.get("booking_reference"),
                }

        except Exception as e:
            print(f"Error paying order: {e}")
            return {"success": False, "error": str(e)}

    async def get_order_status(self, order_id: str) -> Dict:
        """Get current status of a held order (price, awaiting_payment, deadline)"""
        try:
            url = f"{self.base_url}/air/orders/{order_id}"
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return {"success": False, "error": "No se pudo obtener la orden"}

                data = response.json().get("data", {})
                payment_status = data.get("payment_status", {})

                return {
                    "success": True,
                    "order_id": data.get("id"),
                    "booking_reference": data.get("booking_reference"),
                    "total_amount": data.get("total_amount"),
                    "total_currency": data.get("total_currency"),
                    "awaiting_payment": payment_status.get("awaiting_payment", False),
                    "payment_required_by": payment_status.get("payment_required_by"),
                    "price_guarantee_expires_at": payment_status.get("price_guarantee_expires_at"),
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def format_hold_for_whatsapp(self, hold_info: Dict) -> str:
        """Format hold order info for WhatsApp"""
        if not hold_info.get("success"):
            return f"❌ {hold_info.get('error', 'Error desconocido')}"

        pnr = hold_info.get('booking_reference', 'N/A')
        amount = hold_info.get('total_amount', 'N/A')
        currency = hold_info.get('total_currency', '')

        msg = "✅ *Vuelo apartado (pendiente de pago)*\n\n"
        msg += f"PNR: *{pnr}*\n"
        msg += f"Total: ${amount} {currency}\n\n"

        payment_by = hold_info.get('payment_required_by', '')
        if payment_by:
            try:
                dt = datetime.fromisoformat(payment_by.replace('Z', '+00:00'))
                msg += f"Pagar antes de: *{dt.strftime('%d/%m/%Y %H:%M')}*\n\n"
            except Exception:
                msg += f"Pagar antes de: *{payment_by}*\n\n"

        msg += "_Si no pagas a tiempo se cancela automaticamente._\n\n"
        msg += "Escribe *pagar* cuando estes listo."

        return msg

    def format_payment_for_whatsapp(self, pay_info: Dict) -> str:
        """Format payment confirmation for WhatsApp"""
        if not pay_info.get("success"):
            return f"❌ {pay_info.get('error', 'Error de pago')}"

        pnr = pay_info.get('booking_reference', 'N/A')
        amount = pay_info.get('amount_paid', 'N/A')
        currency = pay_info.get('currency', '')

        msg = "✅ *Pago completado*\n\n"
        msg += f"PNR: *{pnr}*\n"
        msg += f"Pagado: ${amount} {currency}\n"

        # Show eticket if issued
        docs = pay_info.get('documents', [])
        for doc in docs:
            if doc.get('type') == 'electronic_ticket':
                msg += f"eTicket: {doc.get('unique_identifier', '')}\n"

        msg += "\nTu reserva esta confirmada."

        return msg
