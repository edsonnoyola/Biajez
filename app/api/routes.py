from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.flight_engine import FlightAggregator
from app.services.booking_execution import BookingOrchestrator
from app.services.hotel_engine import HotelEngine
from app.ai.agent import AntigravityAgent
from app.models.models import Profile, LoyaltyProgram, Trip, TripStatusEnum, Payment, PaymentStatusEnum
import json
from datetime import datetime

router = APIRouter()

# Initialize Services (Singleton-ish for this scope)
flight_aggregator = FlightAggregator()
hotel_engine = HotelEngine()
agent = AntigravityAgent()

@router.get("/v1/search")
async def search_flights(
    origin: str,
    destination: str,
    date: str,
    cabin: str = "ECONOMY",
    airline: str = None,
    time_of_day: str = "ANY",
    return_date: str = None,
    passengers: int = 1
):
    return await flight_aggregator.search_hybrid_flights(
        origin, destination, date, return_date, cabin, airline, time_of_day, passengers
    )

# ===== BATCH SEARCH ENDPOINTS =====

@router.post("/v1/search/batch")
async def create_batch_search(
    origin: str,
    destination: str,
    date: str,
    return_date: str = None,
    cabin: str = "economy",
    passengers: int = 1,
    supplier_timeout: int = 10000
):
    """
    Create a batch offer request for progressive flight search
    
    Query params:
        origin: Origin airport code (e.g., "MEX")
        destination: Destination airport code (e.g., "CUN")
        date: Departure date (YYYY-MM-DD)
        return_date: Optional return date for round trip
        cabin: Cabin class (economy, business, first)
        passengers: Number of passengers (default: 1)
        supplier_timeout: Timeout in milliseconds (default: 10000)
    
    Returns:
        {
            "batch_id": "orq_xxx",
            "total_batches": 2,
            "remaining_batches": 2,
            "created_at": "2024-01-01T00:00:00Z"
        }
    """
    from app.services.batch_search_service import BatchSearchService
    
    batch_service = BatchSearchService()
    return batch_service.create_batch_search(
        origin=origin,
        destination=destination,
        departure_date=date,
        return_date=return_date,
        cabin_class=cabin.lower(),
        passengers=passengers,
        supplier_timeout=supplier_timeout
    )

@router.get("/v1/search/batch/{batch_id}")
async def get_batch_results(batch_id: str):
    """
    Get results from a batch offer request (long-polling)
    
    URL params:
        batch_id: Batch offer request ID
    
    Returns:
        {
            "offers": [...],
            "total_batches": 2,
            "remaining_batches": 1,
            "is_complete": False
        }
    """
    from app.services.batch_search_service import BatchSearchService
    
    batch_service = BatchSearchService()
    return batch_service.get_batch_results(batch_id)

@router.post("/v1/book")
def book_flight(user_id: str, offer_id: str, provider: str, amount: float, seat_service_id: str = None, num_passengers: int = 1, db: Session = Depends(get_db)):
    # Auto-create profile if missing (for seamless demo)
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        print(f"DEBUG: Auto-creating profile for {user_id}")
        from datetime import datetime
        profile = Profile(
            user_id=user_id,
            legal_first_name="Demo",
            legal_last_name="User",
            email="demo@example.com",
            phone_number="+16505550100",
            gender="M",
            dob=datetime.strptime("1990-01-01", "%Y-%m-%d").date(),
            passport_number="000000000",
            passport_expiry=datetime.strptime("2030-01-01", "%Y-%m-%d").date(),
            passport_country="US"
        )
        db.add(profile)
        db.commit()

    orchestrator = BookingOrchestrator(db)
    return orchestrator.execute_booking(user_id, offer_id, provider, amount, seat_service_id, num_passengers)

