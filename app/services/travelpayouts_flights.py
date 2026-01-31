"""
Travelpayouts Flight Search Integration
Provides affiliate flight search via Kiwi.com, Aviasales, and other partners
"""

import os
import requests
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.models.models import AntigravityFlight, FlightSegment


class TravelpayoutsFlightEngine:
    """
    Travelpayouts API integration for flight search.
    NOTE: This is an AFFILIATE model - returns booking links, not direct bookings.
    """
    
    def __init__(self):
        self.token = os.getenv("TRAVELPAYOUTS_TOKEN")
        self.marker = os.getenv("TRAVELPAYOUTS_MARKER", "antigravity")
        self.base_url = "https://api.travelpayouts.com/aviasales/v3"
        
    def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
        return_date: Optional[str] = None,
        cabin: str = "Y",
        adults: int = 1
    ) -> List[AntigravityFlight]:
        """
        Search flights via Travelpayouts (Aviasales API)
        
        Args:
            origin: IATA code (e.g., "MEX")
            destination: IATA code (e.g., "CUN")
            date: Departure date (YYYY-MM-DD)
            return_date: Optional return date
            cabin: Cabin class (Y=economy, C=business)
            adults: Number of passengers
            
        Returns:
            List of AntigravityFlight objects with affiliate booking links
        """
        
        if not self.token:
            print("WARNING: TRAVELPAYOUTS_TOKEN not set. Skipping Travelpayouts search.")
            return []
            
        try:
            # Use Aviasales search API
            url = f"{self.base_url}/prices_for_dates"
            
            params = {
                "origin": origin,
                "destination": destination,
                "departure_at": date,
                "currency": "USD",
                "token": self.token,
                "sorting": "price",  # Cheapest first
                "limit": 30
            }
            
            if return_date:
                params["return_at"] = return_date
                
            print(f"DEBUG: Travelpayouts searching {origin}->{destination} on {date}")
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"Travelpayouts Error: [{response.status_code}] {response.text}")
                return []
                
            data = response.json()
            
            if not data.get("success"):
                print(f"Travelpayouts API returned success=false")
                return []
                
            flights = []
            offers = data.get("data", [])
            
            print(f"DEBUG: Travelpayouts found {len(offers)} offers")
            
            for offer in offers[:10]:  # Limit to top 10
                try:
                    # Parse departure/arrival times
                    depart_time = datetime.fromisoformat(offer.get("departure_at", "").replace("Z", "+00:00"))
                    return_time = datetime.fromisoformat(offer.get("return_at", "").replace("Z", "+00:00")) if offer.get("return_at") else None
                    
                    # Build segments from route info
                    segments = []
                    
                    # Outbound segment
                    segments.append(FlightSegment(
                        carrier_code=offer.get("airline", "XX"),
                        flight_number=offer.get("flight_number", "0"),
                        departure_iata=origin,
                        arrival_iata=destination,
                        departure_time=depart_time,
                        arrival_time=return_time or depart_time,  # Placeholder
                        duration=f"{offer.get('duration', 0)}m"
                    ))
                    
                    # Generate affiliate booking link
                    # Format: TRAVELPAYOUTS::link_url
                    booking_link = offer.get("link")
                    if not booking_link:
                        # Fallback: construct Kiwi.com search link
                        booking_link = f"https://www.kiwi.com/deep?affilid={self.marker}&from={origin}&to={destination}&departure={date}"
                        if return_date:
                            booking_link += f"&return={return_date}"
                    
                    offer_id = f"TRAVELPAYOUTS::{booking_link}"
                    
                    flight = AntigravityFlight(
                        offer_id=offer_id,
                        provider="TRAVELPAYOUTS",
                        price=Decimal(str(offer.get("price", 0))),
                        currency="USD",
                        segments=segments,
                        duration_total=f"{offer.get('duration', 0)}m",
                        cabin_class=cabin,
                        refundable=False,
                        # Add metadata for affiliate link
                        metadata={
                            "booking_type": "affiliate",
                            "booking_link": booking_link,
                            "partner": "Kiwi.com"
                        }
                    )
                    
                    flights.append(flight)
                    
                except Exception as e:
                    print(f"DEBUG: Error parsing Travelpayouts offer: {e}")
                    continue
                    
            print(f"DEBUG: Returning {len(flights)} Travelpayouts flights")
            return flights
            
        except requests.Timeout:
            print("Travelpayouts Error: Request timeout")
            return []
        except Exception as e:
            print(f"Travelpayouts Error: {e}")
            return []
            
    def get_booking_link(self, offer_id: str) -> str:
        """
        Extract booking link from offer_id
        
        Args:
            offer_id: Format "TRAVELPAYOUTS::https://..."
            
        Returns:
            Full booking URL
        """
        if offer_id.startswith("TRAVELPAYOUTS::"):
            return offer_id.replace("TRAVELPAYOUTS::", "")
        return offer_id
