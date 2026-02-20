"""
Ancillary Services - Add meals, WiFi, priority boarding, etc. to bookings
"""

import os
import httpx
from typing import Dict, List, Optional

class AncillaryService:
    """Manage ancillary services like meals, WiFi, priority boarding"""

    SERVICE_TYPES = {
        "meal": "Comida",
        "wifi": "WiFi",
        "priority_boarding": "Embarque prioritario",
        "lounge_access": "Acceso a sala VIP",
        "extra_legroom": "Espacio extra",
        "seat_selection": "Selección de asiento",
        "checked_bag": "Maleta documentada",
        "carry_on": "Equipaje de mano",
    }

    MEAL_OPTIONS = {
        "STANDARD": "Comida estándar",
        "VEGETARIAN": "Vegetariano",
        "VEGAN": "Vegano",
        "KOSHER": "Kosher",
        "HALAL": "Halal",
        "GLUTEN_FREE": "Sin gluten",
        "CHILD": "Menú infantil",
        "DIABETIC": "Diabético",
    }

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

    async def get_available_services(self, offer_id: str) -> Dict:
        """
        Get available ancillary services for a flight offer

        Args:
            offer_id: Duffel offer ID

        Returns:
            Available services with prices
        """
        try:
            url = f"{self.base_url}/air/offers/{offer_id}/available_services"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return {"error": f"No se pudieron obtener servicios: {response.status_code}"}

                data = response.json()
                services = data.get("data", [])

                # Categorize services
                result = {
                    "meals": [],
                    "bags": [],
                    "seats": [],
                    "other": []
                }

                for service in services:
                    service_type = service.get("type", "")
                    service_info = {
                        "id": service.get("id"),
                        "type": service_type,
                        "price": service.get("total_amount"),
                        "currency": service.get("total_currency"),
                        "description": service.get("metadata", {}).get("description", ""),
                        "segment_id": service.get("segment_id"),
                    }

                    if "meal" in service_type.lower():
                        service_info["meal_type"] = service.get("metadata", {}).get("meal_type", "STANDARD")
                        result["meals"].append(service_info)
                    elif "bag" in service_type.lower():
                        service_info["weight"] = service.get("metadata", {}).get("maximum_weight_kg")
                        result["bags"].append(service_info)
                    elif "seat" in service_type.lower():
                        result["seats"].append(service_info)
                    else:
                        result["other"].append(service_info)

                return result

        except Exception as e:
            print(f"Error getting services: {e}")
            return {"error": str(e)}

    async def add_service_to_order(self, order_id: str, service_ids: List[str]) -> Dict:
        """
        Add ancillary services to an existing order

        Args:
            order_id: Duffel order ID
            service_ids: List of service IDs to add

        Returns:
            Result of adding services
        """
        try:
            url = f"{self.base_url}/air/orders/{order_id}/services"
            payload = {
                "data": {
                    "add_services": [{"id": sid} for sid in service_ids]
                }
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code not in [200, 201]:
                    error = response.json().get("errors", [{}])[0].get("message", "Error")
                    return {"success": False, "error": error}

                return {"success": True, "message": "Servicios agregados correctamente"}

        except Exception as e:
            print(f"Error adding service: {e}")
            return {"success": False, "error": str(e)}

    async def get_order_services(self, order_id: str) -> Dict:
        """Get services already added to an order"""
        try:
            url = f"{self.base_url}/air/orders/{order_id}"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return {"error": "No se pudo obtener la orden"}

                data = response.json().get("data", {})
                services = data.get("services", [])

                return {
                    "services": services,
                    "total_services_amount": sum(float(s.get("total_amount", 0)) for s in services)
                }

        except Exception as e:
            return {"error": str(e)}

    def format_services_for_whatsapp(self, services: Dict) -> str:
        """Format available services for WhatsApp"""
        if services.get("error"):
            return f"No pude obtener servicios: {services['error']}"

        msg = "*Servicios adicionales disponibles*\n\n"
        has_services = False

        # Meals
        if services.get("meals"):
            has_services = True
            msg += "*🍽️ Comidas:*\n"
            for i, meal in enumerate(services["meals"][:5], 1):
                meal_name = self.MEAL_OPTIONS.get(meal.get("meal_type"), meal.get("meal_type", "Comida"))
                msg += f"{i}. {meal_name} - ${meal['price']} {meal['currency']}\n"
            msg += "\n"

        # Bags
        if services.get("bags"):
            has_services = True
            msg += "*🧳 Equipaje:*\n"
            for i, bag in enumerate(services["bags"][:3], 1):
                weight = f"{bag.get('weight')}kg" if bag.get('weight') else ""
                msg += f"{i}. Maleta {weight} - ${bag['price']} {bag['currency']}\n"
            msg += "\n"

        # Seats
        if services.get("seats"):
            has_services = True
            msg += "*💺 Asientos:*\n"
            msg += f"Hay {len(services['seats'])} asientos disponibles\n"
            msg += "Escribe 'asientos' para ver el mapa\n\n"

        # Other
        if services.get("other"):
            has_services = True
            msg += "*✨ Otros:*\n"
            for service in services["other"][:3]:
                msg += f"• {service.get('description', service['type'])} - ${service['price']} {service['currency']}\n"

        if not has_services:
            msg += "No hay servicios adicionales disponibles para este vuelo."
        else:
            msg += "\n_Responde con el servicio que quieres agregar_"

        return msg