@router.post("/v1/chat")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    messages = data.get("messages", [])
    user_id = data.get("user_id") # Assuming passed in header or body
    
    try:
        # 0. Fetch User Context
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        user_context = ""
        if profile:
            user_context = f"""
            User Name: {profile.legal_first_name} {profile.legal_last_name}
            Seat Preference: {profile.seat_preference}
            Baggage Preference: {profile.baggage_preference}
            Preferred Seats (Specific): {profile.preferred_seats or "None"}
            Preferred Hotels: {profile.preferred_hotels or "None"}
            Loyalty Programs: {[f"{lp.airline_code}: {lp.program_number}" for lp in profile.loyalty_programs]}
            """
        
        # 1. Get AI Response
        response_message = await agent.chat(messages, user_context)
        
        # 2. Handle Tool Calls
        if response_message.tool_calls:
            # Append assistant message with tool calls
            messages.append(response_message.model_dump())
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                tool_result = None
                
                if function_name == "search_hybrid_flights":
                    print(f"DEBUG: Agent calling search_hybrid_flights with args: {arguments}")
                    tool_result = await flight_aggregator.search_hybrid_flights(
                        arguments["origin"], 
                        arguments["destination"], 
                        arguments["date"], 
                        arguments.get("return_date"),
                        arguments.get("cabin", "ECONOMY"),
                        arguments.get("airline"),
                        arguments.get("time_of_day", "ANY")
                    )
                    print(f"DEBUG: Tool returned {len(tool_result)} flights")
                    # Serialize for LLM
                    tool_result = [f.dict() for f in tool_result]
                    print(f"DEBUG: Serialized {len(tool_result)} flights for LLM")
                    
                elif function_name == "search_multicity_flights":
                    tool_result = await flight_aggregator.search_multicity(
                        arguments["segments"],
                        arguments.get("cabin", "ECONOMY")
                    )
                    tool_result = [f.dict() for f in tool_result]
                    
                elif function_name == "book_flight_final":
                    # We need provider and amount. 
                    # In a real flow, the agent should have this context or we extract it from the offer_id if encoded.
                    # Our offer_id is "PROVIDER::ID".
                    offer_id = arguments["offer_id"]
                    provider = offer_id.split("::")[0]
                    # We need amount. For now, we fetch it or assume it's passed. 
                    # Limitation: The tool definition didn't ask for amount. 
                    # We'll assume we can look it up or it's in the context.
                    # For this exercise, we'll mock the amount lookup or pass a dummy.
                    amount = 100.00 # Placeholder
                    
                    orchestrator = BookingOrchestrator(db)
                    booking_result = orchestrator.execute_booking(user_id, offer_id, provider, amount)
                    tool_result = booking_result # Contains pnr, ticket_number, ticket_url
                    
                elif function_name == "google_hotels":
                    from app.services.hotel_engine import HotelEngine
                    from app.utils.date_parser import SmartDateParser
                    
                    hotel_engine = HotelEngine()
                    args = arguments # arguments is already json.loads(tool_call.function.arguments)
                    
                    city = args.get("city")
                    checkin = args.get("checkin")
                    checkout = args.get("checkout")
                    
                    # Use SmartDateParser if dates are missing or seem incorrect
                    if not checkin or not checkout or checkin == "Unknown":
                        # Get original user message for better parsing
                        user_messages = [m for m in messages if m["role"] == "user"]
                        if user_messages:
                            last_user_msg = user_messages[-1]["content"]
                            parsed_checkin, parsed_checkout = SmartDateParser.parse_date_range(last_user_msg)
                            if parsed_checkin and parsed_checkout:
                                checkin = parsed_checkin
                                checkout = parsed_checkout
                                print(f"✅ SmartDateParser: {checkin} to {checkout}")
                    
                    tool_result = hotel_engine.search_hotels(
                        city=city,
                        checkin=checkin,
                        checkout=checkout,
                        amenities=args.get("amenities"),
                        room_type=args.get("room_type"),
                        landmark=args.get("landmark")
                    )
                    
                elif function_name == "add_loyalty_data":
                    # Add to DB
                    loyalty = LoyaltyProgram(
                        user_id=user_id,
                        airline_code=arguments["airline"],
                        program_number=arguments["number"]
                    )
                    db.add(loyalty)
                    db.commit()
                    tool_result = {"status": "success", "message": "Loyalty added"}

                elif function_name == "update_preferences":
                    if not profile:
                        # Create basic profile if not exists (for demo)
                        profile = Profile(
                            user_id=user_id, 
                            legal_first_name="Demo", 
                            legal_last_name="User",
                            dob="1990-01-01",
                            gender="M",
                            passport_number="Encrypted",
                            passport_expiry="2030-01-01",
                            passport_country="US"
                        )
                        db.add(profile)
                    
                    if "seat" in arguments:
                        profile.seat_preference = arguments["seat"]
                    if "baggage" in arguments:
                        profile.baggage_preference = arguments["baggage"]
                    if "preferred_seats" in arguments:
                        profile.preferred_seats = arguments["preferred_seats"]
                    if "preferred_hotels" in arguments:
                        profile.preferred_hotels = arguments["preferred_hotels"]
                    
                    db.commit()
                    tool_result = {"status": "success", "message": f"Preferences updated."}
                
                # Append Tool Message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str)
                })
                
            # 3. Get Final Response
            final_response = await agent.chat(messages, user_context)
            # Append final response to history
            messages.append({"role": "assistant", "content": final_response.content})
            return {"response": final_response.content, "messages": messages}
            
        # No tool calls
        messages.append({"role": "assistant", "content": response_message.content})
        return {"response": response_message.content, "messages": messages}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL ERROR in /v1/chat: {e}")
        return {"response": f"System Error: {str(e)}", "messages": messages}

