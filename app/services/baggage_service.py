"""
Baggage Service - Handles baggage options and additions via Duffel API
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.models import Trip


class BaggageService:
    """Service for managing baggage options and purchases"""

    def __init__(self, db: Session):
        self.db = db
        self.duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.duffel_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Duffel-Version": "v2"
        }

    def get_baggage_options(self, order_id: str) -> Dict:
        """
        Get available baggage options for an existing order

        Args:
            order_id: Duffel order ID (ord_xxxx)

        Returns:
            Dict with available baggage services and current baggage info
        """
        try:
            # First get order details to see current baggage
            order_url = f"{self.base_url}/air/orders/{order_id}"
            order_response = requests.get(order_url, headers=self.headers)

            if order_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Could not retrieve order: {order_response.text}"
                }

            order_data = order_response.json()["data"]

            # Get available services for this order
            services_url = f"{self.base_url}/air/orders/{order_id}/available_services"
            services_response = requests.get(services_url, headers=self.headers)

            baggage_options = []
            current_baggage = []

            # Extract current baggage from slices
            for slice_data in order_data.get("slices", []):
                for segment in slice_data.get("segments", []):
                    for passenger in segment.get("passengers", []):
                        for bag in passenger.get("baggages", []):
                            current_baggage.append({
                                "type": bag.get("type"),
                                "quantity": bag.get("quantity"),
                                "segment": f"{segment.get('origin', {}).get('iata_code')} → {segment.get('destination', {}).get('iata_code')}"
                            })

            if services_response.status_code == 200:
                services_data = services_response.json()["data"]

                for service in services_data:
                    if service.get("type") == "baggage":
                        metadata = service.get("metadata") or {}
                        baggage_options.append({
                            "id": service.get("id"),
                            "price": service.get("total_amount"),
                            "currency": service.get("total_currency"),
                            "description": self._format_baggage_description(service),
                            "weight_kg": metadata.get("maximum_weight_kg"),
                            "max_quantity": service.get("maximum_quantity", 1),
                            "bag_type": metadata.get("type", "checked"),
                            "segment_ids": service.get("segment_ids", []),
                            "passenger_ids": service.get("passenger_ids", [])
                        })

            return {
                "success": True,
                "order_id": order_id,
                "current_baggage": current_baggage,
                "available_options": baggage_options,
                "booking_reference": order_data.get("booking_reference")
            }

        except Exception as e:
            print(f"Error getting baggage options: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def add_baggage(self, order_id: str, service_ids: List[str],
                    service_prices: Optional[List[Dict]] = None) -> Dict:
        """
        Add baggage services to an existing order.

        Duffel requires payment.amount and payment.currency in the payload.
        If service_prices not provided, fetches available_services to look up prices.

        Args:
            order_id: Duffel order ID
            service_ids: List of baggage service IDs to add
            service_prices: Optional list of {"id": ..., "amount": ..., "currency": ...}

        Returns:
            Dict with result of the operation
        """
        try:
            url = f"{self.base_url}/air/orders/{order_id}/services"

            # Build price lookup: need amount+currency for payment
            price_map = {}
            if service_prices:
                for sp in service_prices:
                    price_map[sp["id"]] = {"amount": sp["amount"], "currency": sp["currency"]}
            else:
                # Fetch available services to get prices
                avail_url = f"{self.base_url}/air/orders/{order_id}/available_services"
                avail_resp = requests.get(avail_url, headers=self.headers)
                if avail_resp.status_code == 200:
                    for svc in avail_resp.json().get("data", []):
                        price_map[svc["id"]] = {
                            "amount": svc.get("total_amount", "0"),
                            "currency": svc.get("total_currency", "USD")
                        }

            # Calculate total payment amount (amount * quantity per service)
            total_amount = 0.0
            payment_currency = "USD"
            services_to_add = []
            for sid in service_ids:
                qty = 1
                services_to_add.append({"id": sid, "quantity": qty})
                if sid in price_map:
                    total_amount += float(price_map[sid]["amount"]) * qty
                    payment_currency = price_map[sid]["currency"]

            payload = {
                "data": {
                    "add_services": services_to_add,
                    "payment": {
                        "type": "balance",
                        "currency": payment_currency,
                        "amount": f"{total_amount:.2f}"
                    }
                }
            }

            print(f"🧳 Adding baggage to {order_id}: {len(service_ids)} services, total ${total_amount:.2f} {payment_currency}")
            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code in [200, 201]:
                result = response.json()["data"]

                # Update trip in database using raw SQL (ORM doesn't persist on Render)
                try:
                    from app.db.database import engine
                    from sqlalchemy import text
                    with engine.connect() as conn:
                        row = conn.execute(
                            text("SELECT baggage_services FROM trips WHERE duffel_order_id = :oid"),
                            {"oid": order_id}
                        ).fetchone()
                        if row:
                            existing_services = json.loads(row[0] or "[]")
                            existing_services.extend(service_ids)
                            conn.execute(
                                text("UPDATE trips SET baggage_services = :bs WHERE duffel_order_id = :oid"),
                                {"bs": json.dumps(existing_services), "oid": order_id}
                            )
                            conn.commit()
                except Exception as db_err:
                    print(f"⚠️ Baggage DB update failed (non-critical): {db_err}")

                return {
                    "success": True,
                    "order_id": order_id,
                    "added_services": service_ids,
                    "new_total": result.get("total_amount"),
                    "currency": result.get("total_currency")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add baggage: {response.text}"
                }

        except Exception as e:
            print(f"Error adding baggage: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_trip_baggage(self, pnr: str) -> Dict:
        """
        Get baggage info for a trip by PNR
        """
        trip = self.db.query(Trip).filter(Trip.booking_reference == pnr).first()

        if not trip:
            return {"success": False, "error": "Trip not found"}

        if trip.duffel_order_id:
            return self.get_baggage_options(trip.duffel_order_id)

        # For non-Duffel bookings, return stored baggage data
        return {
            "success": True,
            "pnr": pnr,
            "current_baggage": json.loads(trip.baggage_services or "[]"),
            "available_options": [],
            "note": "Baggage modifications not available for this booking provider"
        }

    def _format_baggage_description(self, service: Dict) -> str:
        """Format a human-readable baggage description"""
        metadata = service.get("metadata", {})
        weight = metadata.get("maximum_weight_kg")
        bag_type = metadata.get("type", "checked")

        if weight:
            return f"{bag_type.title()} bag - up to {weight}kg"
        return f"{bag_type.title()} bag"

    def format_baggage_for_whatsapp(self, baggage_data: Dict) -> str:
        """Format baggage information for WhatsApp - concise Spanish"""
        if not baggage_data.get("success"):
            return "No pude obtener info de equipaje.\n\nIntenta de nuevo o escribe 'ayuda'."

        lines = ["*Tu equipaje*\n"]

        # Current baggage - translate types
        type_names = {
            "carry_on": "Mano",
            "checked": "Documentada",
            "personal_item": "Personal"
        }

        if baggage_data.get("current_baggage"):
            for bag in baggage_data["current_baggage"]:
                bag_type = type_names.get(bag.get('type', ''), bag.get('type', 'Maleta'))
                qty = bag.get('quantity', 1)
                segment = bag.get('segment', '')
                lines.append(f"{qty}x {bag_type}")
            lines.append("")

        # Available options
        bag_type_names = {
            "carry_on": "Mano",
            "checked": "Documentada",
            "personal_item": "Personal"
        }
        if baggage_data.get("available_options"):
            lines.append("*Agregar:*")
            for i, option in enumerate(baggage_data["available_options"][:5], 1):
                price = option.get("price", "0")
                currency = option.get("currency", "USD")
                weight = option.get("weight_kg", "")
                bag_type = bag_type_names.get(option.get("bag_type", ""), "Maleta")
                weight_str = f" {weight}kg" if weight else ""
                lines.append(f"{i}. {bag_type}{weight_str} - ${price} {currency}")
        else:
            lines.append("Sin opciones adicionales")

        return "\n".join(lines)

    def format_baggage_buttons(self, baggage_data: Dict) -> list:
        """Get interactive buttons for baggage"""
        buttons = []

        if baggage_data.get("available_options"):
            buttons.append({"id": "btn_add_bag", "title": "Agregar maleta"})

        buttons.append({"id": "btn_itinerario", "title": "Ver itinerario"})

        if len(buttons) < 3:
            buttons.append({"id": "btn_ayuda", "title": "Ayuda"})

        return buttons
