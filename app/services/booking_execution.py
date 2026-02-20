import os
import time
import stripe
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.models import Profile, LoyaltyProgram, Trip, TripStatusEnum, ProviderSourceEnum
from amadeus import Client
from duffel_api import Duffel
from app.services.liteapi_hotels import LiteAPIService
import json
import requests as _requests


def _duffel_request_with_retry(method, url, headers, max_retries=2, **kwargs):
    """Make a Duffel API request with retry on transient failures (429, 500, 502, 503, 504).
    Integrates with circuit breaker to stop requests when Duffel is down."""
    from app.services.whatsapp_redis import duffel_breaker, session_manager
    redis_client = session_manager.redis_client if session_manager.enabled else None

    # Circuit breaker check
    if not duffel_breaker.can_request(redis_client):
        raise Exception("Duffel API no disponible temporalmente. Intenta en 1 minuto.")

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            if method == "GET":
                resp = _requests.get(url, headers=headers, **kwargs)
            else:
                resp = _requests.post(url, headers=headers, **kwargs)

            # Retry on transient HTTP errors
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = (attempt + 1) * 2  # 2s, 4s
                print(f"⚠️ Duffel {resp.status_code}, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue

            # Record result in circuit breaker
            if resp.status_code in (429, 500, 502, 503, 504):
                duffel_breaker.record_failure(redis_client)
            else:
                duffel_breaker.record_success(redis_client)

            return resp
        except (_requests.exceptions.Timeout, _requests.exceptions.ConnectionError) as e:
            last_exc = e
            duffel_breaker.record_failure(redis_client)
            if attempt < max_retries:
                wait = (attempt + 1) * 2
                print(f"⚠️ Duffel network error, retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise
    raise last_exc or Exception("Duffel request failed after retries")

def save_trip_sql(booking_reference, user_id, provider_source, total_amount, status,
                   invoice_url=None, confirmed_at=None, departure_city=None,
                   arrival_city=None, departure_date=None, duffel_order_id=None,
                   eticket_number=None):
    """Save Trip record using raw SQL - ORM writes don't persist on Render PostgreSQL."""
    from app.db.database import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO trips (booking_reference, user_id, provider_source, total_amount, status,
                                       invoice_url, confirmed_at, departure_city, arrival_city,
                                       departure_date, duffel_order_id, eticket_number)
                    VALUES (:booking_reference, :user_id, :provider_source, :total_amount, :status,
                            :invoice_url, :confirmed_at, :departure_city, :arrival_city,
                            :departure_date, :duffel_order_id, :eticket_number)
                """),
                {
                    "booking_reference": booking_reference,
                    "user_id": user_id,
                    "provider_source": provider_source,
                    "total_amount": total_amount,
                    "status": status,
                    "invoice_url": invoice_url,
                    "confirmed_at": confirmed_at,
                    "departure_city": departure_city,
                    "arrival_city": arrival_city,
                    "departure_date": str(departure_date) if departure_date else None,
                    "duffel_order_id": duffel_order_id,
                    "eticket_number": eticket_number,
                }
            )
            conn.commit()
        print(f"✅ Trip saved via raw SQL: {booking_reference}")
        return True
    except Exception as e:
        print(f"❌ Trip save FAILED: {booking_reference} - {e}")
        return False


class BookingOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.amadeus = Client(
            client_id=os.getenv("AMADEUS_CLIENT_ID"),
            client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
            hostname=os.getenv("AMADEUS_HOSTNAME", "test")
        )
        self.duffel = Duffel(access_token=os.getenv("DUFFEL_ACCESS_TOKEN"))
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    def execute_booking(self, user_id: str, offer_id: str, provider: str, amount: float, seat_service_id: str = None, num_passengers: int = 1, companions: list = None):
        # 1. Context Loading - Use RAW SQL to ensure we get latest data
        from app.db.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM profiles WHERE user_id = :uid"),
                {"uid": user_id}
            )
            row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User profile not found")

        # Convert row to Profile-like object for compatibility
        row_dict = dict(row._mapping)

        # Ensure date fields are proper date objects (DB may return strings)
        from datetime import date, datetime
        def to_date(val):
            if val is None:
                return None
            if isinstance(val, date):
                return val
            if isinstance(val, str):
                try:
                    return datetime.strptime(val[:10], "%Y-%m-%d").date()
                except:
                    return None
            return val

        user_profile = Profile(
            user_id=row_dict.get('user_id'),
            phone_number=row_dict.get('phone_number'),
            legal_first_name=row_dict.get('legal_first_name'),
            legal_last_name=row_dict.get('legal_last_name'),
            email=row_dict.get('email'),
            gender=row_dict.get('gender', 'M'),
            dob=to_date(row_dict.get('dob')),
            passport_number=row_dict.get('passport_number'),  # Decrypted below
            passport_expiry=to_date(row_dict.get('passport_expiry')),
            passport_country=row_dict.get('passport_country'),
            known_traveler_number=row_dict.get('known_traveler_number'),
        )
        # Decrypt passport number for API calls
        from app.utils.encryption import decrypt_value
        if user_profile.passport_number:
            user_profile.passport_number = decrypt_value(user_profile.passport_number)
        print(f"📋 BOOKING PROFILE: {user_profile.legal_first_name} {user_profile.legal_last_name}, dob={user_profile.dob}, email={user_profile.email}")

        # NOTE: No Stripe payment needed - we're an internal agency
        # Duffel bookings use balance payment (charged to agency account)
        # Amadeus bookings are also direct

        # 3. Execution & Data Injection
        # Normalize provider to uppercase for consistency
        provider = provider.upper()
        
        if provider == "AMADEUS":
            return self._book_amadeus(user_profile, offer_id, amount, num_passengers)
        elif provider == "DUFFEL":
            return self._book_duffel(user_profile, offer_id, amount, seat_service_id, num_passengers, companions or [])
        elif provider == "AMADEUS_HOTEL":
            return self._book_hotel(user_profile, offer_id, amount)
        elif provider == "LITEAPI":
            return self._book_liteapi(user_profile, offer_id, amount)
        elif provider == "SIMULATION":
            return self._book_simulation(user_profile, offer_id, amount)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    def _book_simulation(self, profile: Profile, offer_id: str, amount: float):
        print(f"DEBUG: Executing Simulation Booking for {offer_id}")
        # Generate a fake PNR
        pnr = "SIM" + os.urandom(3).hex().upper()
        
        # Save Trip to DB using raw SQL (ORM doesn't persist on Render)
        from datetime import datetime
        save_trip_sql(
            booking_reference=pnr,
            user_id=profile.user_id,
            provider_source="AMADEUS",
            total_amount=amount,
            status="TICKETED",
            invoice_url="https://stripe.com/invoice/sim_123",
            confirmed_at=datetime.utcnow().isoformat()
        )
        
        # Generate Ticket
        from app.services.ticket_generator import TicketGenerator
        
        # Mock Flight Data for Ticket
        mock_flight_data = {
            "segments": [{
                "origin": "MEX", 
                "destination": "MAD", 
                "departure_time": "2025-12-15T10:00:00",
                "arrival_time": "2025-12-15T21:00:00",
                "carrier_code": "AM",
                "number": "100"
            }]
        }
        
        ticket_url = TicketGenerator.generate_html_ticket(
            pnr, 
            f"{profile.legal_first_name} {profile.legal_last_name}", 
            mock_flight_data, 
            amount
        )
        
        return {"pnr": pnr, "ticket_number": "SIM-TICKET", "ticket_url": ticket_url}

    def _book_amadeus(self, profile: Profile, offer_id: str, amount: float, num_passengers: int = 1):
        # Extract real ID (AMADEUS::ID)
        real_offer_id = offer_id.split("::")[1]
        
        # Prepare Traveler Element
        traveler = {
            "id": "1",
            "dateOfBirth": profile.dob.isoformat(),
            "name": {
                "firstName": profile.legal_first_name,
                "lastName": profile.legal_last_name
            },
            "gender": profile.gender.upper(),
            "contact": {
                "emailAddress": profile.email or "user@example.com",
                "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": profile.phone_number.replace("+1", "") if profile.phone_number else "6465550100"}]
            },
            "documents": [
                {
                    "documentType": "PASSPORT",
                    "number": profile.passport_number, # In real app, decrypt this
                    "expiryDate": profile.passport_expiry.isoformat(),
                    "issuanceCountry": profile.passport_country,
                    "nationality": profile.passport_country,
                    "holder": True
                }
            ]
        }

        # Inject KTN (Known Traveler Number)
        if profile.known_traveler_number:
            traveler["documents"].append({
                "documentType": "KNOWN_TRAVELER",
                "number": profile.known_traveler_number,
                "issuanceCountry": "US", # Assuming US for KTN
                "nationality": "US",
                "holder": True
            })

        # 1. Retrieve Full Offer from Cache
        from app.services.flight_engine import load_cache
        OFFER_CACHE = load_cache() # Reload to ensure freshness
        
        full_offer_id = f"AMADEUS::{real_offer_id}"
        original_offer = OFFER_CACHE.get(full_offer_id)
        
        if not original_offer:
            print(f"DEBUG: Offer {full_offer_id} not found in cache. Keys: {list(OFFER_CACHE.keys())}")
            raise HTTPException(status_code=404, detail="Offer expired or not found. Please search again.")

        try:
            # 2. Pricing (Validation)
            # Required by Amadeus before booking
            pricing_response = self.amadeus.shopping.flight_offers.pricing.post(
                data={
                    "type": "flight-offers-pricing",
                    "flightOffers": [original_offer]
                }
            )
            priced_offer = pricing_response.data["flightOffers"][0]
            
            # 3. Booking (Create Order)
            body = {
                "data": {
                    "type": "flight-order",
                    "flightOffers": [priced_offer],
                    "travelers": [traveler]
                }
            }
            
            response = self.amadeus.booking.flight_orders.post(body)
            order = response.data
            pnr = order['id'] # Amadeus Order ID is often used as PNR or reference
            ticket_number = order.get('associatedRecords', [{}])[0].get('reference', 'PENDING')
            
            # Save Trip using raw SQL (ORM doesn't persist on Render)
            from datetime import datetime
            save_trip_sql(
                booking_reference=pnr,
                user_id=profile.user_id,
                provider_source="AMADEUS",
                total_amount=amount,
                status="TICKETED",
                invoice_url="https://stripe.com/invoice/123",
                confirmed_at=datetime.utcnow().isoformat()
            )
            
            # Generate HTML Ticket
            from app.services.ticket_generator import TicketGenerator
            # Extract real flight data from priced_offer for the ticket
            # Simplified mapping for the generator
            seg = priced_offer['itineraries'][0]['segments'][0]
            mock_flight_data = {
                "segments": [{
                    "origin": seg['departure']['iataCode'],
                    "destination": seg['arrival']['iataCode'],
                    "departure_time": seg['departure']['at'],
                    "arrival_time": seg['arrival']['at'],
                    "carrier_code": seg['carrierCode'],
                    "number": seg['number']
                }]
            }
            ticket_url = TicketGenerator.generate_html_ticket(
                pnr, 
                f"{profile.legal_first_name} {profile.legal_last_name}", 
                mock_flight_data, 
                amount
            )
            
            return {"pnr": pnr, "ticket_number": ticket_number, "ticket_url": ticket_url}
            
        except Exception as e:
            print(f"Amadeus Real Booking Error: {e}")
            raise HTTPException(status_code=500, detail=f"Amadeus Booking Failed: {str(e)}")
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Amadeus Booking Failed: {str(e)}")

    def _book_duffel(self, profile: Profile, offer_id: str, amount: float, seat_service_id: str = None, num_passengers: int = 1, companions: list = None):
        # Extract real ID and Passenger ID (DUFFEL::offer_id::passenger_id)
        parts = offer_id.split("::")
        real_offer_id = parts[1]
        first_passenger_id = parts[2] if len(parts) > 2 else None

        import requests
        token = os.getenv("DUFFEL_ACCESS_TOKEN")
        url = "https://api.duffel.com/air/orders"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Duffel-Version": "v2"
        }

        # Fetch all passenger IDs from the offer (needed for multi-pax)
        all_passenger_ids = [first_passenger_id] if first_passenger_id else []
        if num_passengers > 1:
            try:
                offer_pax_resp = requests.get(
                    f"https://api.duffel.com/air/offers/{real_offer_id}",
                    headers=headers, timeout=15
                )
                if offer_pax_resp.status_code == 200:
                    offer_pax_data = offer_pax_resp.json()["data"]
                    all_passenger_ids = [p["id"] for p in offer_pax_data.get("passengers", [])]
                    print(f"DEBUG: Fetched {len(all_passenger_ids)} passenger IDs from offer")
            except Exception as pid_err:
                print(f"DEBUG: Could not fetch passenger IDs: {pid_err}")

        # Fix phone number format for Duffel (requires E.164: +52XXXXXXXXXX)
        phone = profile.phone_number or "+16505550100"
        phone = phone.replace("+", "").strip()
        if phone.startswith("521") and len(phone) == 13:
            phone = "52" + phone[3:]  # Remove extra "1" from WhatsApp format
        phone = f"+{phone}"

        companions = companions or []

        # Build passengers list
        passengers_list = []
        for i in range(num_passengers):
            pax_id = all_passenger_ids[i] if i < len(all_passenger_ids) else f"pas_000{i}"

            if i == 0:
                # Primary passenger (registered user)
                passenger = {
                    "born_on": profile.dob.isoformat(),
                    "email": profile.email or "passenger@example.com",
                    "family_name": profile.legal_last_name,
                    "given_name": profile.legal_first_name,
                    "gender": "m" if profile.gender == "M" else "f",
                    "title": "mr" if profile.gender == "M" else "ms",
                    "phone_number": phone,
                    "id": pax_id,
                }
                # Add passport
                if profile.passport_number and profile.passport_expiry and profile.passport_country:
                    passenger["identity_documents"] = [{
                        "type": "passport",
                        "unique_identifier": profile.passport_number,
                        "expires_on": profile.passport_expiry.isoformat(),
                        "issuing_country_code": profile.passport_country
                    }]
                # Add KTN
                if profile.known_traveler_number:
                    if "identity_documents" not in passenger:
                        passenger["identity_documents"] = []
                    passenger["identity_documents"].append({
                        "type": "known_traveler_number",
                        "unique_identifier": profile.known_traveler_number,
                        "issuing_country_code": "US"
                    })
            else:
                # Companion passenger (from collected data)
                comp_idx = i - 1
                if comp_idx < len(companions):
                    comp = companions[comp_idx]
                    comp_gender = comp.get("gender", "M")
                    passenger = {
                        "born_on": comp["dob"],
                        "email": profile.email or "passenger@example.com",
                        "family_name": comp["family_name"],
                        "given_name": comp["given_name"],
                        "gender": "m" if comp_gender == "M" else "f",
                        "title": "mr" if comp_gender == "M" else "ms",
                        "phone_number": phone,
                        "id": pax_id,
                    }
                else:
                    # Fallback: shouldn't happen if companion collection worked
                    print(f"⚠️ Missing companion data for passenger {i+1}, using placeholder")
                    passenger = {
                        "born_on": profile.dob.isoformat(),
                        "email": profile.email or "passenger@example.com",
                        "family_name": profile.legal_last_name,
                        "given_name": f"Pasajero{i+1}",
                        "gender": "m" if profile.gender == "M" else "f",
                        "title": "mr" if profile.gender == "M" else "ms",
                        "phone_number": phone,
                        "id": pax_id,
                    }

            print(f"DEBUG: Passenger {i+1}: {passenger['given_name']} {passenger['family_name']} (id={pax_id})")
            passengers_list.append(passenger)
        
        # Add loyalty program matching the flight's airline
        # Per Duffel docs: loyalty_programme_accounts on the passenger at booking time
        try:
            loyalty_programs = self.db.query(LoyaltyProgram).filter(
                LoyaltyProgram.user_id == profile.user_id
            ).all()

            if loyalty_programs:
                print(f"DEBUG: User has {len(loyalty_programs)} loyalty programs")
                # Get airline code from the offer to match correctly
                flight_airline_code = None
                try:
                    offer_check = requests.get(
                        f"https://api.duffel.com/air/offers/{real_offer_id}",
                        headers=headers, timeout=15
                    )
                    if offer_check.status_code == 200:
                        offer_info = offer_check.json()["data"]
                        # Get operating carrier from first segment
                        slices = offer_info.get("slices", [])
                        if slices:
                            segs = slices[0].get("segments", [])
                            if segs:
                                flight_airline_code = segs[0].get("operating_carrier", {}).get("iata_code")
                                print(f"DEBUG: Flight airline code: {flight_airline_code}")
                except Exception as offer_err:
                    print(f"DEBUG: Could not fetch offer for airline match: {offer_err}")

                # Match loyalty program to flight airline, fallback to first program
                matched_lp = None
                if flight_airline_code:
                    matched_lp = next((lp for lp in loyalty_programs if lp.airline_code == flight_airline_code), None)

                if not matched_lp:
                    # Fallback: use first program (user might have partner airline miles)
                    matched_lp = loyalty_programs[0]
                    print(f"DEBUG: No exact airline match, using first loyalty: {matched_lp.airline_code}")

                # Add to first passenger only
                passengers_list[0]["loyalty_programme_accounts"] = [{
                    "airline_iata_code": matched_lp.airline_code,
                    "account_number": matched_lp.program_number
                }]
                print(f"✈️ Added loyalty {matched_lp.airline_code} - {matched_lp.program_number} to booking")
        except Exception as lp_error:
            print(f"DEBUG: Could not add loyalty program: {lp_error}")
        
        # Add services (seats) if selected
        services = []
        if seat_service_id:
            services.append({
                "id": seat_service_id,
                "quantity": 1
            })
        
        # Re-fetch offer to get latest price before booking (per Duffel docs)
        try:
            offer_resp = _duffel_request_with_retry(
                "GET", f"https://api.duffel.com/air/offers/{real_offer_id}",
                headers={**headers, "Content-Type": "application/json"}, timeout=15
            )
            if offer_resp.status_code == 200:
                offer_data = offer_resp.json()["data"]
                duffel_amount = offer_data.get("total_amount", str(amount))
                duffel_currency = offer_data.get("total_currency", "USD")
                print(f"DEBUG: Duffel offer total: {duffel_amount} {duffel_currency} (passed: {amount})")
            else:
                duffel_amount = str(amount)
                duffel_currency = "USD"
                print(f"DEBUG: Could not fetch offer, using passed amount: {amount}")
        except Exception as offer_err:
            duffel_amount = str(amount)
            duffel_currency = "USD"
            print(f"DEBUG: Offer fetch error: {offer_err}, using passed amount: {amount}")

        data = {
            "data": {
                "selected_offers": [real_offer_id],
                "passengers": passengers_list,
                "payments": [{"amount": str(duffel_amount), "currency": duffel_currency, "type": "balance"}]
            }
        }

        if services:
            data["data"]["services"] = services

        try:
            # Add idempotency key to prevent duplicate bookings on retry
            import hashlib
            idem_source = f"{profile.user_id}:{real_offer_id}:{duffel_amount}"
            idem_key = hashlib.sha256(idem_source.encode()).hexdigest()[:40]
            booking_headers = {**headers, "Idempotency-Key": idem_key}

            response = _duffel_request_with_retry("POST", url, booking_headers, json=data, timeout=30)

            if response.status_code not in [200, 201]:
                 print(f"❌ Duffel booking API error: {response.status_code}")
                 raise Exception(f"Duffel booking failed (status {response.status_code})")
                 
            order_data = response.json()["data"]
            pnr = order_data['booking_reference']
            ticket_number = order_data['id']

            # Extract e-ticket numbers from Duffel documents
            eticket_numbers = [doc['unique_identifier'] for doc in order_data.get('documents', [])
                               if doc.get('type') == 'electronic_ticket' and doc.get('unique_identifier')]
            eticket_str = ', '.join(eticket_numbers) if eticket_numbers else None
            if eticket_str:
                print(f"🎫 E-ticket numbers: {eticket_str}")

            # SAFETY NET: Save PNR to Redis immediately after Duffel confirms
            # This way even if DB save fails, we have a record of the booking
            try:
                import redis
                r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
                import json as _json
                r.setex(
                    f"booking_backup:{pnr}",
                    86400 * 30,  # Keep for 30 days
                    _json.dumps({
                        "pnr": pnr,
                        "duffel_order_id": ticket_number,
                        "user_id": profile.user_id,
                        "amount": amount,
                        "timestamp": datetime.utcnow().isoformat() if 'datetime' in dir() else "unknown"
                    })
                )
                print(f"🔒 Booking backup saved to Redis: {pnr}")
            except Exception as redis_err:
                print(f"⚠️ Redis backup failed (non-critical): {redis_err}")

            # Extract flight details from order
            from datetime import datetime
            slices = order_data.get('slices', [])
            departure_city = None
            arrival_city = None
            departure_date = None

            if slices:
                first_slice = slices[0]
                segments = first_slice.get('segments', [])
                if segments:
                    first_segment = segments[0]
                    last_segment = segments[-1]
                    departure_city = first_segment.get('origin', {}).get('iata_code')
                    arrival_city = last_segment.get('destination', {}).get('iata_code')
                    dep_time = first_segment.get('departing_at', '')
                    if dep_time:
                        try:
                            departure_date = datetime.fromisoformat(dep_time.replace('Z', '+00:00')).date()
                        except:
                            pass

            # Save Trip using raw SQL (ORM doesn't persist on Render)
            db_saved = save_trip_sql(
                booking_reference=pnr,
                user_id=profile.user_id,
                provider_source="DUFFEL",
                total_amount=amount,
                status="TICKETED",
                invoice_url=None,
                confirmed_at=datetime.utcnow().isoformat(),
                departure_city=departure_city,
                arrival_city=arrival_city,
                departure_date=departure_date,
                duffel_order_id=ticket_number,
                eticket_number=eticket_str
            )
            if not db_saved:
                print(f"🚨 CRITICAL: Duffel booking {pnr} (order {ticket_number}) succeeded but DB save failed!")
                # Escalate: alert admin via WhatsApp
                try:
                    admin_phone = os.getenv("ADMIN_PHONE")
                    if admin_phone:
                        from app.services.push_notification_service import PushNotificationService
                        import asyncio
                        _push = PushNotificationService()
                        _alert = (
                            f"🚨 *DB SAVE FAILED*\n\n"
                            f"PNR: {pnr}\nOrder: {ticket_number}\n"
                            f"User: {profile.user_id}\nAmount: {amount}\n\n"
                            f"Booking en Duffel pero NO en DB!"
                        )
                        try:
                            _loop = asyncio.get_event_loop()
                            if _loop.is_running():
                                asyncio.ensure_future(_push.send_message(admin_phone, _alert))
                            else:
                                _loop.run_until_complete(_push.send_message(admin_phone, _alert))
                        except RuntimeError:
                            pass
                except Exception:
                    pass  # Alert is best-effort, Redis backup already has the data

            # Generate HTML Ticket with REAL Duffel data
            from app.services.ticket_generator import TicketGenerator
            
            # Extract real flight data from Duffel order
            slices = order_data.get('slices', [])
            flight_segments = []
            
            for slice_data in slices:
                for segment in slice_data.get('segments', []):
                    flight_segments.append({
                        "origin": segment.get('origin', {}).get('iata_code', 'XXX'),
                        "destination": segment.get('destination', {}).get('iata_code', 'XXX'),
                        "departure_time": segment.get('departing_at', ''),
                        "arrival_time": segment.get('arriving_at', ''),
                        "carrier_code": segment.get('marketing_carrier', {}).get('iata_code', ''),
                        "number": segment.get('marketing_carrier_flight_number', ''),
                        "aircraft": segment.get('aircraft', {}).get('name', 'Aircraft')
                    })
            
            real_flight_data = {
                "segments": flight_segments,
                "cabin_class": order_data.get('cabin_class', 'economy'),
                "total_amount": order_data.get('total_amount', amount),
                "currency": order_data.get('total_currency', 'USD')
            }
            
            ticket_url = TicketGenerator.generate_html_ticket(
                pnr,
                f"{profile.legal_first_name} {profile.legal_last_name}",
                real_flight_data,  # ✅ REAL DATA from Duffel
                amount
            )

            # Send email confirmation (rich template with segments, airline, eTicket)
            try:
                from app.services.email_service import EmailService
                passenger_name = f"{profile.legal_first_name} {profile.legal_last_name}"

                # Extract airline name from first segment
                airline_name = ""
                if flight_segments:
                    carrier_code = flight_segments[0].get("carrier_code", "")
                    # Try to get full airline name from order
                    for sl in order_data.get("slices", []):
                        for seg in sl.get("segments", []):
                            op_carrier = seg.get("operating_carrier", {})
                            if op_carrier.get("name"):
                                airline_name = op_carrier["name"]
                                break
                        if airline_name:
                            break

                email_data = {
                    "pnr": pnr,
                    "departure_city": departure_city or "N/A",
                    "arrival_city": arrival_city or "N/A",
                    "departure_date": str(departure_date) if departure_date else "N/A",
                    "passenger_name": passenger_name,
                    "total_amount": str(duffel_amount),
                    "currency": duffel_currency or "USD",
                    "airline_name": airline_name,
                    "eticket_number": eticket_str or "",
                    "segments": flight_segments,  # Rich segment data for email template
                }
                if profile.email and "@whatsapp.temp" not in profile.email:
                    EmailService.send_booking_confirmation(profile.email, email_data, "flight")
                    print(f"📧 Email enviado a {profile.email}")
            except Exception as email_error:
                print(f"⚠️ Error enviando email (no critico): {email_error}")

            # Send WhatsApp booking confirmation
            try:
                from app.services.push_notification_service import PushNotificationService
                import asyncio
                if profile.phone_number:
                    push_svc = PushNotificationService()
                    route = f"{departure_city or '?'} → {arrival_city or '?'}"
                    dep_str = str(departure_date) if departure_date else "Pendiente"

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(push_svc.send_booking_confirmation(
                                profile.phone_number, pnr, route, dep_str, float(duffel_amount), duffel_currency or "USD"
                            ))
                        else:
                            loop.run_until_complete(push_svc.send_booking_confirmation(
                                profile.phone_number, pnr, route, dep_str, float(duffel_amount), duffel_currency or "USD"
                            ))
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(push_svc.send_booking_confirmation(
                                profile.phone_number, pnr, route, dep_str, float(duffel_amount), duffel_currency or "USD"
                            ))
                        finally:
                            loop.close()
                    print(f"📱 WhatsApp confirmacion enviado a {profile.phone_number}")
            except Exception as wa_error:
                print(f"⚠️ Error enviando WhatsApp (no critico): {wa_error}")

            return {"pnr": pnr, "ticket_number": ticket_number, "ticket_url": ticket_url,
                    "eticket_number": eticket_str, "duffel_order_id": ticket_number,
                    "offer_id": real_offer_id, "db_saved": db_saved}

        except Exception as e:
            print(f"DEBUG: Duffel Booking Error: {e}")
            raise HTTPException(status_code=500, detail=f"Duffel Booking Failed: {str(e)}")

    def _book_hotel(self, profile: Profile, offer_id: str, amount: float):
        # HANDLE MOCK HOTELS
        if "MOCK_" in offer_id:
            print(f"DEBUG: Booking Mock Hotel {offer_id}")
            pnr = "HTL-" + os.urandom(3).hex().upper()
            
            # Save Trip using raw SQL (ORM doesn't persist on Render)
            save_trip_sql(
                booking_reference=pnr,
                user_id=profile.user_id,
                provider_source="AMADEUS_HOTEL",
                total_amount=amount,
                status="TICKETED",
                invoice_url="https://stripe.com/invoice/mock_htl"
            )
            
            # Generate Ticket
            from app.services.ticket_generator import TicketGenerator
            mock_hotel_data = {
                "name": "Mock Hotel (Confirmed)",
                "address": {"cityName": "Destination City"},
                "checkin": "2025-12-15",
                "checkout": "2025-12-20"
            }
            ticket_url = TicketGenerator.generate_hotel_ticket(
                pnr, 
                f"{profile.legal_first_name} {profile.legal_last_name}", 
                mock_hotel_data, 
                amount
            )
            return {"pnr": pnr, "ticket_number": "CONFIRMED", "ticket_url": ticket_url}

        # --- REAL IMPLEMENTATION (Ready for Production) ---
        try:
            # Try to create VCC, but fallback to Test Card if it fails
            payment = None
            try:
                # ... Stripe Logic ...
                # For now, we skip Stripe and use Test Card directly for stability in this demo
                raise Exception("Skip Stripe")
            except:
                # Fallback to Amadeus Test Card (Visa)
                payment = {
                    "method": "CREDIT_CARD",
                    "card": {
                        "vendorCode": "VI",
                        "cardNumber": "4444333322221111", # Amadeus Test Visa
                        "expiryDate": "2025-12"
                    }
                }
            
            body = {
                "data": {
                    "offerId": offer_id,
                    "guests": [{
                        "name": {
                            "title": "MR" if profile.gender == "M" else "MS",
                            "firstName": profile.legal_first_name,
                            "lastName": profile.legal_last_name
                        },
                        "contact": {
                            "phone": profile.phone_number or "+15555555555",
                            "email": profile.email or "user@example.com"
                        }
                    }],
                    "payments": [payment]
                }
            }
            
            response = self.amadeus.booking.hotel_bookings.post(body)
            order_data = response.data[0] # Usually a list
            pnr = order_data['id']
            
            # Save Trip using raw SQL (ORM doesn't persist on Render)
            save_trip_sql(
                booking_reference=pnr,
                user_id=profile.user_id,
                provider_source="AMADEUS_HOTEL",
                total_amount=amount,
                status="TICKETED",
                invoice_url="https://stripe.com/invoice/789"
            )
            
            # Generate Hotel Ticket
            from app.services.ticket_generator import TicketGenerator
            mock_hotel_data = {
                "name": "Confirmed Hotel", # Should extract from response
                "address": {"cityName": "Unknown"},
                "checkin": "2025-12-15",
                "checkout": "2025-12-20"
            }
            ticket_url = TicketGenerator.generate_hotel_ticket(
                pnr, 
                f"{profile.legal_first_name} {profile.legal_last_name}", 
                mock_hotel_data, 
                amount
            )
            
            return {"pnr": pnr, "ticket_number": "CONFIRMED", "ticket_url": ticket_url}
            
        except Exception as e:
             print(f"Real Hotel Booking Error: {e}")
             raise HTTPException(status_code=500, detail=f"Hotel Booking Failed: {str(e)}")

    def _book_liteapi(self, profile: Profile, offer_id: str, amount: float):
        """
        Execute LiteAPI hotel booking
        """
        print(f"DEBUG: Executing LiteAPI Booking for {offer_id}")
        
        try:
            lite = LiteAPIService()
            
            # Prepare guest info
            guest_info = {
                "first_name": profile.legal_first_name,
                "last_name": profile.legal_last_name,
                "email": profile.email
            }
            
            # Execute booking
            booking_res = lite.book_hotel(offer_id, guest_info)
            
            pnr = booking_res.get("booking_id")
            
            # Save Trip using raw SQL (ORM doesn't persist on Render)
            from datetime import datetime
            save_trip_sql(
                booking_reference=pnr,
                user_id=profile.user_id,
                provider_source="AMADEUS_HOTEL",
                total_amount=amount,
                status="TICKETED",
                invoice_url="https://stripe.com/invoice/lite_123",
                confirmed_at=datetime.utcnow().isoformat()
            )
            
            # Generate Ticket
            from app.services.ticket_generator import TicketGenerator
            
            # Parse offer_id for hotel info (handle MOCK and real formats)
            if offer_id.startswith("MOCK_"):
                # MOCK hotels: MOCK_RC_CAN, MOCK_FS_CAN, etc.
                hotel_name = "Mock Hotel (Confirmed)"
                checkin = booking_res.get("checkin", "2026-02-10")
                checkout = booking_res.get("checkout", "2026-02-13")
            elif "::" in offer_id:
                # Real LiteAPI format: LITEAPI::HOTELID::CHECKIN::CHECKOUT
                parts = offer_id.split("::")
                hotel_name = f"Hotel {parts[1] if len(parts) > 1 else 'Unknown'}"
                checkin = parts[2] if len(parts) > 2 else booking_res.get("checkin", "Unknown")
                checkout = parts[3] if len(parts) > 3 else booking_res.get("checkout", "Unknown")
            else:
                # Simple hotel ID
                hotel_name = f"Hotel {offer_id}"
                checkin = booking_res.get("checkin", "Unknown")
                checkout = booking_res.get("checkout", "Unknown")
            
            mock_hotel_data = {
                "name": hotel_name,
                "address": {"cityName": "Destination"},
                "checkin": checkin,
                "checkout": checkout
            }
            
            ticket_url = TicketGenerator.generate_hotel_ticket(
                pnr, 
                f"{profile.legal_first_name} {profile.legal_last_name}", 
                mock_hotel_data, 
                amount
            )
            
            return {"pnr": pnr, "ticket_number": booking_res.get("confirmation_code"), "ticket_url": ticket_url}
            
        except Exception as e:
            print(f"LiteAPI Booking Error: {e}")
            raise HTTPException(status_code=400, detail=f"LiteAPI Booking Failed: {str(e)}")
