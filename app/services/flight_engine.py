import asyncio
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from amadeus import Client, ResponseError
from duffel_api import Duffel
from app.services.travelpayouts_flights import TravelpayoutsFlightEngine
from app.models.models import AntigravityFlight, FlightSegment




# --- Service ---
# Simple persistent cache for offers (ID -> Full Object)
import json
CACHE_FILE = "offers_cache.json"

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except:
        pass

OFFER_CACHE = load_cache()

class FlightAggregator:
    def __init__(self):
        # Initialize Amadeus
        self.amadeus = Client(
            client_id=os.getenv("AMADEUS_CLIENT_ID"),
            client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
            hostname=os.getenv("AMADEUS_HOSTNAME", "test")
        )
        
        # Initialize Duffel (Test or Live)
        # Using v2 as confirmed by debug script
        self.duffel = Duffel(access_token=os.getenv("DUFFEL_ACCESS_TOKEN"), api_version="v2")

    async def search_hybrid_flights(
        self, 
        origin: str, 
        destination: str, 
        departure_date: str, 
        return_date: Optional[str] = None,
        cabin_class: str = "ECONOMY",
        airline: Optional[str] = None,
        time_of_day: str = "ANY",
        num_passengers: int = 1
    ) -> List[AntigravityFlight]:
        """
        Parallel execution of Amadeus and Duffel searches with intelligent scoring.
        """
        print(f"DEBUG: Searching flights - Origin: {origin}, Dest: {destination}, Date: {departure_date}, Cabin: {cabin_class}, Time: {time_of_day}")
        
        # Run all THREE sources in parallel
        amadeus_task = asyncio.create_task(self._search_amadeus(origin, destination, departure_date, cabin_class, airline, return_date))
        duffel_task = asyncio.create_task(self._search_duffel(
            origin=origin,
            dest=destination,
            date=departure_date,
            cabin=cabin_class,
            airline_filter=airline,
            return_date=return_date,
            num_passengers=num_passengers
        ))
        travelpayouts_task = asyncio.create_task(self._search_travelpayouts(origin, destination, departure_date, cabin_class, return_date))
        
        amadeus_results, duffel_results, travelpayouts_results = await asyncio.gather(
            amadeus_task, duffel_task, travelpayouts_task, return_exceptions=True
        )
        
        # Debug: Print what we got from each source
        print(f"DEBUG: Amadeus returned: {type(amadeus_results)} - {len(amadeus_results) if isinstance(amadeus_results, list) else 'ERROR'}")
        if isinstance(amadeus_results, Exception):
            print(f"DEBUG: Amadeus exception: {amadeus_results}")
        print(f"DEBUG: Duffel returned: {type(duffel_results)} - {len(duffel_results) if isinstance(duffel_results, list) else 'ERROR'}")
        print(f"DEBUG: Travelpayouts returned: {type(travelpayouts_results)} - {len(travelpayouts_results) if isinstance(travelpayouts_results, list) else 'ERROR'}")
        
        # Combine all results
        all_flights = []
        if isinstance(amadeus_results, list):
            all_flights.extend(amadeus_results)
        if isinstance(duffel_results, list):
            all_flights.extend(duffel_results)
        if isinstance(travelpayouts_results, list):
            all_flights.extend(travelpayouts_results)
        
        if not all_flights:
            print("DEBUG: No flights found from APIs. Returning empty list as per user request (NO SIMULATION).")
            return []
        
        # INTELLIGENT SCORING SYSTEM
        print(f"DEBUG: Scoring {len(all_flights)} flights with intelligent algorithm")
        
        for flight in all_flights:
            score = 100  # Base score
            
            # 1. DIRECT FLIGHTS GET MASSIVE BOOST (+50 points)
            num_segments = len(flight.segments)
            if num_segments == 1:
                score += 50  # Direct flight - HIGHEST PRIORITY
            elif num_segments == 2:
                score += 20  # One stop
            else:
                score -= (num_segments - 2) * 10  # Penalize multiple stops
            
            # 2. PREFERRED AIRLINE BOOST (+50 points) - VERY HIGH PRIORITY
            if airline:
                carrier = flight.segments[0].carrier_code if flight.segments else ""
                if carrier and airline.upper() in carrier.upper():
                    score += 50  # Increased from 30 to ensure preferred airline is prioritized
                    print(f"DEBUG: Preferred airline {airline} matched for {carrier} - Boost: +50")
            
            # 3. PRICE SCORING (cheaper = better)
            price = float(flight.price) if flight.price else 999
            if price < 200:
                score += 20  # Very cheap
            elif price < 350:
                score += 10  # Reasonable
            elif price > 600:
                score -= 15  # Expensive
            
            # 4. DURATION SCORING (shorter = better)
            duration_str = flight.duration_total or "99h"
            try:
                if "h" in duration_str:
                    hours = int(duration_str.split("h")[0].strip())
                    if hours < 5:
                        score += 15  # Short flight
                    elif hours < 10:
                        score += 5   # Medium flight
                    elif hours > 15:
                        score -= 10  # Very long flight
            except:
                pass
            
            # 5. TIME OF DAY PREFERENCE
            if time_of_day != "ANY":
                dep_hour = flight.segments[0].departure_time.hour
                matches_time = False
                if time_of_day == "EARLY_MORNING" and 0 <= dep_hour < 6: matches_time = True
                elif time_of_day == "MORNING" and 6 <= dep_hour < 12: matches_time = True
                elif time_of_day == "AFTERNOON" and 12 <= dep_hour < 18: matches_time = True
                elif time_of_day == "EVENING" and 18 <= dep_hour < 22: matches_time = True
                elif time_of_day == "NIGHT" and 22 <= dep_hour <= 23: matches_time = True
                
                if matches_time:
                    score += 25
            
            # 6. PROVIDER PREFERENCE (Duffel more reliable)
            if flight.provider == "DUFFEL":
                score += 5
            
            flight.score = score

        # Sort by score (highest first)
        all_flights.sort(key=lambda f: f.score, reverse=True)
        
        # Log top 3 scores
        for i, flight in enumerate(all_flights[:3]):
            segments = len(flight.segments)
            carrier = flight.segments[0].carrier_code if flight.segments else "?"
            print(f"DEBUG: Rank {i+1}: {carrier} - Score={flight.score}, Segments={segments}, Price=${flight.price}")
        
        return all_flights[:30]  # Return top 30 (was 15)


    async def search_multicity(self, segments: List[Dict[str, str]], cabin_class="ECONOMY") -> List[AntigravityFlight]:
        """
        Search for multi-city flights using Duffel.
        segments: [{"origin": "MEX", "destination": "MAD", "date": "2025-12-15"}, ...]
        """
        print(f"DEBUG: Searching Multi-City: {segments}")
        
        # Map to Duffel slices
        duffel_slices = [{
            "origin": s["origin"], 
            "destination": s["destination"], 
            "departure_date": s["date"]
        } for s in segments]
        
        # Call Duffel with custom slices
        # We pass None for standard args as they are ignored when custom_slices is present
        return await self._search_duffel(None, None, None, cabin_class, custom_slices=duffel_slices)

    async def _search_amadeus(self, origin, dest, date, cabin, airline_filter=None, return_date=None):
        try:
            # Amadeus Search
            # Note: Amadeus SDK is synchronous, so this will block the event loop.
            # For production, consider running in a thread pool or using an async Amadeus client if available.
            if not return_date:
                response = self.amadeus.shopping.flight_offers_search.get(
                    originLocationCode=origin,
                    destinationLocationCode=dest,
                    departureDate=date,
                    adults=1,
                    travelClass=cabin,
                    max=10
                )
            else:
                response = self.amadeus.shopping.flight_offers_search.get(
                    originLocationCode=origin,
                    destinationLocationCode=dest,
                    departureDate=date,
                    returnDate=return_date,
                    adults=1,
                    travelClass=cabin,
                    max=10
                )
            
            if not response.data:
                return []
                
            flights = []
            for offer in response.data:
                # Basic mapping
                segments = []
                for itin in offer['itineraries']:
                    for seg in itin['segments']:
                        segments.append(FlightSegment(
                            carrier_code=seg['carrierCode'],
                            flight_number=seg['number'],
                            departure_iata=seg['departure']['iataCode'],
                            arrival_iata=seg['arrival']['iataCode'],
                            departure_time=datetime.fromisoformat(seg['departure']['at']),
                            arrival_time=datetime.fromisoformat(seg['arrival']['at']),
                            duration=seg['duration']
                        ))
                
                flights.append(AntigravityFlight(
                    offer_id=f"AMADEUS::{offer['id']}",
                    provider="AMADEUS",
                    price=Decimal(offer['price']['total']),
                    currency=offer['price']['currency'],
                    segments=segments,
                    duration_total=offer['itineraries'][0]['duration'],
                    cabin_class=cabin,
                    refundable=False 
                ))
            return flights
        except ResponseError as error:
            print(f"Amadeus Error: {error}")
            return []
        except Exception as e:
            print(f"Amadeus Unexpected Error: {e}")
            return []

    async def _search_duffel(self, origin, dest, date, cabin, airline_filter=None, return_date=None, custom_slices=None, num_passengers=1):
        try:
            import requests
            token = os.getenv("DUFFEL_ACCESS_TOKEN")
            url = "https://api.duffel.com/air/offer_requests"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Duffel-Version": "v2"
            }
            
            if custom_slices:
                slices = custom_slices
            else:
                slices = [{"origin": origin, "destination": dest, "departure_date": date}]
                if return_date:
                    slices.append({"origin": dest, "destination": origin, "departure_date": return_date})

            # Generate passengers list dynamically based on num_passengers
            passengers_list = [{"type": "adult"} for _ in range(num_passengers)]
            
            payload = {
                "data": {
                    "slices": slices,
                    "passengers": passengers_list,  # Now dynamic
                    "cabin_class": (cabin or "economy").lower()
                }
            }
            
            print(f"DEBUG: Duffel request payload: {json.dumps(payload, indent=2)}")
            
            response = await asyncio.to_thread(requests.post, url, json=payload, headers=headers)
            
            if response.status_code != 201:
                print(f"Duffel Search Error: {response.text}")
                return []
                
            response_data = response.json()["data"]
            print(f"DEBUG: Duffel Raw Search Found {len(response_data['offers'])} offers")
            flights = []
            
            for offer in response_data['offers']:
                # NOTE: Don't filter by airline here - we'll boost preferred airline in scoring
                # This ensures we always return results even if preferred airline isn't available
                    
                segments = []
                for slice in offer['slices']:
                    for seg in slice['segments']:
                        segments.append(FlightSegment(
                            carrier_code=seg['operating_carrier']['iata_code'],
                            flight_number=seg.get('operating_carrier_flight_number') or "UNKNOWN",
                            departure_iata=seg['origin']['iata_code'],
                            arrival_iata=seg['destination']['iata_code'],
                            departure_time=datetime.fromisoformat(seg['departing_at']),
                            arrival_time=datetime.fromisoformat(seg['arriving_at']),
                            duration=seg['duration'] or "00:00"
                        ))
                
                # Store passenger ID in offer_id for booking retrieval if needed
                # Format: DUFFEL::offer_id::passenger_id
                passenger_id = offer['passengers'][0]['id']
                
                flights.append(AntigravityFlight(
                    offer_id=f"DUFFEL::{offer['id']}::{passenger_id}",
                    provider="DUFFEL",
                    price=Decimal(offer['total_amount']),
                    currency=offer['total_currency'],
                    segments=segments,
                    duration_total=offer['slices'][0]['duration'] or "00:00",
                    cabin_class=cabin,
                    refundable=False
                ))
            
            print(f"DEBUG: Returning {len(flights)} flights from Duffel")
            return flights
        except Exception as e:
            print(f"Duffel Error: {e}")
            return []

    async def _search_travelpayouts(self, origin, dest, date, cabin, return_date=None):
        """
        Search flights via Travelpayouts (affiliate)
        Returns flights with external booking links
        """
        try:
            engine = TravelpayoutsFlightEngine()
            results = engine.search_flights(
                origin=origin,
                destination=dest,
                date=date,
                return_date=return_date,
                cabin=cabin
            )
            return results
        except Exception as e:
            print(f"Travelpayouts Error: {e}")
            return []


    def _get_mock_flights(self, origin, dest, date, cabin, airline_filter=None, time_of_day="ANY") -> List[AntigravityFlight]:
        """Generate mock flights for testing when APIs fail."""
        import random
        from datetime import datetime, timedelta
        
        mock_airlines = [
            {"code": "BA", "name": "British Airways"},
            {"code": "IB", "name": "Iberia"},
            {"code": "AM", "name": "Aeromexico"},
            {"code": "LH", "name": "Lufthansa"},
            {"code": "AF", "name": "Air France"}
        ]
        
        flights = []
        base_price = 800 if cabin == "ECONOMY" else 2500
        
        # Determine start hour based on time_of_day
        start_hour = 10
        if time_of_day == "EARLY_MORNING": start_hour = 4
        elif time_of_day == "MORNING": start_hour = 8
        elif time_of_day == "AFTERNOON": start_hour = 13
        elif time_of_day == "EVENING": start_hour = 18
        elif time_of_day == "NIGHT": start_hour = 22
        
        for i in range(5):
            # If airline filter is set and NOT 'ANY', force it
            effective_filter = airline_filter if airline_filter and airline_filter != "ANY" else None
            
            if effective_filter and (i < 4): # Ensure at least 4 match
                # Find the airline object
                airline = next((a for a in mock_airlines if a["code"] == effective_filter), {"code": effective_filter, "name": "Filtered Airline"})
            else:
                airline = random.choice(mock_airlines)
            
            # Apply Filter strict check
            if effective_filter and airline["code"] != effective_filter:
                continue
                
            try:
                # Generate time based on preference
                hour = (start_hour + i) % 24
                dep_time = datetime.strptime(f"{date} {hour:02d}:00", "%Y-%m-%d %H:%M")
            except:
                dep_time = datetime.now()
            
            arr_time = dep_time + timedelta(hours=11)
            
            flights.append(AntigravityFlight(
                offer_id=f"mock_{i}_{airline['code']}",
                provider="SIMULATION",
                price=Decimal(base_price + (i * 50)),
                currency="USD",
                segments=[FlightSegment(
                    carrier_code=airline["code"],
                    flight_number=f"{airline['code']}{100+i}",
                    departure_iata=origin,
                    arrival_iata=dest,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    duration="11h 00m"
                )],
                duration_total="11h 00m",
                cabin_class=cabin or "ECONOMY",
                refundable=True
            ))
            
        return flights

    def _deduplicate(self, flights: List[AntigravityFlight]) -> List[AntigravityFlight]:
        unique_map = {}
        
        for f in flights:
            if not f.segments:
                continue
                
            # Key: First Segment Flight Number + Departure Time
            # This is a heuristic. 
            key = f"{f.segments[0].carrier_code}{f.segments[0].flight_number}_{f.segments[0].departure_time}"
            
            if key in unique_map:
                existing = unique_map[key]
                # Keep lower price
                if f.price < existing.price:
                    unique_map[key] = f
            else:
                unique_map[key] = f
                
        return list(unique_map.values())