@router.post("/v1/chat/stream")
async def chat_stream(request: Request, db: Session = Depends(get_db)):
    """
    Chat endpoint con streaming usando Server-Sent Events
    Retorna respuestas en tiempo real para efecto typewriter
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    
    async def generate():
        try:
            data = await request.json()
            messages = data.get("messages", [])
            user_id = data.get("user_id")
            
            # Fetch User Context
            profile = db.query(Profile).filter(Profile.user_id == user_id).first()
            user_context = ""
            if profile:
                user_context = f"""
                User Name: {profile.legal_first_name} {profile.legal_last_name}
                Seat Preference: {profile.seat_preference}
                Baggage Preference: {profile.baggage_preference}
                Preferred Seats (Specific): {profile.preferred_seats or "None"}
                Preferred Hotels: {profile.preferred_hotels or "None"}
                Loyalty Programs: {[f"{lp.airline_code}: {lp.program_number}" for lp in profile.loyalty_programs]}
                """
            
            # Stream response from agent
            async for chunk in agent.chat_stream(messages, user_context):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for typewriter effect
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"CRITICAL ERROR in /v1/chat/stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/v1/profile/{user_id}")
def get_profile(user_id: str, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        # Return empty/default structure if not found
        return {
            "legal_first_name": "",
            "legal_last_name": "",
            "dob": "",
            "passport_number": "",
            "passport_expiry": "",
            "passport_country": "",
            "known_traveler_number": "",
            "seat_preference": "ANY",
            "baggage_preference": "CARRY_ON",
            "email": "",
            "phone_number": ""
        }
    return profile


# ===== PROFILE CRM ENDPOINTS =====

@router.get("/v1/profiles")
def list_all_profiles(
    search: str = None,
    seat_preference: str = None,
    flight_class: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all profiles with optional filters (CRM endpoint)
    
    Query params:
        search: Search by name, email, or phone
        seat_preference: Filter by WINDOW, AISLE, etc.
        flight_class: Filter by ECONOMY, BUSINESS, etc.
        limit: Max results (default 50)
        offset: Pagination offset
    """
    query = db.query(Profile)
    
    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Profile.legal_first_name.ilike(search_term)) |
            (Profile.legal_last_name.ilike(search_term)) |
            (Profile.email.ilike(search_term)) |
            (Profile.phone_number.ilike(search_term))
        )
    
    # Apply preference filters
    if seat_preference:
        query = query.filter(Profile.seat_preference == seat_preference.upper())
    if flight_class:
        query = query.filter(Profile.flight_class_preference == flight_class.upper())
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    profiles = query.offset(offset).limit(limit).all()
    
    # Format response
    return {
        "profiles": [
            {
                "user_id": p.user_id,
                "name": f"{p.legal_first_name} {p.legal_last_name}",
                "email": p.email,
                "phone_number": p.phone_number,
                "seat_preference": p.seat_preference,
                "flight_class_preference": p.flight_class_preference,
                "hotel_preference": p.hotel_preference,
                "preferred_airline": p.preferred_airline,
                "created": str(p.dob) if p.dob else None
            }
            for p in profiles
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.delete("/v1/profiles/{user_id}")
def delete_profile(user_id: str, db: Session = Depends(get_db)):
    """Delete a profile (CRM endpoint)"""
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Also delete loyalty programs
    db.query(LoyaltyProgram).filter(LoyaltyProgram.user_id == user_id).delete()
    
    db.delete(profile)
    db.commit()
    
    return {"status": "success", "message": f"Profile {user_id} deleted"}

@router.put("/v1/profile/{user_id}")
async def update_profile(user_id: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
    
    # Update fields
    # Note: In a real app, use Pydantic models for validation
    if "legal_first_name" in data: profile.legal_first_name = data["legal_first_name"]
    if "legal_last_name" in data: profile.legal_last_name = data["legal_last_name"]
    from datetime import datetime
    if "dob" in data and data["dob"]: profile.dob = datetime.strptime(data["dob"], "%Y-%m-%d").date()
    if "passport_number" in data: profile.passport_number = data["passport_number"]
    if "passport_expiry" in data and data["passport_expiry"]: profile.passport_expiry = datetime.strptime(data["passport_expiry"], "%Y-%m-%d").date()
    if "passport_country" in data: profile.passport_country = data["passport_country"]
    if "known_traveler_number" in data: profile.known_traveler_number = data["known_traveler_number"]
    if "seat_preference" in data: profile.seat_preference = data["seat_preference"]
    if "baggage_preference" in data: profile.baggage_preference = data["baggage_preference"]
    if "email" in data: profile.email = data["email"]
    if "phone_number" in data: profile.phone_number = data["phone_number"]
    if "preferred_seats" in data: profile.preferred_seats = data["preferred_seats"]
    if "preferred_hotels" in data: profile.preferred_hotels = data["preferred_hotels"]
    
    # Set defaults for required fields if missing (hack for demo)
    if not profile.gender: profile.gender = "M" 
    
    db.commit()
    return {"status": "success", "profile": profile}

@router.get("/v1/trips/{user_id}")
def get_trips(user_id: str, db: Session = Depends(get_db)):
    trips = db.query(Trip).filter(Trip.user_id == user_id).all()
    return trips

@router.post("/v1/trips/{pnr}/cancel")
def cancel_trip(pnr: str, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.booking_reference == pnr).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip.status = TripStatusEnum.CANCELLED
    db.commit()
    return {"status": "success", "message": "Trip cancelled successfully"}

@router.get("/v1/seats/{offer_id}")
def get_seat_map(offer_id: str):
    # Extract real ID if needed (DUFFEL::ID)
    if "::" in offer_id:
        offer_id = offer_id.split("::")[1]
    
    import requests
    import os
    
    token = os.getenv("DUFFEL_ACCESS_TOKEN")
    url = f"https://api.duffel.com/air/seat_maps?offer_id={offer_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Duffel-Version": "v2"
    }
    
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            # If no seat map (e.g. not supported by airline), return empty
            return {"maps": []}
            
        return {"maps": res.json()["data"]}
    except Exception as e:
        print(f"Error fetching seats: {e}")
        return {"maps": []}

# ===== BOOKING ENDPOINTS (INTERNAL USE - NO PAYMENT PROCESSING) =====

@router.post("/v1/booking/create")
async def create_internal_booking(request: Request, db: Session = Depends(get_db)):
    """
    Create a booking directly for internal use (no payment processing)
    
    Body: {
        "user_id": "USER123",
        "offer_id": "DUFFEL::off_xxx",
        "provider": "DUFFEL",
        "amount": 150.50,
        "currency": "USD",
        "seat_service_id": "ase_xxx" (optional),
        "credit_id": "acd_xxx" (optional)
    }
    """
    try:
        data = await request.json()
        user_id = data.get("user_id")
        offer_id = data.get("offer_id")
        provider = data.get("provider")
        amount = data.get("amount")
        currency = data.get("currency", "USD")
        seat_service_id = data.get("seat_service_id")
        credit_id = data.get("credit_id")
        
        # Create booking directly (internal use - no payment processing)
        orchestrator = BookingOrchestrator(db)
        booking_result = orchestrator.execute_booking(
            user_id=user_id,
            offer_id=offer_id,
            provider=provider,
            amount=amount,
            seat_service_id=seat_service_id
        )
        
        # Mark credit as spent if used
        if credit_id:
            from app.services.airline_credits_service import AirlineCreditsService
            credits_service = AirlineCreditsService(db)
            try:
                credits_service.mark_credit_as_spent(
                    credit_id=credit_id,
                    order_id=booking_result.get("pnr", "unknown")
                )
                print(f"✅ Credit {credit_id} marked as spent for booking {booking_result.get('pnr')}")
            except Exception as e:
                print(f"⚠️  Warning: Could not mark credit as spent: {e}")
        
        # Send confirmation email
        try:
            from app.services.email_service import EmailService
            profile = db.query(Profile).filter(Profile.user_id == user_id).first()
            
            if profile and profile.email:
                trip = db.query(Trip).filter(Trip.booking_reference == booking_result.get("pnr")).first()
                email_data = {
                    "pnr": booking_result.get("pnr", "N/A"),
                    "departure_city": trip.departure_city if trip else "N/A",
                    "arrival_city": trip.arrival_city if trip else "N/A",
                    "departure_date": trip.departure_date if trip else "N/A",
                    "passenger_name": f"{profile.legal_first_name} {profile.legal_last_name}",
                    "total_amount": f"{amount:.2f}",
                    "currency": currency
                }
                
                EmailService.send_booking_confirmation(
                    to_email=profile.email,
                    booking_data=email_data,
                    booking_type="flight"
                )
                print(f"✅ Confirmation email sent to {profile.email}")
        except Exception as e:
            print(f"⚠️  Warning: Email sending failed: {e}")
        
        print(f"✅ Internal booking created: {booking_result.get('pnr')}")
        
        return {
            "success": True,
            "booking": booking_result,
            "credit_applied": credit_id is not None
        }
        
    except Exception as e:
        print(f"❌ Error creating booking: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Legacy endpoint - redirects to new internal booking endpoint
@router.post("/v1/payment/confirm")
async def confirm_payment_and_book_legacy(request: Request, db: Session = Depends(get_db)):
    """
    Legacy endpoint - now creates booking directly for internal use
    """
    return await create_internal_booking(request, db)


# ===== HOTEL ENDPOINTS =====

@router.get("/v1/hotels")
async def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1
):
    """
    Search for hotels using LiteAPI
    
    Query params:
        location: City name (e.g., "Cancun", "Mexico City")
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests (default: 2)
        rooms: Number of rooms (default: 1)
    """
    try:
        from app.services.liteapi_hotels import LiteAPIService
        
        lite_api = LiteAPIService()
        hotels = lite_api.search_hotels(
            location=location,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms
        )
        
        # Transform to match frontend expectations
        results = []
        for hotel in hotels:
            results.append({
                "offer_id": hotel.get("offer_id"),
                "provider": "LITEAPI",
                "name": hotel.get("name"),
                "location": hotel.get("location"),
                "price": hotel.get("price_total", "0"),
                "currency": hotel.get("currency", "USD"),
                "rating": hotel.get("rating", 0),
                "image": hotel.get("image", ""),
                "check_in": check_in,
                "check_out": check_out,
                "metadata": {
                    "address": hotel.get("address", ""),
                    "hotel_id": hotel.get("id")
                }
            })
        
        return results
        
    except Exception as e:
        print(f"❌ Hotel search error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty list instead of error for better UX
        return []

# ===== AIRLINE CREDITS ENDPOINTS =====

@router.get("/v1/credits/{user_id}")
def get_user_credits(user_id: str, include_spent: bool = False, db: Session = Depends(get_db)):
    """Get all airline credits for a user"""
    from app.services.airline_credits_service import AirlineCreditsService
    credits_service = AirlineCreditsService(db)
    return {"credits": credits_service.get_user_credits(user_id, include_spent)}

@router.get("/v1/credits/detail/{credit_id}")
def get_credit_detail(credit_id: str, db: Session = Depends(get_db)):
    """Get details of a specific credit"""
    from app.services.airline_credits_service import AirlineCreditsService
    credits_service = AirlineCreditsService(db)
    return credits_service.get_credit_details(credit_id)

@router.get("/v1/credits/available/{user_id}/{airline_code}")
def get_available_credits_for_airline(
    user_id: str, 
    airline_code: str, 
    db: Session = Depends(get_db)
):
    """Get available credits for a specific airline"""
    from app.services.airline_credits_service import AirlineCreditsService
    credits_service = AirlineCreditsService(db)
    return {
        "credits": credits_service.get_available_credits_for_airline(user_id, airline_code)
    }

@router.post("/v1/credits/create")
async def create_credit(request: Request, db: Session = Depends(get_db)):
    """
    Create an airline credit
    
    Body: {
        "user_id": "USER123",
        "airline_iata_code": "AM",
        "amount": 150.00,
        "currency": "USD",
        "order_id": "ord_xxx" (optional),
        "credit_code": "ABC123" (optional),
        "expires_days": 365 (optional)
    }
    """
    from app.services.airline_credits_service import AirlineCreditsService
    data = await request.json()
    
    credits_service = AirlineCreditsService(db)
    credit = credits_service.create_credit(
        user_id=data["user_id"],
        airline_iata_code=data["airline_iata_code"],
        amount=data["amount"],
        currency=data["currency"],
        order_id=data.get("order_id"),
        credit_code=data.get("credit_code"),
        expires_days=data.get("expires_days", 365)
    )
    
    return credit

@router.post("/v1/credits/apply")
async def apply_credit(request: Request, db: Session = Depends(get_db)):
    """
    Apply a credit to a booking
    
    Body: {
        "credit_id": "acd_xxx",
        "order_id": "ord_xxx"
    }
    """
    from app.services.airline_credits_service import AirlineCreditsService
    data = await request.json()
    
    credits_service = AirlineCreditsService(db)
    result = credits_service.mark_credit_as_spent(
        credit_id=data["credit_id"],
        order_id=data["order_id"]
    )
    
    return result

@router.get("/v1/credits/balance/{user_id}")
def get_credit_balance(user_id: str, db: Session = Depends(get_db)):
    """Get total available credit balance by currency"""
    from app.services.airline_credits_service import AirlineCreditsService
    credits_service = AirlineCreditsService(db)
    return {"balances": credits_service.get_total_available_balance(user_id)}
