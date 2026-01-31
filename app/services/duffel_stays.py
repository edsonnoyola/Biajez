import os
import requests
from fastapi import HTTPException
from typing import List, Dict, Optional

class DuffelStaysEngine:
    """
    Duffel Stays API integration for hotel search and booking
    Uses same DUFFEL_ACCESS_TOKEN as flights
    """
    
    def __init__(self):
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com/stays"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Duffel-Version": "v2"
        }
    
    def search_hotels(
        self, 
        location: str, 
        check_in: str, 
        check_out: str,
        guests: int = 1,
        rooms: int = 1,
        radius: int = 5000,  # meters
        preferred_chains: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for hotels using Duffel Stays
        
        Args:
            location: City name or coordinates
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            guests: Number of guests (default 1)
            rooms: Number of rooms (default 1)
            radius: Search radius in meters
            preferred_chains: Comma-separated hotel chains for prioritization
            
        Returns:
            List of hotel accommodations with pricing
        """
        
        # City coordinates mapping (major cities)
        city_coords = {
            "cancun": {"lat": 21.1619, "lng": -86.8515},
            "cdmx": {"lat": 19.4326, "lng": -99.1332},
            "guadalajara": {"lat": 20.6597, "lng": -103.3496},
            "monterrey": {"lat": 25.6866, "lng": -100.3161},
            "playa del carmen": {"lat": 20.6296, "lng": -87.0739},
            "tulum": {"lat": 20.2114, "lng": -87.4654},
            "puerto vallarta": {"lat": 20.6534, "lng": -105.2253},
            "los cabos": {"lat": 22.8905, "lng": -109.9167},
            "oaxaca": {"lat": 17.0732, "lng": -96.7266},
            "merida": {"lat": 20.9674, "lng": -89.5926}
        }
        
        # Get coordinates for location
        location_lower = location.lower().strip()
        coords = city_coords.get(location_lower, city_coords["cancun"])  # Default to Cancun
        
        # Proper Duffel Stays API format
        search_url = f"{self.base_url}/search"
        
        payload = {
            "data": {
                "location": {
                    "geographic_coordinates": {
                        "latitude": coords["lat"],
                        "longitude": coords["lng"]
                    },
                    "radius": {
                        "value": radius / 1000,  # Convert to km
                        "unit": "km"
                    }
                },
                "check_in_date": check_in,
                "check_out_date": check_out,
                "guests": [
                    {
                        "type": "adult",
                        "age": None
                    }
                ] * guests,
                "rooms": rooms
            }
        }
        
        try:
            print(f"DEBUG: Searching Duffel Stays for {location} at {coords}")
            response = requests.post(search_url, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                print(f"Duffel Stays Error: {response.status_code} - {response.text}")
                return self._get_fallback_hotels(location)
            
            data = response.json()
            accommodations = data.get("data", {}).get("accommodations", [])
            
            if not accommodations:
                print("No accommodations found, using fallback")
                return self._get_fallback_hotels(location)
            
            print(f"DEBUG: Found {len(accommodations)} hotels from Duffel")
            
            # Format results
            hotels = []
            for acc in accommodations[:10]:
                rates = acc.get("rates", [])
                if not rates:
                    continue
                
                cheapest = min(rates, key=lambda r: float(r.get("total_amount", 999999)))
                
                hotel = {
                    "offerId": cheapest.get("id"),
                    "accommodation_id": acc.get("id"),
                    "name": acc.get("name", "Hotel"),
                    "rating": str(acc.get("rating", {}).get("value", "4")),
                    "address": {
                        "cityName": location.title(),
                        "countryCode": "MX"
                    },
                    "price": {
                        "total": cheapest.get("total_amount"),
                        "currency": cheapest.get("total_currency", "USD")
                    },
                    "amenities": [a.get("name", a) if isinstance(a, dict) else a for a in acc.get("amenities", [])[:5]],
                    "location_description": "City Center",
                    "photos": [],
                    "provider": "DUFFEL_STAYS"
                }
                hotels.append(hotel)
            
            return hotels if hotels else self._get_fallback_hotels(location)
            
        except Exception as e:
            print(f"Duffel Stays Search Error: {e}")
            return self._get_fallback_hotels(location)
    
    def _get_fallback_hotels(self, location: str) -> List[Dict]:
        """Fallback simulated hotels if API fails"""
        city_name = location.title()
        return [
            {
                "offerId": f"sim_rate_{city_name}_001",
                "accommodation_id": f"sim_acc_{city_name}_001",
                "name": f"Ritz-Carlton {city_name}",
                "rating": "5",
                "address": {"cityName": city_name, "countryCode": "MX"},
                "price": {"total": "450.00", "currency": "USD"},
                "amenities": ["WiFi", "Pool", "Spa"],
                "location_description": "City Center",
                "photos": [],
                "provider": "SIMULATED"
            }
        ]
    
    def get_accommodation_details(self, accommodation_id: str) -> Dict:
        """Get full details of a specific accommodation"""
        url = f"{self.base_url}/accommodations/{accommodation_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()["data"]
        except Exception as e:
            print(f"Error fetching accommodation details: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def book_hotel(
        self, 
        rate_id: str, 
        guest_info: Dict
    ) -> Dict:
        """
        Book a hotel using Duffel Stays
        
        Args:
            rate_id: The rate ID from search results
            guest_info: Guest information (name, email, phone)
            
        Returns:
            Booking confirmation with reference number
        """
        url = f"{self.base_url}/bookings"
        
        payload = {
            "data": {
                "rate_id": rate_id,
                "guests": [{
                    "given_name": guest_info.get("given_name"),
                    "family_name": guest_info.get("family_name"),
                    "email": guest_info.get("email"),
                    "phone_number": guest_info.get("phone_number")
                }],
                "payment": {
                    "type": "balance"  # Using Duffel balance
                }
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            booking = response.json()["data"]
            
            return {
                "booking_id": booking.get("id"),
                "confirmation_number": booking.get("reference"),
                "status": booking.get("status"),
                "accommodation": booking.get("accommodation"),
                "total_amount": booking.get("total_amount"),
                "total_currency": booking.get("total_currency")
            }
            
        except Exception as e:
            print(f"Error booking hotel: {e}")
            raise HTTPException(status_code=500, detail=str(e))
