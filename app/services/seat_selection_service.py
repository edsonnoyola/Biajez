"""
Seat Selection Service - Get available seats and select seats via Duffel
"""

import os
import httpx
from typing import Dict, List, Optional

class SeatSelectionService:
    """Handle seat selection for flight bookings"""

    def __init__(self):
        self.api_key = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json"
        }

    async def get_seat_map(self, offer_id: str) -> Dict:
        """
        Get seat map for a flight offer

        Args:
            offer_id: Duffel offer ID

        Returns:
            Seat map data
        """
        try:
            url = f"{self.base_url}/air/seat_maps"
            params = {"offer_id": offer_id}

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code != 200:
                    return {"error": f"Could not get seat map: {response.status_code}"}

                data = response.json()
                seat_maps = data.get("data", [])

                if not seat_maps:
                    return {"error": "No seat map available for this flight"}

                # Process seat maps
                result = {
                    "segments": [],
                    "total_segments": len(seat_maps)
                }

                for sm in seat_maps:
                    segment_data = {
                        "segment_id": sm.get("segment_id"),
                        "aircraft": sm.get("aircraft", {}).get("name", "N/A"),
                        "cabins": []
                    }

                    for cabin in sm.get("cabins", []):
                        cabin_data = {
                            "cabin_class": cabin.get("cabin_class", "N/A"),
                            "rows": []
                        }

                        for row in cabin.get("rows", []):
                            row_data = {
                                "row_number": row.get("row_number"),
                                "seats": []
                            }

                            for seat in row.get("sections", []):
                                for s in seat.get("elements", []):
                                    if s.get("type") == "seat":
                                        seat_info = {
                                            "designator": s.get("designator"),
                                            "available": s.get("available_services", []) != [],
                                            "price": None,
                                            "features": []
                                        }

                                        # Get price if available
                                        services = s.get("available_services", [])
                                        if services:
                                            seat_info["price"] = services[0].get("total_amount")
                                            seat_info["currency"] = services[0].get("total_currency")
                                            seat_info["service_id"] = services[0].get("id")

                                        # Get features
                                        if s.get("is_exit_row"):
                                            seat_info["features"].append("exit_row")
                                        if s.get("has_extra_legroom"):
                                            seat_info["features"].append("extra_legroom")
                                        if "window" in s.get("designator", "").lower() or s.get("designator", "")[-1] in ["A", "F", "K"]:
                                            seat_info["features"].append("window")
                                        if s.get("designator", "")[-1] in ["C", "D", "G", "H"]:
                                            seat_info["features"].append("aisle")

                                        row_data["seats"].append(seat_info)

                            if row_data["seats"]:
                                cabin_data["rows"].append(row_data)

                        if cabin_data["rows"]:
                            segment_data["cabins"].append(cabin_data)

                    result["segments"].append(segment_data)

                return result

        except Exception as e:
            print(f"Seat map API error: {e}")
            return {"error": str(e)}

    async def select_seat(self, order_id: str, service_id: str) -> Dict:
        """
        Add a seat selection to an order

        Args:
            order_id: Duffel order ID
            service_id: Seat service ID from seat map

        Returns:
            Selection result
        """
        try:
            url = f"{self.base_url}/air/orders/{order_id}/services"
            payload = {
                "data": {
                    "add_services": [{"id": service_id}]
                }
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code not in [200, 201]:
                    error_data = response.json()
                    return {"error": error_data.get("errors", [{}])[0].get("message", "Failed to select seat")}

                return {"success": True, "message": "Asiento seleccionado correctamente"}

        except Exception as e:
            print(f"Seat selection error: {e}")
            return {"error": str(e)}

    def format_seat_map_for_whatsapp(self, seat_map: Dict, segment_index: int = 0) -> str:
        """Format seat map for WhatsApp (simplified view)"""
        if seat_map.get("error"):
            return f"No pude obtener el mapa de asientos: {seat_map['error']}"

        segments = seat_map.get("segments", [])
        if not segments or segment_index >= len(segments):
            return "No hay mapa de asientos disponible."

        segment = segments[segment_index]
        aircraft = segment.get("aircraft", "N/A")

        msg = f"*Mapa de asientos*\n"
        msg += f"Avión: {aircraft}\n\n"

        # Get available seats summary
        available_window = []
        available_aisle = []
        available_exit = []
        available_extra = []

        for cabin in segment.get("cabins", []):
            for row in cabin.get("rows", []):
                for seat in row.get("seats", []):
                    if seat.get("available"):
                        designator = seat.get("designator", "")
                        features = seat.get("features", [])
                        price = seat.get("price", "")

                        seat_str = f"{designator}"
                        if price:
                            seat_str += f" (${price})"

                        if "exit_row" in features:
                            available_exit.append(seat_str)
                        elif "extra_legroom" in features:
                            available_extra.append(seat_str)
                        elif "window" in features:
                            available_window.append(seat_str)
                        elif "aisle" in features:
                            available_aisle.append(seat_str)

        if available_window:
            msg += f"*Ventana:* {', '.join(available_window[:5])}\n"
        if available_aisle:
            msg += f"*Pasillo:* {', '.join(available_aisle[:5])}\n"
        if available_exit:
            msg += f"*Salida emergencia:* {', '.join(available_exit[:3])}\n"
        if available_extra:
            msg += f"*Espacio extra:* {', '.join(available_extra[:3])}\n"

        if not any([available_window, available_aisle, available_exit, available_extra]):
            msg += "No hay asientos disponibles para selección.\n"
        else:
            msg += "\n_Responde con el asiento que quieres (ej: '12A')_"

        return msg

    def find_seat_service_id(self, seat_map: Dict, designator: str) -> Optional[str]:
        """Find the service ID for a specific seat"""
        for segment in seat_map.get("segments", []):
            for cabin in segment.get("cabins", []):
                for row in cabin.get("rows", []):
                    for seat in row.get("seats", []):
                        if seat.get("designator", "").upper() == designator.upper():
                            return seat.get("service_id")
        return None
