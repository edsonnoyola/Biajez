import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

class BatchSearchService:
    """
    Service for Duffel Batch Offer Requests
    Enables progressive loading of flight search results
    """
    
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
    
    def create_batch_search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        cabin_class: str = "economy",
        passengers: int = 1,
        supplier_timeout: int = 10000  # 10 seconds
    ) -> Dict:
        """
        Create a batch offer request
        
        Args:
            origin: Origin airport code (e.g., "MEX")
            destination: Destination airport code (e.g., "CUN")
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Optional return date for round trip
            cabin_class: Cabin class (economy, business, first)
            passengers: Number of passengers
            supplier_timeout: Timeout in milliseconds (2000-60000)
            
        Returns:
            dict: {
                "batch_id": "orq_xxx",
                "total_batches": 2,
                "remaining_batches": 2,
                "created_at": "2024-01-01T00:00:00Z"
            }
        """
        url = f"{self.base_url}/air/batch_offer_requests?supplier_timeout={supplier_timeout}"
        
        # Build slices
        slices = [{
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date
        }]
        
        # Add return slice if round trip
        if return_date:
            slices.append({
                "origin": destination,
                "destination": origin,
                "departure_date": return_date
            })
        
        # Build passengers list
        passengers_list = [{"type": "adult"} for _ in range(passengers)]
        
        payload = {
            "data": {
                "slices": slices,
                "passengers": passengers_list,
                "cabin_class": cabin_class
            }
        }
        
        try:
            print(f"🔍 Creating batch search: {origin} → {destination} on {departure_date}")
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()["data"]

            result = {
                "batch_id": data["id"],
                "total_batches": data["total_batches"],
                "remaining_batches": data["remaining_batches"],
                "created_at": data["created_at"]
            }
            
            print(f"✅ Batch created: {result['batch_id']} ({result['total_batches']} batches expected)")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating batch search: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def get_batch_results(self, batch_id: str) -> Dict:
        """
        Get results from a batch offer request (long-polling)
        
        Args:
            batch_id: Batch offer request ID
            
        Returns:
            dict: {
                "offers": [...],
                "total_batches": 2,
                "remaining_batches": 1,
                "is_complete": False
            }
        """
        url = f"{self.base_url}/air/batch_offer_requests/{batch_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            data = response.json()["data"]

            offers = data.get("offers", [])
            total_batches = data["total_batches"]
            remaining_batches = data["remaining_batches"]
            is_complete = remaining_batches == 0
            
            print(f"📦 Batch {batch_id}: {len(offers)} offers, {remaining_batches}/{total_batches} batches remaining")
            
            # Format offers for frontend
            formatted_offers = self.format_batch_offers(offers)
            
            return {
                "offers": formatted_offers,
                "total_batches": total_batches,
                "remaining_batches": remaining_batches,
                "is_complete": is_complete
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting batch results: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def format_batch_offers(self, offers: List[Dict]) -> List[Dict]:
        """
        Format Duffel offers for frontend consumption
        
        Args:
            offers: Raw Duffel offers
            
        Returns:
            List of formatted offers compatible with existing frontend
        """
        formatted = []
        
        for offer in offers:
            try:
                # Extract basic info
                offer_id = offer.get("id")
                total_amount = offer.get("total_amount")
                total_currency = offer.get("total_currency")
                
                # Extract slices
                slices = offer.get("slices", [])
                if not slices:
                    continue
                
                # Get first slice for basic info
                first_slice = slices[0]
                segments = first_slice.get("segments", [])
                
                if not segments:
                    continue
                
                # Calculate total duration
                duration = first_slice.get("duration", "PT0H0M")
                
                # Format segments
                formatted_segments = []
                for seg in segments:
                    formatted_segments.append({
                        "carrier_code": seg.get("operating_carrier", {}).get("iata_code", "XX"),
                        "flight_number": seg.get("operating_carrier_flight_number", "0000"),
                        "departure_iata": seg.get("origin", {}).get("iata_code", ""),
                        "arrival_iata": seg.get("destination", {}).get("iata_code", ""),
                        "departure_time": seg.get("departing_at", ""),
                        "arrival_time": seg.get("arriving_at", ""),
                        "duration": seg.get("duration", "PT0H0M")
                    })
                
                # Determine cabin class
                cabin_class = "economy"
                if segments:
                    passengers = segments[0].get("passengers", [])
                    if passengers:
                        cabin_class = passengers[0].get("cabin_class", "economy")
                
                formatted_offer = {
                    "offer_id": f"DUFFEL::{offer_id}",
                    "provider": "DUFFEL",
                    "price": total_amount,
                    "currency": total_currency,
                    "segments": formatted_segments,
                    "duration_total": duration,
                    "cabin_class": cabin_class,
                    "refundable": False,  # Would need to check conditions
                    "metadata": {
                        "owner": offer.get("owner", {}).get("name", ""),
                        "expires_at": offer.get("expires_at", "")
                    }
                }
                
                formatted.append(formatted_offer)
                
            except Exception as e:
                print(f"⚠️  Error formatting offer {offer.get('id')}: {e}")
                continue
        
        return formatted
