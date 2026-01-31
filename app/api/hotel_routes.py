"""
Hotel search endpoint - Basic implementation
Uses Amadeus hotel search API
"""

from fastapi import APIRouter, HTTPException
from amadeus import Client, ResponseError
import os
from typing import List, Dict, Any

router = APIRouter()

def get_amadeus_client():
    return Client(
        client_id=os.getenv("AMADEUS_CLIENT_ID"),
        client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
        hostname=os.getenv("AMADEUS_HOSTNAME", "test")
    )

@router.get("/v1/hotels")
async def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    rooms: int = 1
) -> List[Dict[str, Any]]:
    """
    Search hotels by location
    
    Args:
        location: City name or code (e.g., "Cancun" or "CUN")
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests
        rooms: Number of rooms
    """
    try:
        amadeus = get_amadeus_client()
        
        # Try to get city code if it's a name
        city_code = location.upper()[:3]  # Simple heuristic
        
        print(f"DEBUG: Searching hotels in {location} ({city_code})")
        print(f"DEBUG: Check-in: {check_in}, Check-out: {check_out}")
        
        # Search hotel offers by city
        response = amadeus.shopping.hotel_offers_search.get(
            cityCode=city_code,
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=guests,
            roomQuantity=rooms,
            radius=20,
            radiusUnit='KM'
        )
        
        hotels = []
        for hotel_offer in response.data[:10]:  # Limit to 10 results
            hotel = hotel_offer.get('hotel', {})
            offers = hotel_offer.get('offers', [])
            
            if offers:
                best_offer = offers[0]
                price = best_offer.get('price', {})
                
                hotels.append({
                    'hotel_id': hotel.get('hotelId'),
                    'name': hotel.get('name', 'Unknown Hotel'),
                    'price': float(price.get('total', 0)),
                    'currency': price.get('currency', 'USD'),
                    'offer_id': best_offer.get('id'),
                    'check_in': check_in,
                    'check_out': check_out,
                    'rating': hotel.get('rating', 'N/A'),
                    'provider': 'AMADEUS'
                })
        
        print(f"DEBUG: Found {len(hotels)} hotels")
        return hotels
        
    except ResponseError as error:
        print(f"Amadeus Hotel Error: {error}")
        print(f"Status: {error.response.status_code}")
        # Return empty list instead of error for better UX
        return []
    except Exception as e:
        print(f"Hotel Search Error: {e}")
        import traceback
        traceback.print_exc()
        return []
