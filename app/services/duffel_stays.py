"""
Duffel Stays API - Search, quote, and book accommodation
Per Duffel docs: 4-step flow: search → fetch rates → quote → book
"""
import os
import requests
from fastapi import HTTPException
from typing import List, Dict, Optional


class DuffelStaysEngine:
    """
    Duffel Stays API integration for hotel search and booking.
    Uses same DUFFEL_ACCESS_TOKEN as flights.

    Flow per docs:
    1. POST /stays/search → get search_result_id per accommodation
    2. GET /stays/search_results/{id}/rates → get all rooms + rates
    3. POST /stays/quotes → get quote_id (confirms availability + price)
    4. POST /stays/bookings → book using quote_id
    """

    def __init__(self):
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com/stays"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Duffel-Version": "v2"
        }

    # City coordinates mapping (major cities)
    CITY_COORDS = {
        "cancun": {"lat": 21.1619, "lng": -86.8515},
        "cdmx": {"lat": 19.4326, "lng": -99.1332},
        "ciudad de mexico": {"lat": 19.4326, "lng": -99.1332},
        "mexico city": {"lat": 19.4326, "lng": -99.1332},
        "guadalajara": {"lat": 20.6597, "lng": -103.3496},
        "monterrey": {"lat": 25.6866, "lng": -100.3161},
        "playa del carmen": {"lat": 20.6296, "lng": -87.0739},
        "tulum": {"lat": 20.2114, "lng": -87.4654},
        "puerto vallarta": {"lat": 20.6534, "lng": -105.2253},
        "los cabos": {"lat": 22.8905, "lng": -109.9167},
        "oaxaca": {"lat": 17.0732, "lng": -96.7266},
        "merida": {"lat": 20.9674, "lng": -89.5926},
        "new york": {"lat": 40.7128, "lng": -74.0060},
        "miami": {"lat": 25.7617, "lng": -80.1918},
        "madrid": {"lat": 40.4168, "lng": -3.7038},
        "barcelona": {"lat": 41.3874, "lng": 2.1686},
        "london": {"lat": 51.5074, "lng": -0.1278},
        "paris": {"lat": 48.8566, "lng": 2.3522},
    }

    # ===== STEP 1: SEARCH =====
    def search_hotels(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int = 1,
        rooms: int = 1,
        radius: float = 5,  # km (per Duffel docs)
        preferred_chains: Optional[str] = None
    ) -> List[Dict]:
        """
        Step 1: Search for hotels.
        Per Duffel docs: POST /stays/search with location, dates, guests, rooms.
        Returns list of accommodations with search_result_id for Step 2.
        """
        location_lower = location.lower().strip()
        coords = self.CITY_COORDS.get(location_lower)
        if not coords:
            # Try partial match
            for city, c in self.CITY_COORDS.items():
                if city in location_lower or location_lower in city:
                    coords = c
                    break
            if not coords:
                coords = self.CITY_COORDS["cancun"]

        search_url = f"{self.base_url}/search"

        # Per Duffel docs: guests is array of {type: "adult"}, radius is number in km
        payload = {
            "data": {
                "location": {
                    "geographic_coordinates": {
                        "latitude": coords["lat"],
                        "longitude": coords["lng"]
                    },
                    "radius": radius
                },
                "check_in_date": check_in,
                "check_out_date": check_out,
                "guests": [{"type": "adult"} for _ in range(guests)],
                "rooms": rooms
            }
        }

        try:
            print(f"🏨 Searching Duffel Stays: {location} ({coords['lat']}, {coords['lng']})")
            response = requests.post(search_url, headers=self.headers, json=payload, timeout=30)

            if response.status_code not in [200, 201]:
                print(f"Duffel Stays Search Error: {response.status_code}")
                return self._get_fallback_hotels(location)

            data = response.json().get("data", {})
            results = data.get("results", [])

            if not results:
                print("No search results found, using fallback")
                return self._get_fallback_hotels(location)

            print(f"🏨 Found {len(results)} accommodations from Duffel Stays")

            hotels = []
            for result in results[:10]:
                accommodation = result.get("accommodation", {})
                search_result_id = result.get("id")
                cheapest_rate = result.get("cheapest_rate_total_amount")
                cheapest_currency = result.get("cheapest_rate_currency", "USD")

                rating_data = accommodation.get("rating", {})
                rating_value = rating_data.get("value", "4") if isinstance(rating_data, dict) else str(rating_data)

                location_data = accommodation.get("location", {})
                address = location_data.get("address", {}) if isinstance(location_data, dict) else {}

                hotel = {
                    "offerId": search_result_id,  # This is search_result_id for Step 2
                    "search_result_id": search_result_id,
                    "accommodation_id": accommodation.get("id"),
                    "name": accommodation.get("name", "Hotel"),
                    "rating": str(rating_value),
                    "address": {
                        "cityName": address.get("city_name", location.title()) if isinstance(address, dict) else location.title(),
                        "countryCode": address.get("country_code", "MX") if isinstance(address, dict) else "MX"
                    },
                    "price": {
                        "total": cheapest_rate or "0",
                        "currency": cheapest_currency
                    },
                    "amenities": [
                        a.get("description", a) if isinstance(a, dict) else str(a)
                        for a in accommodation.get("amenities", [])[:5]
                    ],
                    "photos": [
                        p.get("url", "") if isinstance(p, dict) else str(p)
                        for p in accommodation.get("photos", [])[:3]
                    ],
                    "provider": "DUFFEL_STAYS"
                }
                hotels.append(hotel)

            return hotels if hotels else self._get_fallback_hotels(location)

        except Exception as e:
            print(f"Duffel Stays Search Error: {e}")
            return self._get_fallback_hotels(location)

    # ===== STEP 2: FETCH ALL RATES =====
    def fetch_all_rates(self, search_result_id: str) -> Dict:
        """
        Step 2: Get all available rooms and rates for a search result.
        Per Duffel docs: GET /stays/search_results/{id}/rates
        Returns rooms with their rates (rate_id needed for Step 3).
        """
        url = f"{self.base_url}/search_results/{search_result_id}/rates"

        try:
            print(f"🏨 Fetching rates for search result: {search_result_id}")
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                print(f"Fetch rates error: {response.status_code}")
                return {"success": False, "error": "No se pudieron obtener las tarifas"}

            data = response.json().get("data", {})
            rooms = data.get("rooms", [])

            formatted_rooms = []
            for room in rooms:
                rates = room.get("rates", [])
                for rate in rates:
                    formatted_rooms.append({
                        "rate_id": rate.get("id"),
                        "room_name": room.get("name", "Habitacion"),
                        "room_photos": [p.get("url", "") if isinstance(p, dict) else str(p) for p in room.get("photos", [])[:2]],
                        "total_amount": rate.get("total_amount"),
                        "total_currency": rate.get("total_currency", "USD"),
                        "cancellation_policy": rate.get("cancellation_timeline", []),
                        "board_type": rate.get("board_type", "room_only"),
                        "conditions": rate.get("conditions", {}),
                    })

            print(f"🏨 Found {len(formatted_rooms)} room/rate options")

            return {
                "success": True,
                "search_result_id": search_result_id,
                "rooms": formatted_rooms
            }

        except Exception as e:
            print(f"Error fetching rates: {e}")
            return {"success": False, "error": str(e)}

    # ===== STEP 3: CREATE QUOTE =====
    def create_quote(self, rate_id: str) -> Dict:
        """
        Step 3: Request a final quote for the selected rate.
        Per Duffel docs: POST /stays/quotes with rate_id.
        Confirms availability and final price. Returns quote_id for Step 4.
        """
        url = f"{self.base_url}/quotes"

        payload = {
            "data": {
                "rate_id": rate_id
            }
        }

        try:
            print(f"🏨 Creating quote for rate: {rate_id}")
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code not in [200, 201]:
                print(f"Quote error: {response.status_code}")

                # Parse error type for user-friendly message
                try:
                    err_body = response.json()
                    err_type = err_body.get("errors", [{}])[0].get("type", "").lower()
                    if "unavailable" in err_type or "sold_out" in err_type:
                        return {"success": False, "error": "Esta habitacion ya no esta disponible. Intenta con otra opcion."}
                    if "price" in err_type or "changed" in err_type:
                        return {"success": False, "error": "El precio cambio. Busca de nuevo para ver el precio actualizado."}
                except:
                    pass

                return {"success": False, "error": "No se pudo confirmar la tarifa. Intenta de nuevo."}

            data = response.json().get("data", {})

            if not data.get("id"):
                return {"success": False, "error": "No se obtuvo cotización válida. Intenta de nuevo."}

            return {
                "success": True,
                "quote_id": data.get("id"),
                "total_amount": data.get("total_amount"),
                "total_currency": data.get("total_currency", "USD"),
                "check_in_date": data.get("check_in_date"),
                "check_out_date": data.get("check_out_date"),
                "accommodation": data.get("accommodation", {}),
                "cancellation_timeline": data.get("cancellation_timeline", []),
            }

        except requests.exceptions.Timeout:
            print("Quote request timeout")
            return {"success": False, "error": "La solicitud tardó demasiado. Intenta de nuevo."}
        except Exception as e:
            print(f"Error creating quote: {e}")
            return {"success": False, "error": "No se pudo confirmar la tarifa. Intenta de nuevo."}

    # ===== STEP 4: BOOK =====
    def book_hotel(self, quote_id: str, guest_info: Dict) -> Dict:
        """
        Step 4: Create a booking using the quote_id.
        Per Duffel docs: POST /stays/bookings with quote_id, guests, email, phone.
        """
        # Validate inputs before calling API
        if not quote_id:
            return {"success": False, "error": "No se pudo procesar la reserva. Intenta de nuevo."}

        if not guest_info.get("given_name") or not guest_info.get("family_name"):
            return {"success": False, "error": "Faltan datos del huésped. Verifica tu perfil."}

        url = f"{self.base_url}/bookings"

        payload = {
            "data": {
                "quote_id": quote_id,
                "guests": [{
                    "given_name": guest_info.get("given_name"),
                    "family_name": guest_info.get("family_name"),
                }],
                "email": guest_info.get("email") or "guest@biajez.com",
                "phone_number": guest_info.get("phone_number") or "+15005550100",
            }
        }

        # Add born_on if available (some Duffel accommodations require it)
        if guest_info.get("born_on"):
            payload["data"]["guests"][0]["born_on"] = guest_info["born_on"]

        # Add special requests if provided
        if guest_info.get("special_requests"):
            payload["data"]["accommodation_special_requests"] = guest_info["special_requests"]

        try:
            print(f"🏨 Booking hotel with quote: {quote_id}")
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)

            if response.status_code not in [200, 201]:
                print(f"Booking error: {response.status_code}")
                # Parse error for user-friendly message
                try:
                    err_data = response.json().get("errors", [{}])[0]
                    err_type = err_data.get("type", "")
                    if "expired" in err_type or "invalid" in err_type:
                        return {"success": False, "error": "La cotización expiró. Busca el hotel de nuevo."}
                except:
                    pass
                return {"success": False, "error": "Error al reservar hotel. Intenta de nuevo."}

            booking = response.json().get("data", {})

            return {
                "success": True,
                "booking_id": booking.get("id"),
                "confirmation_number": booking.get("reference"),
                "status": booking.get("status"),
                "accommodation": booking.get("accommodation", {}),
                "total_amount": booking.get("total_amount"),
                "total_currency": booking.get("total_currency"),
                "check_in_date": booking.get("check_in_date"),
                "check_out_date": booking.get("check_out_date"),
            }

        except requests.exceptions.Timeout:
            print("Hotel booking timeout")
            return {"success": False, "error": "La reserva tardó demasiado. Intenta de nuevo."}
        except Exception as e:
            print(f"Error booking hotel: {e}")
            return {"success": False, "error": "Error al reservar hotel. Intenta de nuevo."}

    # ===== HELPERS =====
    def get_accommodation_details(self, accommodation_id: str) -> Dict:
        """Get full details of a specific accommodation"""
        url = f"{self.base_url}/accommodations/{accommodation_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return {"success": False, "error": "No se encontro el hotel"}
            return {"success": True, "data": response.json().get("data", {})}
        except Exception as e:
            print(f"Error fetching accommodation details: {e}")
            return {"success": False, "error": str(e)}

    def get_booking(self, booking_id: str) -> Dict:
        """Retrieve booking details by ID"""
        url = f"{self.base_url}/bookings/{booking_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return {"success": False, "error": "No se encontro la reserva"}
            return {"success": True, "data": response.json().get("data", {})}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_fallback_hotels(self, location: str) -> List[Dict]:
        """Fallback simulated hotels if API fails"""
        city_name = location.title()
        return [
            {
                "offerId": f"sim_rate_{city_name}_001",
                "search_result_id": None,
                "accommodation_id": f"sim_acc_{city_name}_001",
                "name": f"Ritz-Carlton {city_name}",
                "rating": "5",
                "address": {"cityName": city_name, "countryCode": "MX"},
                "price": {"total": "450.00", "currency": "USD"},
                "amenities": ["WiFi", "Pool", "Spa"],
                "photos": [],
                "provider": "SIMULATED"
            }
        ]

    def format_for_whatsapp(self, hotels: List[Dict]) -> str:
        """Format hotel results for WhatsApp"""
        if not hotels:
            return "No encontre hoteles disponibles."

        msg = "*Hoteles disponibles:*\n\n"
        for i, hotel in enumerate(hotels[:5], 1):
            name = hotel.get("name", "Hotel")
            rating = hotel.get("rating", "")
            stars = "⭐" * int(float(rating)) if rating and rating != "0" else ""
            price = hotel.get("price", {})
            total = price.get("total", "?")
            currency = price.get("currency", "USD")
            amenities = hotel.get("amenities", [])
            amenities_str = ", ".join(amenities[:3]) if amenities else ""

            msg += f"*{i}.* {name} {stars}\n"
            msg += f"   💰 ${total} {currency}\n"
            if amenities_str:
                msg += f"   🏷️ {amenities_str}\n"
            msg += "\n"

        msg += "Envia el *numero* del hotel para ver habitaciones."
        return msg

    def format_rooms_for_whatsapp(self, rooms_data: Dict) -> str:
        """Format room/rate options for WhatsApp"""
        if not rooms_data.get("success"):
            return f"❌ {rooms_data.get('error', 'Error al obtener habitaciones')}"

        rooms = rooms_data.get("rooms", [])
        if not rooms:
            return "No hay habitaciones disponibles."

        board_names = {
            "room_only": "Solo habitacion",
            "breakfast": "Con desayuno",
            "half_board": "Media pension",
            "full_board": "Pension completa",
            "all_inclusive": "Todo incluido",
        }

        msg = "*Habitaciones disponibles:*\n\n"
        for i, room in enumerate(rooms[:5], 1):
            name = room.get("room_name", "Habitacion")
            total = room.get("total_amount", "?")
            currency = room.get("total_currency", "USD")
            board = board_names.get(room.get("board_type", ""), room.get("board_type", ""))

            msg += f"*{i}.* {name}\n"
            msg += f"   💰 ${total} {currency}\n"
            if board:
                msg += f"   🍽️ {board}\n"
            msg += "\n"

        msg += "Envia el *numero* para reservar."
        return msg
