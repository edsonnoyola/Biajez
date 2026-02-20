import asyncio
import os
import time
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
    except Exception as e:
        print(f"⚠️ Cache load failed: {e}")
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"⚠️ Cache save failed: {e}")

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
        duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
        if not duffel_token:
            print("⚠️ WARNING: DUFFEL_ACCESS_TOKEN not set!")
            print(f"   Available env vars: {[k for k in os.environ.keys() if 'DUFFEL' in k.upper()]}")
        else:
            print(f"✅ Duffel token loaded: {duffel_token[:20]}...")
        self.duffel = Duffel(access_token=duffel_token, api_version="v2")

    async def search_hybrid_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        cabin_class: str = "ECONOMY",
        airline: Optional[str] = None,
        time_of_day: str = "ANY",
        num_passengers: int = 1,
        user_id: Optional[str] = None
    ) -> List[AntigravityFlight]:
        """
        Parallel execution of Amadeus and Duffel searches with intelligent scoring.
        """
        print(f"DEBUG: Searching flights - Origin: {origin}, Dest: {destination}, Date: {departure_date}, Cabin: {cabin_class}, Time: {time_of_day}, AIRLINE: {airline}")
        
        # Run all THREE sources in parallel
        amadeus_task = asyncio.create_task(self._search_amadeus(origin, destination, departure_date, cabin_class, airline, return_date))
        duffel_task = asyncio.create_task(self._search_duffel(
            origin=origin,
            dest=destination,
            date=departure_date,
            cabin=cabin_class,
            airline_filter=airline,
            return_date=return_date,
            num_passengers=num_passengers,
            time_of_day=time_of_day,
            user_id=user_id
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
                    score += 50  # Strong boost for matching time preference

            # 6. PROVIDER PREFERENCE (Duffel more reliable)
            if flight.provider == "DUFFEL":
                score += 5

            # 7. CHANGEABLE TICKET BOOST
            if flight.metadata and flight.metadata.get("changeable"):
                score += 10

            flight.score = score

        # FILTER by time_of_day if specified
        if time_of_day != "ANY":
            def matches_time_filter(flight):
                dep_hour = flight.segments[0].departure_time.hour
                if time_of_day == "EARLY_MORNING": return 0 <= dep_hour < 6
                elif time_of_day == "MORNING": return 6 <= dep_hour < 12
                elif time_of_day == "AFTERNOON": return 12 <= dep_hour < 18
                elif time_of_day == "EVENING": return 18 <= dep_hour < 22
                elif time_of_day == "NIGHT": return 22 <= dep_hour <= 23
                return True

            matching_flights = [f for f in all_flights if matches_time_filter(f)]
            if matching_flights:
                all_flights = matching_flights
                print(f"DEBUG: Filtered to {len(all_flights)} flights matching {time_of_day}")
            else:
                print(f"DEBUG: No flights match {time_of_day}, returning all results")

        # FILTER by airline if specified - SHOW ONLY REQUESTED AIRLINE
        if airline:
            airline_upper = airline.upper()
            def matches_airline_filter(flight):
                if not flight.segments:
                    return False
                carrier = flight.segments[0].carrier_code
                return carrier and carrier.upper() == airline_upper

            airline_flights = [f for f in all_flights if matches_airline_filter(f)]
            if airline_flights:
                all_flights = airline_flights
                print(f"DEBUG: Filtered to {len(all_flights)} flights for airline {airline}")
            else:
                print(f"DEBUG: No flights found for airline {airline}, returning all results with warning")
                # Mark that no flights from requested airline were found
                # The AI should inform the user

        # GLOBAL FILTER: Only show flights that can be changed OR cancelled
        # Any airline is fine, but must be flexible (user requirement)
        flexible = [f for f in all_flights if
            (f.metadata and f.metadata.get("changeable")) or f.refundable]
        if flexible:
            print(f"DEBUG: Filtered to {len(flexible)} flexible flights (changeable or refundable) from {len(all_flights)} total")
            all_flights = flexible
        else:
            print("WARNING: No flexible flights found at all — showing all results as fallback")

        # Sort by score (highest first)
        all_flights.sort(key=lambda f: f.score, reverse=True)

        # Log top 3 scores
        for i, flight in enumerate(all_flights[:3]):
            segments = len(flight.segments)
            carrier = flight.segments[0].carrier_code if flight.segments else "?"
            dep_time = flight.segments[0].departure_time.strftime("%H:%M") if flight.segments else "?"
            changeable = "✅" if (flight.metadata or {}).get("changeable") else "❌"
            refundable = "✅" if flight.refundable else "❌"
            print(f"DEBUG: Rank {i+1}: {carrier} {dep_time} - Score={flight.score}, Price=${flight.price}, Change={changeable}, Refund={refundable}")

        return all_flights[:30]  # Return top 30


    async def search_multicity(self, segments: List[Dict[str, str]], cabin_class="ECONOMY", num_passengers=1) -> List[AntigravityFlight]:
        """
        Search for multi-city flights using Duffel.
        segments: [{"origin": "MEX", "destination": "MAD", "date": "2025-12-15"}, ...]
        """
        print(f"DEBUG: Searching Multi-City: {segments} (Pax: {num_passengers})")
        
        # Map to Duffel slices
        duffel_slices = [{
            "origin": s["origin"], 
            "destination": s["destination"], 
            "departure_date": s["date"]
        } for s in segments]
        
        # Call Duffel with custom slices
        # We pass None for standard args as they are ignored when custom_slices is present
        return await self._search_duffel(None, None, None, cabin_class, custom_slices=duffel_slices, num_passengers=num_passengers)

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
                for itin_idx, itin in enumerate(offer['itineraries']):
                    for seg in itin['segments']:
                        segments.append(FlightSegment(
                            carrier_code=seg['carrierCode'],
                            flight_number=seg['number'],
                            departure_iata=seg['departure']['iataCode'],
                            arrival_iata=seg['arrival']['iataCode'],
                            departure_time=datetime.fromisoformat(seg['departure']['at']),
                            arrival_time=datetime.fromisoformat(seg['arrival']['at']),
                            duration=seg['duration'],
                            slice_index=itin_idx,
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

    async def _search_duffel(self, origin, dest, date, cabin, airline_filter=None, return_date=None, custom_slices=None, num_passengers=1, time_of_day="ANY", user_id=None):
        try:
            import requests
            token = os.getenv("DUFFEL_ACCESS_TOKEN")
            # Duffel best practice: use return_offers=true and supplier_timeout for speed
            url = "https://api.duffel.com/air/offer_requests?return_offers=true&supplier_timeout=20000"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept-Encoding": "gzip",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Duffel-Version": "v2"
            }

            if custom_slices:
                slices = custom_slices
            else:
                slices = [{"origin": origin, "destination": dest, "departure_date": date}]
                if return_date:
                    slices.append({"origin": dest, "destination": origin, "departure_date": return_date})

            # Duffel best practice: add departure_time filter based on time_of_day preference
            # This reduces results at the API level for faster responses
            if time_of_day and time_of_day != "ANY":
                time_ranges = {
                    "EARLY_MORNING": {"from": "00:00", "to": "06:00"},
                    "MORNING": {"from": "06:00", "to": "12:00"},
                    "AFTERNOON": {"from": "12:00", "to": "18:00"},
                    "EVENING": {"from": "18:00", "to": "23:59"},
                    "NIGHT": {"from": "22:00", "to": "23:59"},
                }
                dep_time = time_ranges.get(time_of_day)
                if dep_time and not custom_slices:
                    # Add departure_time to the first slice
                    slices[0]["departure_time"] = dep_time

            # Generate passengers list dynamically based on num_passengers
            # Per Duffel docs: include loyalty_programme_accounts + given_name/family_name
            # at search time for potentially discounted fares
            passengers_list = []
            loyalty_accounts = []
            user_names = {}

            if user_id:
                try:
                    from app.db.database import engine as db_engine
                    from sqlalchemy import text
                    with db_engine.connect() as conn:
                        # Get user profile for name (required by Duffel when sending loyalty)
                        profile_row = conn.execute(
                            text("SELECT legal_first_name, legal_last_name FROM profiles WHERE user_id = :uid"),
                            {"uid": user_id}
                        ).fetchone()
                        if profile_row:
                            user_names = {
                                "given_name": profile_row[0],
                                "family_name": profile_row[1]
                            }

                        # Get all loyalty programs for this user
                        lp_rows = conn.execute(
                            text("SELECT airline_code, program_number FROM loyalty_programs WHERE user_id = :uid"),
                            {"uid": user_id}
                        ).fetchall()
                        for row in lp_rows:
                            loyalty_accounts.append({
                                "airline_iata_code": row[0],
                                "account_number": row[1]
                            })
                        if loyalty_accounts:
                            print(f"✈️ Search with {len(loyalty_accounts)} loyalty programs for user {user_id}")
                except Exception as lp_err:
                    print(f"DEBUG: Could not load loyalty for search: {lp_err}")

            for i in range(num_passengers):
                pax = {"type": "adult"}
                # Only add loyalty + names to first passenger (the registered user)
                if i == 0 and loyalty_accounts and user_names:
                    pax["given_name"] = user_names["given_name"]
                    pax["family_name"] = user_names["family_name"]
                    pax["loyalty_programme_accounts"] = loyalty_accounts
                passengers_list.append(pax)

            payload = {
                "data": {
                    "slices": slices,
                    "passengers": passengers_list,
                    "cabin_class": (cabin or "economy").lower(),
                    "max_connections": 1  # Duffel best practice: limit connections for speed + relevance
                }
            }

            print(f"DEBUG: Duffel request payload: {json.dumps(payload, indent=2)}")

            def _duffel_search_with_retry():
                from app.services.whatsapp_redis import duffel_breaker, session_manager
                redis_client = session_manager.redis_client if session_manager.enabled else None

                if not duffel_breaker.can_request(redis_client):
                    print("🔴 Circuit breaker OPEN — skipping Duffel search")
                    return None

                for attempt in range(3):
                    try:
                        resp = requests.post(url, json=payload, headers=headers, timeout=25)
                        if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                            wait = (attempt + 1) * 2
                            print(f"⚠️ Duffel search {resp.status_code}, retrying in {wait}s")
                            time.sleep(wait)
                            continue
                        if resp.status_code in (429, 500, 502, 503, 504):
                            duffel_breaker.record_failure(redis_client)
                        else:
                            duffel_breaker.record_success(redis_client)
                        return resp
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                        duffel_breaker.record_failure(redis_client)
                        if attempt < 2:
                            print(f"⚠️ Duffel search network error, retrying: {e}")
                            time.sleep((attempt + 1) * 2)
                        else:
                            raise
                return None

            response = await asyncio.to_thread(_duffel_search_with_retry)

            if not response or response.status_code != 201:
                print(f"Duffel Search Error: {response.status_code if response else 'no response'}")
                return []
                
            response_data = response.json()["data"]
            print(f"DEBUG: Duffel Raw Search Found {len(response_data['offers'])} offers")
            flights = []

            # In test mode, filter out offers that expire too quickly (Travelport sandbox issue)
            is_test_mode = token and "duffel_test_" in token
            valid_offers = response_data['offers']
            if is_test_mode:
                from datetime import timezone
                now = datetime.now(timezone.utc)
                filtered = []
                for o in valid_offers:
                    expires = o.get("expires_at")
                    if expires:
                        try:
                            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                            if (exp_dt - now).total_seconds() > 300:  # More than 5 min
                                filtered.append(o)
                        except:
                            filtered.append(o)
                    else:
                        filtered.append(o)
                print(f"DEBUG: Test mode - filtered {len(valid_offers)} → {len(filtered)} offers (removed quick-expiry)")
                valid_offers = filtered if filtered else valid_offers[:5]

            for offer in valid_offers:
                # NOTE: Don't filter by airline here - we'll boost preferred airline in scoring
                # This ensures we always return results even if preferred airline isn't available
                    
                segments = []
                for slice_idx, slice in enumerate(offer['slices']):
                    for seg in slice['segments']:
                        segments.append(FlightSegment(
                            carrier_code=seg['operating_carrier']['iata_code'],
                            flight_number=seg.get('operating_carrier_flight_number') or seg.get('marketing_carrier_flight_number') or "",
                            departure_iata=seg['origin']['iata_code'],
                            arrival_iata=seg['destination']['iata_code'],
                            departure_time=datetime.fromisoformat(seg['departing_at']),
                            arrival_time=datetime.fromisoformat(seg['arriving_at']),
                            duration=seg['duration'] or "00:00",
                            slice_index=slice_idx,
                        ))
                
                # Store ALL passenger IDs for multi-passenger booking
                all_passenger_ids = [p['id'] for p in offer['passengers']]
                passenger_id = all_passenger_ids[0]

                # Extract change/refund conditions (use `or {}` because Duffel may return None explicitly)
                conditions = offer.get("conditions") or {}
                change_info = conditions.get("change_before_departure") or {}
                refund_info = conditions.get("refund_before_departure") or {}

                changeable = change_info.get("allowed", False) if change_info else False
                change_penalty = change_info.get("penalty_amount") if change_info else None
                change_currency = change_info.get("penalty_currency") if change_info else None
                refundable = refund_info.get("allowed", False) if refund_info else False

                flights.append(AntigravityFlight(
                    offer_id=f"DUFFEL::{offer['id']}::{passenger_id}",
                    provider="DUFFEL",
                    price=Decimal(offer['total_amount']),
                    currency=offer['total_currency'],
                    segments=segments,
                    duration_total=offer['slices'][0]['duration'] or "00:00",
                    cabin_class=cabin,
                    refundable=refundable,
                    metadata={
                        "changeable": changeable,
                        "change_penalty": change_penalty,
                        "change_penalty_currency": change_currency,
                        "passenger_ids": all_passenger_ids,
                    }
                ))
            
            # RULE: Only show flights that are both changeable AND refundable (cancellable)
            flexible_flights = [f for f in flights if
                f.metadata and f.metadata.get("changeable") and f.refundable]
            if flexible_flights:
                print(f"DEBUG: Filtered to {len(flexible_flights)} flexible (changeable+refundable) flights (from {len(flights)} total)")
                flights = flexible_flights
            else:
                # Fallback: at least changeable
                changeable_flights = [f for f in flights if f.metadata and f.metadata.get("changeable")]
                if changeable_flights:
                    print(f"DEBUG: No fully flexible flights, using {len(changeable_flights)} changeable flights")
                    flights = changeable_flights
                else:
                    print("WARNING: No changeable/refundable flights found, returning all results")

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
