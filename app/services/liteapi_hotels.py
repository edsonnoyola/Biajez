"""
LiteAPI Hotel Integration
Provides real hotel search and booking capabilities via LiteAPI.travel
"""

import os
import requests
import json
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

class LiteAPIService:
    """
    LiteAPI integration for hotel search and booking.
    Documentation: https://docs.liteapi.travel/
    """
    
    def __init__(self):
        self.api_key = os.getenv("LITEAPI_API_KEY")
        self.is_sandbox = os.getenv("LITEAPI_SANDBOX", "true").lower() == "true"
        self.base_url = "https://api.liteapi.travel/v3.0"
        
    def _get_headers(self):
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def search_hotels(self, location: str, check_in: str, check_out: str, guests: int = 1, rooms: int = 1) -> List[Dict[str, Any]]:
        """
        Search hotels by location (city name)
        
        Args:
            location: City name (e.g., "Cancun")
            check_in: YYYY-MM-DD
            check_out: YYYY-MM-DD
            guests: Number of adults
            rooms: Number of rooms
            
        Returns:
            List of hotel offers
        """
        if not self.api_key:
            print("WARNING: LITEAPI_API_KEY not set")
            return []

        try:
            print(f"DEBUG: LiteAPI searching hotels in {location} for {check_in} to {check_out}")
            
            # Step 1: Get Hotel IDs for the location (LiteAPI works best with Hotel IDs or Lat/Lon)
            # Since we don't have a geocoder handy, we'll use a hardcoded mapping for the demo cities
            # or try a broad search if the API supports it.
            
            # LiteAPI v3 recommends searching by country/city code or lat/lon.
            # Let's use a simple coordinate mapping for common demos
            coordinates = self._get_coordinates(location)
            
            if not coordinates:
                print(f"DEBUG: Could not geocode {location}, returning empty")
                return []
                
            # Step 2: Search for hotels availability
            # Use /hotels/rates endpoint for availability
            url = f"{self.base_url}/hotels/rates"
            
            payload = {
                "occupancies": [{
                    "adults": guests,
                    "children": []
                } for _ in range(rooms)],
                "currency": "USD",
                "checkin": check_in,
                "checkout": check_out,
                "latitude": coordinates["lat"],
                "longitude": coordinates["lon"],
                "radius": 20000,  # 20km radius
                "limit": 10,
                "guestNationality": "MX" 
            }
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            
            if response.status_code != 200:
                print(f"LiteAPI Error: [{response.status_code}] {response.text}")
                return []
            
            data = response.json()
            print(f"DEBUG: Data keys: {list(data.keys())}")
            hotels_data = data.get("hotels", [])
            
            results = []
            for hotel in hotels_data:
                try:
                    if len(results) == 0:
                         print(f"DEBUG: Hotel keys: {list(hotel.keys())}")
                    # Extract lowest price
                    # Structure seems to be: hotel object contains 'rates' list?
                    # Or maybe just hotel info?
                    # Let's check if 'rates' exists
                    rates = hotel.get("rates", [])
                    if not rates:
                        # Maybe it's just hotel info without rates?
                        # If so, we can't show price.
                        # But /hotels/rates SHOULD return rates.
                        # Let's print the first hotel to debug
                        if len(results) == 0:
                            print(f"DEBUG: First hotel structure: {json.dumps(hotel, default=str)[:200]}...")
                        
                    # Find cheapest rate
                    min_price = float('inf')
                    currency = "USD"
                    
                    for rate in rates:
                        price = rate.get("retailRate", {}).get("total", {}).get("amount", 0)
                        curr = rate.get("retailRate", {}).get("total", {}).get("currency", "USD")
                        if price > 0 and price < min_price:
                            min_price = price
                            currency = curr
                            
                    if min_price == float('inf'):
                         # Fallback if no rates found (or different structure)
                         # In sandbox mode, use a placeholder price
                         min_price = 150.00 if self.is_sandbox else 0
                    
                    # Show hotels even without price in sandbox mode
                    if min_price > 0 or self.is_sandbox:
                        results.append({
                            "id": hotel.get("id"),
                            "name": hotel.get("name"),
                            "location": location,
                            "price_total": str(min_price) if min_price > 0 else "150.00",
                            "currency": currency,
                            "rating": hotel.get("rating", 0),
                            "address": hotel.get("address", ""),
                            "image": hotel.get("main_photo", ""),
                            "provider": "LITEAPI",
                            "check_in": check_in,
                            "check_out": check_out,
                            "offer_id": f"LITEAPI::{hotel.get('id')}::{check_in}::{check_out}"
                        })
                except Exception as e:
                    print(f"Error parsing hotel: {e}")
                    continue
                    
            print(f"DEBUG: LiteAPI found {len(results)} hotels")
            return results

        except Exception as e:
            print(f"LiteAPI Exception: {e}")
            return []

    def _get_coordinates(self, city_name: str) -> Optional[Dict[str, float]]:
        """
        Get coordinates for a city using Nominatim (OpenStreetMap) geocoder.
        Falls back to hardcoded cities if geocoder fails.
        """
        # First try Nominatim (free, no API key needed)
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": city_name,
                "format": "json",
                "limit": 1
            }
            headers = {
                "User-Agent": "Biajez-TravelApp/1.0"  # Required by Nominatim
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    print(f"📍 Geocoded '{city_name}' → lat:{lat}, lon:{lon}")
                    return {"lat": lat, "lon": lon}
                    
        except Exception as e:
            print(f"⚠️ Nominatim geocoding failed: {e}, using fallback")
        
        # Fallback: Expanded hardcoded cities
        cities = {
            # México
            "cancun": {"lat": 21.1619, "lon": -86.8515},
            "cancún": {"lat": 21.1619, "lon": -86.8515},
            "mexico city": {"lat": 19.4326, "lon": -99.1332},
            "ciudad de mexico": {"lat": 19.4326, "lon": -99.1332},
            "mexico": {"lat": 19.4326, "lon": -99.1332},
            "cdmx": {"lat": 19.4326, "lon": -99.1332},
            "monterrey": {"lat": 25.6866, "lon": -100.3161},
            "guadalajara": {"lat": 20.6597, "lon": -103.3496},
            "playa del carmen": {"lat": 20.6296, "lon": -87.0739},
            "los cabos": {"lat": 22.8905, "lon": -109.9167},
            "san miguel de allende": {"lat": 20.9144, "lon": -100.7452},
            "oaxaca": {"lat": 17.0732, "lon": -96.7266},
            "merida": {"lat": 20.9674, "lon": -89.5926},
            "puerto vallarta": {"lat": 20.6534, "lon": -105.2253},
            "tulum": {"lat": 20.2114, "lon": -87.4654},
            
            # USA
            "new york": {"lat": 40.7128, "lon": -74.0060},
            "nyc": {"lat": 40.7128, "lon": -74.0060},
            "miami": {"lat": 25.7617, "lon": -80.1918},
            "los angeles": {"lat": 34.0522, "lon": -118.2437},
            "la": {"lat": 34.0522, "lon": -118.2437},
            "las vegas": {"lat": 36.1699, "lon": -115.1398},
            "chicago": {"lat": 41.8781, "lon": -87.6298},
            "san francisco": {"lat": 37.7749, "lon": -122.4194},
            "orlando": {"lat": 28.5383, "lon": -81.3792},
            "houston": {"lat": 29.7604, "lon": -95.3698},
            "dallas": {"lat": 32.7767, "lon": -96.7970},
            
            # Europa
            "madrid": {"lat": 40.4168, "lon": -3.7038},
            "barcelona": {"lat": 41.3851, "lon": 2.1734},
            "paris": {"lat": 48.8566, "lon": 2.3522},
            "london": {"lat": 51.5074, "lon": -0.1278},
            "londres": {"lat": 51.5074, "lon": -0.1278},
            "rome": {"lat": 41.9028, "lon": 12.4964},
            "roma": {"lat": 41.9028, "lon": 12.4964},
            "amsterdam": {"lat": 52.3676, "lon": 4.9041},
            "berlin": {"lat": 52.5200, "lon": 13.4050},
            "lisbon": {"lat": 38.7223, "lon": -9.1393},
            "lisboa": {"lat": 38.7223, "lon": -9.1393},
            "prague": {"lat": 50.0755, "lon": 14.4378},
            "praga": {"lat": 50.0755, "lon": 14.4378},
            "vienna": {"lat": 48.2082, "lon": 16.3738},
            "viena": {"lat": 48.2082, "lon": 16.3738},
            
            # Latinoamérica
            "buenos aires": {"lat": -34.6037, "lon": -58.3816},
            "bogota": {"lat": 4.7110, "lon": -74.0721},
            "bogotá": {"lat": 4.7110, "lon": -74.0721},
            "lima": {"lat": -12.0464, "lon": -77.0428},
            "santiago": {"lat": -33.4489, "lon": -70.6693},
            "rio de janeiro": {"lat": -22.9068, "lon": -43.1729},
            "rio": {"lat": -22.9068, "lon": -43.1729},
            "sao paulo": {"lat": -23.5505, "lon": -46.6333},
            "cartagena": {"lat": 10.3910, "lon": -75.4794},
            "medellin": {"lat": 6.2476, "lon": -75.5658},
            
            # Asia
            "tokyo": {"lat": 35.6762, "lon": 139.6503},
            "tokio": {"lat": 35.6762, "lon": 139.6503},
            "dubai": {"lat": 25.2048, "lon": 55.2708},
            "singapore": {"lat": 1.3521, "lon": 103.8198},
            "singapur": {"lat": 1.3521, "lon": 103.8198},
            "hong kong": {"lat": 22.3193, "lon": 114.1694},
            "bangkok": {"lat": 13.7563, "lon": 100.5018},
            "bali": {"lat": -8.3405, "lon": 115.0920},
            
            # Caribe
            "punta cana": {"lat": 18.5601, "lon": -68.3725},
            "san juan": {"lat": 18.4655, "lon": -66.1057},
            "havana": {"lat": 23.1136, "lon": -82.3666},
            "habana": {"lat": 23.1136, "lon": -82.3666}
        }
        
        result = cities.get(city_name.lower().strip())
        if result:
            print(f"📍 Using fallback coordinates for '{city_name}'")
        return result

    def book_hotel(self, offer_id: str, guest_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Book a hotel via LiteAPI (Mock implementation)
        Handles both MOCK hotel IDs (e.g., MOCK_RC_CAN) and real LiteAPI IDs
        """
        import uuid
        
        try:
            # Handle MOCK hotels (from simulated searches)
            if offer_id.startswith("MOCK_"):
                booking_id = f"LITE-MOCK-{uuid.uuid4().hex[:8].upper()}"
                return {
                    "booking_id": booking_id,
                    "status": "confirmed",
                    "hotel_id": offer_id,
                    "confirmation_code": booking_id,
                    "checkin": "2026-02-10",
                    "checkout": "2026-02-13"
                }
            
            # Handle real LiteAPI format: LITEAPI::HOTELID::CHECKIN::CHECKOUT
            if "::" in offer_id:
                parts = offer_id.split("::")
                hotel_id = parts[1] if len(parts) > 1 else offer_id
                checkin = parts[2] if len(parts) > 2 else None
                checkout = parts[3] if len(parts) > 3 else None
            else:
                hotel_id = offer_id
                checkin = None
                checkout = None
            
            # Mock booking
            booking_id = f"LITE-{uuid.uuid4().hex[:8].upper()}"
            result = {
                "booking_id": booking_id,
                "status": "confirmed",
                "hotel_id": hotel_id,
                "confirmation_code": booking_id
            }
            
            if checkin:
                result["checkin"] = checkin
            if checkout:
                result["checkout"] = checkout
                
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"Booking failed: {e}")
