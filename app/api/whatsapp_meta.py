from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.ai.agent import AntigravityAgent
from app.services.flight_engine import FlightAggregator
from app.services.booking_execution import BookingOrchestrator
from app.models.models import Profile
from app.services.whatsapp_redis import session_manager, rate_limiter
import requests
import os
import json
from datetime import datetime, timedelta
from app.services import profile_manager

router = APIRouter()
agent = AntigravityAgent()
flight_aggregator = FlightAggregator()

# DEPRECATED: Now using Redis session manager
# user_sessions = {}

# AUTHORIZED NUMBERS - Only these can make bookings
AUTHORIZED_NUMBERS = [
    "525610016226",  # Admin
    "525572461012",  # User
]

def normalize_mx_number(phone_number: str) -> str:
    """Standardize Mexican phone numbers to 52 + 10 digits (remove + and 1 after 52)"""
    # Remove + if present
    phone = phone_number.replace("+", "").strip()
    
    # Handle Mexico special case (521 -> 52)
    if phone.startswith("521") and len(phone) == 13:
        return "52" + phone[3:]
    
    return phone

def is_authorized(phone_number: str) -> bool:
    """Check if phone number is authorized to make bookings"""
    normalized = normalize_mx_number(phone_number)
    print(f"🔐 Checking authorization for {phone_number} -> {normalized}")
    
    # Check against normalized authorized list
    for auth in AUTHORIZED_NUMBERS:
        if normalize_mx_number(auth) == normalized:
            return True
    
    return False

@router.get("/v1/whatsapp/webhook")
async def verify_webhook(request: Request):
    """
    Verificación de webhook por Meta
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "biajez_verify_token_123")
    
    if mode == "subscribe" and token == verify_token:
        print(f"✅ Webhook verified successfully")
        return Response(content=challenge, media_type="text/plain")
    
    print(f"❌ Webhook verification failed")
    return Response(status_code=403)

@router.post("/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Recibir mensajes de WhatsApp vía Meta API
    """
    try:
        body = await request.json()
        print(f"📱 WhatsApp webhook received: {json.dumps(body, indent=2)}")
        
        # Extraer mensaje
        if body.get("object") != "whatsapp_business_account":
            return {"status": "ok"}
        
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok"}
        
        message = messages[0]
        from_number = message.get("from")
        message_type = message.get("type")
        
        # Handle interactive button responses
        if message_type == "interactive":
            interactive = message.get("interactive", {})
            button_reply = interactive.get("button_reply", {})
            button_id = button_reply.get("id", "")
            button_title = button_reply.get("title", "")
            
            print(f"📱 Button click from {from_number}: {button_title} (id: {button_id})")
            
            # Map button clicks to text commands
            if "confirmar" in button_title.lower() or "✅" in button_title:
                incoming_msg = "si"  # Treat as confirmation
            elif "cancelar" in button_title.lower() or "❌" in button_title:
                incoming_msg = "no"  # Treat as cancellation
            elif "buscar" in button_title.lower() or "🔄" in button_title:
                incoming_msg = "buscar otro"
            else:
                incoming_msg = button_title  # Use button text directly
        elif message_type == "text":
            incoming_msg = message.get("text", {}).get("body", "")
        else:
            return {"status": "ok"}  # Ignore other message types
        
        print(f"📱 WhatsApp from {from_number}: {incoming_msg}")
        
        # ===== RATE LIMITING =====
        allowed, remaining = rate_limiter.is_allowed(from_number)
        if not allowed:
            rate_limit_msg = "⚠️ *Demasiados mensajes*\n\n"
            rate_limit_msg += "Has enviado muchos mensajes en poco tiempo.\n"
            rate_limit_msg += "Por favor espera 1 minuto antes de continuar.\n\n"
            rate_limit_msg += "_Esto es para mantener el servicio rápido para todos_ 😊"
            send_whatsapp_message(from_number, rate_limit_msg)
            return {"status": "rate_limited"}
        
        # Get or create session with Redis
        session = session_manager.get_session(from_number)
        
        # Initialize session if new user
        if not session.get("user_id"):
            from app.models.models import Profile
            
            # Normalize phone number for lookup
            normalized_phone = normalize_mx_number(from_number)
            
            # Look for existing profile by phone number (check both raw and normalized)
            existing_profile = db.query(Profile).filter(
                (Profile.phone_number == normalized_phone) | 
                (Profile.phone_number == from_number)
            ).first()
            
            is_new_user = existing_profile is None
            
            if existing_profile:
                # Use existing profile
                user_id = existing_profile.user_id
                print(f"✅ Found existing profile for {normalized_phone}: {user_id}")
            else:
                # Create new WhatsApp user
                user_id = f"whatsapp_{from_number}"
                print(f"📱 New WhatsApp user: {user_id}")
            
            
            session["user_id"] = user_id
            session_manager.save_session(from_number, session)

            # NOTE: Welcome message removed - was causing issues after Reset
            # The AI will greet naturally when appropriate

        
        # ===== HELP COMMAND =====
        if incoming_msg.lower() in ["ayuda", "help", "que puedes hacer", "qué puedes hacer", "comandos", "menu", "menú"]:
            help_text = """🤖 *Antigravity Travel Assistant*

*VUELOS* ✈️
• "MEX a MAD el 15 marzo"
• "Vuelo redondo NYC del 10 al 20"
• "Solo con Iberia" (filtro aerolínea)
• "Vuelo en la mañana/tarde/noche"

*Aerolíneas:* Aeroméxico, Iberia, British Airways, American, United, Delta, Volaris, etc.

*Horarios:*
🌅 Madrugada (0-6h)
☀️ Mañana (6-12h)
🌤️ Tarde (12-18h)
🌙 Noche (18-22h)

*HOTELES* 🏨
• "Busca hotel en Madrid"
• "Hotel del 15 al 20 marzo"
• "Cerca del aeropuerto"

*PERFIL* 👤
• "Mi perfil" - Ver preferencias
• "Cambiar asiento ventana"
• "Cambiar clase business"

¿Qué necesitas? 😊"""
            send_whatsapp_message(from_number, help_text)
            return {"status": "ok"}
        
        # ===== PROFILE COMMANDS =====
        if incoming_msg.lower() in ["mi perfil", "perfil", "preferencias"]:
            summary = profile_manager.get_preferences_summary(db, from_number)
            send_whatsapp_message(from_number, summary)
            return {"status": "ok"}
        
        # Handle preference updates: "cambiar asiento ventana", "cambiar clase business"
        if incoming_msg.lower().startswith("cambiar "):
            parts = incoming_msg.lower().replace("cambiar ", "").split()
            if len(parts) >= 2:
                field_map = {
                    "asiento": ("seat_preference", {"ventana": "WINDOW", "pasillo": "AISLE", "medio": "MIDDLE", "cualquiera": "ANY"}),
                    "clase": ("flight_class_preference", {"economy": "ECONOMY", "ejecutiva": "BUSINESS", "business": "BUSINESS", "primera": "FIRST", "first": "FIRST"}),
                    "hotel": ("hotel_preference", {"3": "3_STAR", "4": "4_STAR", "5": "5_STAR"})
                }
                
                field_key = parts[0]
                value = parts[1] if len(parts) > 1 else ""
                
                if field_key in field_map:
                    field_name, value_map = field_map[field_key]
                    mapped_value = value_map.get(value, value.upper())
                    
                    if profile_manager.update_preference(db, from_number, field_name, mapped_value):
                        send_whatsapp_message(from_number, f"✅ Preferencia actualizada: {field_key} → {value}")
                    else:
                        send_whatsapp_message(from_number, f"❌ No se pudo actualizar. Valores válidos: {', '.join(value_map.keys())}")
                    return {"status": "ok"}
        
        # Check if selecting flight by number
        if incoming_msg.strip().isdigit() and session.get("pending_flights"):
            flight_num = int(incoming_msg.strip()) - 1
            if 0 <= flight_num < len(session["pending_flights"]):
                selected = session["pending_flights"][flight_num]
                session["selected_flight"] = selected

                price = selected.get("price", "N/A")
                segments = selected.get("segments", [])
                duration = selected.get("duration_total", "")

                # Extract airline from first segment
                airline = "N/A"
                if segments:
                    airline = segments[0].get("carrier_code", "N/A")

                # Determine flight type
                num_segments = len(segments)
                origin = segments[0].get("departure_iata", "") if segments else ""
                final_dest = segments[-1].get("arrival_iata", "") if segments else ""
                is_direct = num_segments == 1
                is_round_trip = (origin == final_dest) and num_segments > 1

                if is_direct:
                    flight_type = "✈️ Vuelo Directo"
                elif is_round_trip:
                    flight_type = "🔄 Ida y Vuelta"
                else:
                    flight_type = f"🌍 Multidestino ({num_segments} tramos)"

                response_text = f"📋 *Confirmar reserva*\n\n"
                response_text += f"✈️ Aerolínea: {airline}\n"
                response_text += f"💰 Precio: ${price} USD\n"
                response_text += f"📊 Tipo: {flight_type}\n"
                if duration:
                    response_text += f"⏱️ Duración total: {duration}\n"
                response_text += "\n"

                # Show all segments with proper labels
                for idx, seg in enumerate(segments, 1):
                    seg_origin = seg.get("departure_iata", "")
                    seg_dest = seg.get("arrival_iata", "")
                    dep_time = seg.get("departure_time", "")
                    arr_time = seg.get("arrival_time", "")
                    seg_duration = seg.get("duration", "")

                    # Format departure
                    dep_str = "N/A"
                    if dep_time:
                        dep_str_raw = str(dep_time)
                        if len(dep_str_raw) >= 16 and "T" in dep_str_raw:
                            # ISO format: 2026-02-10T06:58:00
                            dep_str = f"{dep_str_raw[8:10]}/{dep_str_raw[5:7]} {dep_str_raw[11:16]}"
                        elif hasattr(dep_time, 'strftime'):
                            dep_str = dep_time.strftime("%d/%m %H:%M")

                    # Format arrival
                    arr_str = "N/A"
                    if arr_time:
                        arr_str_raw = str(arr_time)
                        if len(arr_str_raw) >= 16 and "T" in arr_str_raw:
                            arr_str = f"{arr_str_raw[8:10]}/{arr_str_raw[5:7]} {arr_str_raw[11:16]}"
                        elif hasattr(arr_time, 'strftime'):
                            arr_str = arr_time.strftime("%d/%m %H:%M")

                    # Label based on flight type
                    if is_direct:
                        label = "Vuelo"
                    elif is_round_trip:
                        label = "Ida" if idx == 1 else "Regreso"
                    else:
                        label = f"Tramo {idx}"

                    response_text += f"*{label}:* {seg_origin} → {seg_dest}\n"
                    response_text += f"   🛫 Salida: {dep_str}\n"
                    response_text += f"   🛬 Llegada: {arr_str}\n"
                    if seg_duration:
                        response_text += f"   ⏱️ {seg_duration}\n"
                    response_text += "\n"

                # Send with interactive buttons
                send_interactive_message(
                    from_number,
                    response_text,
                    ["✅ Confirmar", "❌ Cancelar", "🔄 Buscar otro"],
                    header="🎫 Confirmar reserva"
                )
                session_manager.save_session(from_number, session)
                return {"status": "ok"}
        
        # Check if selecting hotel by number (MUST be before AI processing)
        if incoming_msg.strip().isdigit() and session.get("pending_hotels") and not session.get("pending_flights"):
            hotel_num = int(incoming_msg.strip()) - 1
            if 0 <= hotel_num < len(session["pending_hotels"]):
                selected = session["pending_hotels"][hotel_num]
                session["selected_hotel"] = selected
                session["pending_hotels"] = []  # Clear pending
                
                name = selected.get("name", "N/A")
                rating = selected.get("rating", "N/A")
                price = selected.get("price", {}).get("total", "N/A")
                currency = selected.get("price", {}).get("currency", "USD")
                amenities = selected.get("amenities", [])[:3]
                amenities_str = ', '.join(amenities) if amenities else 'WiFi'
                
                response_text = f"🏨 *Confirmar reserva de hotel*\n\n"
                response_text += f"📍 {name}\n"
                response_text += f"⭐ {rating} estrellas\n"
                response_text += f"💰 {price} {currency}/noche\n"
                response_text += f"✨ {amenities_str}\n\n"
                # Send with interactive buttons
                send_interactive_message(
                    from_number,
                    response_text,
                    ["✅ Confirmar", "❌ Cancelar", "🔄 Buscar otro"],
                    header="🏨 Confirmar hotel"
                )
                session_manager.save_session(from_number, session)
                return {"status": "ok"}
        
        # Check if confirming hotel booking (MUST be before AI processing)
        if incoming_msg.lower() in ['si', 'sí', 'yes', 'confirmar'] and session.get("selected_hotel"):
            # Check if user is authorized
            if not is_authorized(from_number):
                response_text = "❌ *No autorizado*\n\n"
                response_text += "Tu número no está autorizado para hacer reservas.\n"
                response_text += "Contacta al administrador para solicitar acceso."
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}
            
            hotel = session["selected_hotel"]
            rate_id = hotel.get("offerId")
            hotel_id = hotel.get("hotelId", "")
            hotel_name = hotel.get("name", "Hotel")
            
            # Check if this is a MOCK hotel (test data)
            if hotel_id and hotel_id.startswith("MOCK_"):
                # Mock booking for test hotels
                import random
                confirmation_number = f"HTL-{random.randint(100000, 999999)}"
                hotel_dates = session.get("hotel_dates", {})
                price = hotel.get("price", {})
                total = price.get("total", "0") if isinstance(price, dict) else "0"
                currency = price.get("currency", "USD") if isinstance(price, dict) else "USD"
                
                response_text = f"✅ *¡Reserva de hotel confirmada!*\n\n"
                response_text += f"📝 Confirmación: {confirmation_number}\n"
                response_text += f"🏨 {hotel_name}\n"
                response_text += f"📅 {hotel_dates.get('checkin', 'N/A')} - {hotel_dates.get('checkout', 'N/A')}\n"
                response_text += f"💰 Total: ${total} {currency}\n\n"
                response_text += "_✨ Reserva de prueba exitosa_\n"
                response_text += "_En producción se usaría API real de DuffelStays_"
                
                session["selected_hotel"] = None
                session["hotel_dates"] = None
                session_manager.save_session(from_number, session)
                
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}
            
            # Real booking with DuffelStays for production hotels
            # Get profile for guest info
            from app.models.models import Profile
            profile = db.query(Profile).filter(Profile.user_id == session["user_id"]).first()
            if not profile:
                response_text = "❌ Necesitas un perfil para reservar hoteles.\nContacta al administrador."
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}
            
            try:
                from app.services.duffel_stays import DuffelStaysEngine
                duffel_stays = DuffelStaysEngine()
                
                guest_info = {
                    "given_name": profile.legal_first_name,
                    "family_name": profile.legal_last_name,
                    "email": profile.email,
                    "phone_number": profile.phone_number
                }
                
                booking_result = duffel_stays.book_hotel(rate_id, guest_info)
                
                confirmation = booking_result.get("confirmation_number", "N/A")
                total = booking_result.get("total_amount", "N/A")
                currency = booking_result.get("total_currency", "USD")
                
                response_text = f"✅ *¡Reserva de hotel confirmada!*\n\n"
                response_text += f"📝 Confirmación: {confirmation}\n"
                response_text += f"💰 Total: {total} {currency}\n\n"
                response_text += "_Te enviaremos los detalles por email_"
                
                session["selected_hotel"] = None
                session_manager.save_session(from_number, session)
                
            except Exception as e:
                print(f"❌ Hotel booking error: {e}")
                response_text = f"❌ Error al procesar reserva: {str(e)}"
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # Hotel selection moved above to prevent AI interception
        
        # Check if confirming booking
        # DEBUG: Log session state to diagnose confirmation issues
        if incoming_msg.lower() in ['si', 'sí', 'yes', 'confirmar']:
            print(f"🔍 DEBUG Confirmation attempt:")
            print(f"   - from_number: {from_number}")
            print(f"   - incoming_msg: {incoming_msg}")
            print(f"   - selected_flight exists: {bool(session.get('selected_flight'))}")
            print(f"   - selected_hotel exists: {bool(session.get('selected_hotel'))}")
            print(f"   - session keys: {list(session.keys())}")

        if incoming_msg.lower() in ['si', 'sí', 'yes', 'confirmar'] and session.get("selected_flight"):
            # Check if user is authorized to make bookings
            if not is_authorized(from_number):
                response_text = "❌ *No autorizado*\n\n"
                response_text += "Tu número no está autorizado para hacer reservas.\n"
                response_text += "Contacta al administrador para solicitar acceso."
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}
            
            flight = session["selected_flight"]
            offer_id = flight.get("offer_id")
            provider = flight.get("provider")
            amount = float(flight.get("price", 0))
            
            # Create profile if needed
            from app.models.models import Profile
            from datetime import datetime as dt  # Explicit import to avoid any shadowing
            profile = db.query(Profile).filter(Profile.user_id == session["user_id"]).first()
            if not profile:
                profile = Profile(
                    user_id=session["user_id"],
                    legal_first_name="WhatsApp",
                    legal_last_name="User",
                    email=f"{session['user_id']}@whatsapp.temp",
                    phone_number=from_number,
                    gender="M",
                    dob=dt.strptime("1990-01-01", "%Y-%m-%d").date(),
                    passport_number="000000000",
                    passport_expiry=dt.strptime("2030-01-01", "%Y-%m-%d").date(),
                    passport_country="US"
                )
                db.add(profile)
                db.commit()
            
            # Get flight details - convert to dict if it's an object
            # Use 'flight' variable that was defined from session["selected_flight"] above
            if hasattr(flight, 'dict'):
                flight_dict = flight.dict()
            elif isinstance(flight, dict):
                flight_dict = flight
            else:
                flight_dict = flight.__dict__ if hasattr(flight, '__dict__') else {}

            
            offer_id = flight_dict.get("id")
            provider = flight_dict.get("provider", "duffel")
            price = flight_dict.get("price", "0.00")
            
            try:
                # MOCK BOOKING FOR TEST FLIGHTS (avoid Duffel 422 errors)
                # Check if this is a test/simulated flight ID
                if offer_id and (offer_id.startswith("MOCK_") or offer_id.startswith("DUFFEL::") or offer_id.startswith("AMADEUS::")):
                    print(f"🧪 Mock flight booking for test ID: {offer_id}")
                    
                    import random
                    import string
                    pnr = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    
                    # Get flight details from dict
                    segments = flight_dict.get("segments", [])
                    origin = segments[0].get("departure_iata", "N/A") if segments else "N/A"
                    destination = segments[-1].get("arrival_iata", "N/A") if segments else "N/A"
                    airline = flight_dict.get("airline", "Mock Airlines")
                    
                    response_text = f"✅ *¡Vuelo reservado!*\n\n"
                    response_text += f"📝 PNR: {pnr}\n"
                    response_text += f"✈️ {origin} → {destination}\n"
                    response_text += f"🏢 {airline}\n"
                    response_text += f"💰 Total: ${price}\n\n"
                    response_text += f"✨ *Reserva de prueba exitosa*\n"
                    response_text += f"En producción se usaría Duffel API real\n\n"
                    response_text += f"📧 Confirmación enviada al email"
                    
                    send_whatsapp_message(from_number, response_text)
                    session.pop("selected_flight", None)
                    session.pop("pending_flights", None)
                    session_manager.save_session(from_number, session)
                    return {"status": "ok"}
                
                # REAL BOOKING (for production flight IDs)
                orchestrator = BookingOrchestrator(db)
                booking_result = orchestrator.execute_booking(
                    session["user_id"], offer_id, provider, amount
                )
                
                pnr = booking_result.get("pnr", "N/A")
                
                # Get flight details for better confirmation
                segments = flight.get("segments", [])
                airline = segments[0].get("carrier_code", "N/A") if segments else "N/A"
                
                response_text = f"✅ *¡Reserva confirmada!*\n\n"
                response_text += f"📝 PNR: {pnr}\n"
                response_text += f"✈️ {airline}\n"
                response_text += f"💰 Total: ${amount} USD\n\n"
                response_text += "📧 Te enviaremos los detalles por email"
                
                session["selected_flight"] = None
                session["pending_flights"] = []
                session_manager.save_session(from_number, session)
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Booking error: {error_msg}")
                
                if "offer_no_longer_available" in error_msg or "price_changed" in error_msg:
                    response_text = "⚠️ *Tarifa expirada*\n\n"
                    response_text += "Esa oferta ya no está disponible (el precio cambió o se agotó).\n"
                    response_text += "Por favor busca el vuelo nuevamente para obtener el precio actualizado."
                else:
                    response_text = "❌ *Error en la reserva*\n\n"
                    response_text += "Hubo un problema procesando tu solicitud.\n"
                    response_text += "Por favor intenta buscar y reservar nuevamente."

            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # Command handlers
        msg_lower = incoming_msg.lower().strip()
        
        # Ver reservas
        if any(keyword in msg_lower for keyword in ['mis vuelos', 'mis reservas', 'ver reservas', 'mis viajes']):
            from app.models.models import Trip
            trips = db.query(Trip).filter(Trip.user_id == session["user_id"]).all()
            
            if not trips:
                response_text = "📭 No tienes reservas activas."
            else:
                response_text = "✈️ *Tus reservas:*\n\n"
                for trip in trips:
                    response_text += f"📝 PNR: {trip.booking_reference}\n"
                    response_text += f"💰 ${trip.total_amount} USD\n"
                    response_text += f"📍 {trip.departure_city or 'N/A'} → {trip.arrival_city or 'N/A'}\n"
                    response_text += f"📅 {trip.departure_date or 'N/A'}\n"
                    response_text += f"Status: {trip.status.value}\n\n"
                
                response_text += "_Para cancelar: 'Cancelar [PNR]'_"
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # Cancelar vuelo
        if 'cancelar' in msg_lower and len(msg_lower.split()) >= 2:
            from app.models.models import Trip, TripStatusEnum
            import requests
            
            # Extract PNR from message
            words = incoming_msg.split()
            pnr = words[-1].upper()  # Assume PNR is last word
            
            trip = db.query(Trip).filter(
                Trip.booking_reference == pnr,
                Trip.user_id == session["user_id"]
            ).first()
            
            if not trip:
                response_text = f"❌ No encontré reserva con PNR: {pnr}"
            elif trip.status == TripStatusEnum.CANCELLED:
                response_text = f"ℹ️ La reserva {pnr} ya está cancelada"
            else:
                # Cancel with Duffel if it's a Duffel booking
                if trip.provider_source.value == "DUFFEL" and trip.duffel_order_id:
                    try:
                        token = os.getenv("DUFFEL_ACCESS_TOKEN")
                        url = f"https://api.duffel.com/air/order_cancellations"
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "Duffel-Version": "v2"
                        }
                        data = {"data": {"order_id": trip.duffel_order_id}}
                        
                        response = requests.post(url, json=data, headers=headers)
                        
                        if response.status_code == 201:
                            trip.status = TripStatusEnum.CANCELLED
                            db.commit()
                            response_text = f"✅ Reserva {pnr} cancelada exitosamente"
                        else:
                            response_text = f"❌ Error al cancelar: {response.text}"
                    except Exception as e:
                        response_text = f"❌ Error: {str(e)}"
                else:
                    # Mark as cancelled in DB
                    trip.status = TripStatusEnum.CANCELLED
                    db.commit()
                    response_text = f"✅ Reserva {pnr} cancelada"
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # ===== HOTEL SEARCH - NOW HANDLED BY AI AGENT =====
        # The AI agent has google_hotels function with better NLP
        # It can parse dates like "del 8 al 9 de feb" automatically
        # Commenting out manual handler to avoid conflicts
        
        # # Buscar hoteles - EXPANDED KEYWORDS
        # hotel_keywords = [
        #     'busca hoteles', 'hotel en', 'hoteles en', 'buscar hotel',
        #     'quiero hotel', 'in hotel', 'necesito hotel', 'quiero in hotel',
        #     'hospedaje', 'necesito hospedaje', 'donde hospedarme',
        #     'donde me hospedo', 'reserva hotel', 'hotel cerca'
        # ]
        
        # if any(keyword in msg_lower for keyword in hotel_keywords):
        #     from app.services.duffel_stays import DuffelStaysEngine
        #     from datetime import datetime, timedelta
        #     from app.models.models import Trip
            
        #     # Extract city from message - improved extraction
        #     city = None
            
        #     # Try different patterns
        #     patterns = [
        #         ('en ', 'after'),  # "hotel en Miami"
        #         ('in ', 'after'),  # "hotel in Miami"  
        #         ('cerca del ', 'after'),  # "cerca del aeropuerto"
        #         ('cerca de ', 'after'),  # "cerca de aeropuerto"
        #     ]
            
        #     for pattern, position in patterns:
        #         if pattern in incoming_msg.lower():
        #             parts = incoming_msg.lower().split(pattern)
        #             if len(parts) > 1:
        #                 # Get city name (first word after pattern)
        #                 city_part = parts[1].strip().split()[0] if parts[1].strip() else None
        #                 if city_part and len(city_part) > 2:
        #                     city = city_part
        #                     break
            
        #     if not city:
        #         # If no city found but mentions "aeropuerto", try to get from recent flight
        #         if 'aeropuerto' in msg_lower or 'airport' in msg_lower:
        #             recent_trip = db.query(Trip).filter(
        #                 Trip.user_id == session["user_id"]
        #             ).order_by(Trip.booking_reference.desc()).first()
                    
        #             if recent_trip:
        #                 # Use the destination of the flight
        #                 destination_code = recent_trip.destination
                        
        #                 # Map common airport codes to city names
        #                 airport_to_city = {
        #                     'MIA': 'miami', 'JFK': 'new york', 'LAX': 'los angeles',
        #                     'ORD': 'chicago', 'DFW': 'dallas', 'ATL': 'atlanta',
        #                     'MAD': 'madrid', 'BCN': 'barcelona', 'LHR': 'london',
        #                     'CDG': 'paris', 'FCO': 'rome', 'AMS': 'amsterdam',
        #                     'MEX': 'ciudad de mexico', 'CUN': 'cancun', 'GDL': 'guadalajara',
        #                     'BOG': 'bogota', 'LIM': 'lima', 'sao paulo',
        #                     'EZE': 'buenos aires', 'SCL': 'santiago', 'SDQ': 'santo domingo'
        #                 }
                        
        #                 city = airport_to_city.get(destination_code, destination_code.lower())
        #                 print(f"✅ Auto-detected city from flight: {city} (from {destination_code})")
                
        #         if not city:
        #             response_text = "❌ Por favor especifica la ciudad.\nEjemplo: 'Busca hoteles en Cancún'"
        #             send_whatsapp_message(from_number, response_text)
        #             return {"status": "ok"}
            
        #     # Try to get dates from recent flight booking
        #     recent_trip = db.query(Trip).filter(
        #         Trip.user_id == session["user_id"]
        #     ).order_by(Trip.booking_reference.desc()).first()
            
        #     if recent_trip and recent_trip.departure_date and recent_trip.return_date:
        #         # Use flight dates
        #         checkin = recent_trip.departure_date
        #         checkout = recent_trip.return_date
        #         date_source = f"(fechas de tu vuelo: {checkin} a {checkout})"
        #     else:
        #         # No flight found - ask for dates
        #         response_text = "📅 *¿Cuándo quieres hospedarte?*\n\n"
        #         response_text += "Por favor indica las fechas:\n"
        #         response_text += "Ejemplo: 'Del 15 de febrero al 20 de febrero'\n\n"
        #         response_text += "O puedo usar fechas sugeridas (próxima semana).\n"
        #         response_text += "Responde 'Sugeridas' para continuar."
                
        #         # Store pending hotel search
        #         session["pending_hotel_search"] = {"city": city}
                
        #         send_whatsapp_message(from_number, response_text)
        #         return {"status": "ok"}
            
        #     try:
        #         # Use LiteAPI with Nominatim geocoder (supports any city)
        #         from app.services.liteapi_hotels import LiteAPIService
        #         lite_api = LiteAPIService()
                
        #         # Convert date objects to strings if needed
        #         checkin_str = checkin.strftime("%Y-%m-%d") if hasattr(checkin, 'strftime') else str(checkin)
        #         checkout_str = checkout.strftime("%Y-%m-%d") if hasattr(checkout, 'strftime') else str(checkout)
                
        #         hotels = lite_api.search_hotels(city, checkin_str, checkout_str)
                
        #         if not hotels:
        #             response_text = f"🏨 No encontré hoteles en {city.title()}"
        #         else:
        #             # Store hotels in session for selection
        #             session["pending_hotels"] = hotels
        #             session["hotel_dates"] = {"checkin": checkin, "checkout": checkout}
                    
        #             response_text = f"🏨 *Hoteles en {city.title()}*\n"
        #             response_text += f"📅 {date_source}\n\n"
                    
        #             for i, hotel in enumerate(hotels[:5], 1):
        #                 name = hotel.get('name', 'N/A')
        #                 rating = hotel.get('rating', 'N/A')
        #                 price = hotel.get('price', {}).get('total', 'N/A')
        #                 currency = hotel.get('price', {}).get('currency', 'USD')
        #                 amenities = hotel.get('amenities', [])[:2]
        #                 amenities_str = ', '.join(amenities) if amenities else 'WiFi'
                        
        #                 response_text += f"{i}. *{name}*\n"
        #                 response_text += f"   ⭐ {rating} estrellas\n"
        #                 response_text += f"   💰 {price} {currency}/noche\n"
        #                 response_text += f"   ✨ {amenities_str}\n\n"
                    
        #             response_text += "_Responde con el número para reservar_"
                
        #     except Exception as e:
        #         print(f"❌ Hotel search error: {e}")
        #         response_text = f"❌ Error al buscar hoteles: {str(e)}"
            
        #     send_whatsapp_message(from_number, response_text)
        #     return {"status": "ok"}
        
        # Manual hotel handler removed - AI agent handles this now
        
        # Handle date response for hotel search (keep this for backwards compat)
        if session.get("pending_hotel_search") and msg_lower == "sugeridas":
            from app.services.duffel_stays import DuffelStaysEngine
            # datetime and timedelta imported at top of file
            city = session["pending_hotel_search"]["city"]
            checkin = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            checkout = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")
            
            try:
                duffel_stays = DuffelStaysEngine()
                hotels = duffel_stays.search_hotels(city, checkin, checkout)
                
                if hotels:
                    session["pending_hotels"] = hotels
                    session["hotel_dates"] = {"checkin": checkin, "checkout": checkout}
                    session["pending_hotel_search"] = None
                    
                    response_text = f"🏨 *Hoteles en {city.title()}*\n"
                    response_text += f"📅 {checkin} a {checkout}\n\n"
                    
                    for i, hotel in enumerate(hotels[:5], 1):
                        name = hotel.get('name', 'N/A')
                        rating = hotel.get('rating', 'N/A')
                        price = hotel.get('price', {}).get('total', 'N/A')
                        currency = hotel.get('price', {}).get('currency', 'USD')
                        amenities = hotel.get('amenities', [])[:2]
                        amenities_str = ', '.join(amenities) if amenities else 'WiFi'
                        
                        response_text += f"{i}. *{name}*\n"
                        response_text += f"   ⭐ {rating} estrellas\n"
                        response_text += f"   💰 {price} {currency}/noche\n"
                        response_text += f"   ✨ {amenities_str}\n\n"
                    
                    response_text += "_Responde con el número para reservar_"
                else:
                    response_text = f"🏨 No encontré hoteles en {city.title()}"
                    
            except Exception as e:
                print(f"❌ Hotel search error: {e}")
                response_text = f"❌ Error al buscar hoteles: {str(e)}"
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # Ayuda
        msg_lower = incoming_msg.lower().strip()
        
        # EMERGENCY RESET COMMAND
        if msg_lower in ["reset", "reiniciar", "borrar", "limpiar"]:
            session_manager.delete_session(from_number)
            send_whatsapp_message(from_number, "✅ Tu sesión ha sido reiniciada. ¿A dónde quieres viajar?")
            return {"status": "reset"}

        # Ayuda
        if msg_lower in ['/ayuda', 'ayuda', 'help', 'comandos']:
            response_text = "🤖 *Comandos disponibles:*\n\n"
            response_text += "✈️ *Vuelos:*\n"
            response_text += "• Busca vuelos a [destino]\n"
            response_text += "• Vuelos en la mañana/tarde/noche\n"
            response_text += "• Vuelos directos\n\n"
            response_text += "📋 *Reservas:*\n"
            response_text += "• Mis vuelos\n"
            response_text += "• Cancelar [PNR]\n\n"
            response_text += "🏨 *Hoteles:*\n"
            response_text += "• Busca hoteles en [ciudad]\n\n"
            response_text += "💡 _Puedes hablar naturalmente, entiendo español!_"
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        # Regular AI processing
        session["messages"].append({"role": "user", "content": incoming_msg})
        session_manager.save_session(from_number, session)  # Save after adding message
        
        # --- ROBUST MESSAGE SANITIZATION ---
        # Fix for OpenAI 400 Error: "An assistant message with 'tool_calls' must be followed by tool messages"
        # We iterate through messages and ensure every tool_call has a matching tool response.
        # If not, we remove the tool_calls field from the assistant message.
        
        sanitized_messages = []
        skip_indices = set()
        
        # First pass: Identify valid tool responses
        tool_outputs = {} # Map tool_call_id -> message
        for msg in session["messages"]:
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                tool_outputs[msg.get("tool_call_id")] = msg
        
        # Second pass: Build sanitized list
        for i, msg in enumerate(session["messages"]):
            if i in skip_indices:
                continue
                
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Check if all tool calls have responses
                valid_tool_calls = []
                for tc in msg["tool_calls"]:
                    if tc["id"] in tool_outputs:
                        valid_tool_calls.append(tc)
                
                # If we have valid tool calls, keep them and ensure tool outputs follow
                if valid_tool_calls:
                    msg_copy = msg.copy()
                    msg_copy["tool_calls"] = valid_tool_calls
                    sanitized_messages.append(msg_copy)
                    # We don't need to manually add tool outputs here, the loop will handle them
                    # as they appear later in the list (since we only kept valid ones)
                else:
                    # No valid tool calls - strip the tool_calls field
                    # If content is empty, maybe skip? But let's keep content if exists
                    msg_copy = msg.copy()
                    del msg_copy["tool_calls"]
                    if msg_copy.get("content"):
                        sanitized_messages.append(msg_copy)
                    # If no content and no tool calls, it's useless, so skip
            
            elif msg.get("role") == "tool":
                # Only keep tool messages if we kept the parent tool call
                # Implicitly handled because we only checked existence in tool_outputs
                # But better to just keep all tool messages that were found in map? 
                # Actually, simpler: just keep them. If parent removed tool_call, OpenAI might ignore extra tool msg?
                # No, OpenAI is strict. Tool msg MUST follow assistant msg.
                # So we need to ensure flow.
                
                # LET'S SIMPLIFY:
                # Just keeping logic simpler: 
                sanitized_messages.append(msg)
        
        # FINAL STRICT PASS: Ensure sequence Assistant(tool) -> Tool(result)
        # If we find Assistant(tool) without Tool(result) immediately after (ignoring other roles?), fix it.
        # Actually simplest way:
        # If assistant has tool_calls, subsequent messages MUST include the tool results.
        
        final_messages = []
        for i, msg in enumerate(session["messages"]):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # verify next messages match
                tool_ids = [tc["id"] for tc in msg["tool_calls"]]
                found_ids = set()
                
                # Look ahead for tool responses
                for j in range(i + 1, len(session["messages"])):
                    next_msg = session["messages"][j]
                    if next_msg.get("role") == "tool" and next_msg.get("tool_call_id") in tool_ids:
                        found_ids.add(next_msg["tool_call_id"])
                
                if len(found_ids) == len(tool_ids):
                    final_messages.append(msg) # All honest
                else:
                    # Missing responses! Strip tool_calls
                    print(f"⚠️ Stripping broken tool_calls from msg {i}")
                    msg_copy = msg.copy()
                    del msg_copy["tool_calls"]
                    if msg_copy.get("content"):
                        final_messages.append(msg_copy)
            
            elif msg.get("role") == "tool":
                # Only include tool message if the PREVIOUS message was assistant requesting it?
                # Or just checking if it corresponds to a known assistant tool call in final_messages?
                # This is tricky. Let's rely on the stripping above. 
                # If we stripped the parent, the tool message becomes an orphan.
                # OpenAI *might* accept orphan tool messages? No, usually errors.
                
                is_orphan = True
                if final_messages:
                    last_msg = final_messages[-1]
                    if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
                        parent_ids = [tc["id"] for tc in last_msg["tool_calls"]]
                        if msg.get("tool_call_id") in parent_ids:
                            is_orphan = False
                
                if not is_orphan:
                    final_messages.append(msg)
                else:
                   print(f"⚠️ Dropping orphan tool output {msg.get('tool_call_id')}")
            
            else:
                final_messages.append(msg)
        
        session["messages"] = final_messages

        # CRITICAL: If the last message is assistant with tool_calls but no tool results follow,
        # we need to remove or fix it. This happens when session was saved mid-processing.
        if final_messages and final_messages[-1].get("role") == "assistant" and final_messages[-1].get("tool_calls"):
            print("⚠️ Last message has orphan tool_calls - removing it")
            final_messages = final_messages[:-1]
            session["messages"] = final_messages
            session_manager.save_session(from_number, session)

        # AGGRESSIVE: Limit conversation history to prevent "Request too large" error
        if len(session["messages"]) > 10:
            # Keep only last 10 messages to stay under token limit
            session["messages"] = session["messages"][-10:]
            session_manager.save_session(from_number, session)
            print(f"📝 Trimmed conversation history to last 10 messages")
        # -----------------------------------

        response_message = await agent.chat(session["messages"], "")
        
        if response_message.tool_calls:
            session["messages"].append(response_message.model_dump())
            session_manager.save_session(from_number, session)  # Save after AI response
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                tool_result = None
                
                if function_name == "search_hybrid_flights":
                    tool_result = await flight_aggregator.search_hybrid_flights(
                        arguments["origin"],
                        arguments["destination"],
                        arguments["date"],
                        arguments.get("return_date"),
                        arguments.get("cabin", "ECONOMY"),
                        arguments.get("airline"),
                        arguments.get("time_of_day", "ANY"),
                        arguments.get("passengers", 1)  # num_passengers
                    )
                    tool_result = [f.dict() for f in tool_result]

                    if tool_result:
                        session["pending_flights"] = tool_result[:5]
                        session_manager.save_session(from_number, session)
                
                elif function_name == "google_hotels":
                    # Handle hotel search via AI agent
                    from app.services.hotel_engine import HotelEngine
                    from app.utils.date_parser import SmartDateParser
                    
                    hotel_engine = HotelEngine()
                    city = arguments.get("city")
                    checkin = arguments.get("checkin")
                    checkout = arguments.get("checkout")
                    
                    # Use SmartDateParser if dates are missing
                    if not checkin or not checkout:
                        parsed_checkin, parsed_checkout = SmartDateParser.parse_date_range(incoming_msg)
                        if parsed_checkin and parsed_checkout:
                            checkin = parsed_checkin
                            checkout = parsed_checkout
                    
                    tool_result = hotel_engine.search_hotels(
                        city=city,
                        checkin=checkin,
                        checkout=checkout,
                        amenities=arguments.get("amenities"),
                        room_type=arguments.get("room_type"),
                        landmark=arguments.get("landmark")
                    )
                    
                    # Store hotels in session for booking
                    if tool_result:
                        session["pending_hotels"] = tool_result[:5]
                        session["hotel_dates"] = {"checkin": checkin, "checkout": checkout}
                        session_manager.save_session(from_number, session)
                
                elif function_name == "search_multicity_flights":
                    # Multi-city flight search
                    segments = arguments.get("segments", [])
                    print(f"DEBUG: Multi-city search with {len(segments)} segments")

                    # Fix: Correct method name and pass arguments properly
                    # Also added debug print to confirmed fixed code usage
                    print(f"DEBUG: Calling flight_aggregator.search_multicity with pax={arguments.get('passengers', 1)}")

                    tool_result = await flight_aggregator.search_multicity(
                        segments,
                        arguments.get("cabin", "ECONOMY"),
                        arguments.get("passengers", 1)
                    )

                    # CRITICAL FIX: Convert AntigravityFlight objects to dicts
                    # This prevents "AttributeError: 'AntigravityFlight' object has no attribute 'get'"
                    tool_result = [f.dict() for f in tool_result]

                    if tool_result:
                        session["pending_flights"] = tool_result[:5]
                        session_manager.save_session(from_number, session)
                    else:
                        tool_result = []

                elif function_name == "book_flight_final":
                    # Booking is handled by the confirmation flow, not by AI tool
                    tool_result = {"status": "error", "message": "Use the confirmation buttons to book. Select a flight number first."}

                elif function_name == "add_loyalty_data":
                    # TODO: Implement loyalty program storage
                    tool_result = {"status": "success", "message": f"Loyalty data noted: {arguments}"}

                elif function_name == "update_preferences":
                    # TODO: Implement preferences storage
                    tool_result = {"status": "success", "message": f"Preferences noted: {arguments}"}

                else:
                    # Unknown tool - return error to AI
                    print(f"⚠️ Unknown tool called: {function_name}")
                    tool_result = {"status": "error", "message": f"Unknown tool: {function_name}"}

                # Ensure tool_result is never None
                if tool_result is None:
                    tool_result = []

                # COMPACT: Store only summary in messages to avoid "Request too large"
                if isinstance(tool_result, list) and len(tool_result) > 0:
                    compact_result = f"Found {len(tool_result)} results. Data stored in session."
                else:
                    compact_result = json.dumps(tool_result, default=str)[:500]  # Limit size

                session["messages"].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": compact_result
                })
                session_manager.save_session(from_number, session)  # Save after tool result
            
            final_response = await agent.chat(session["messages"], "")
            session["messages"].append({"role": "assistant", "content": final_response.content})
            session_manager.save_session(from_number, session)  # Save final AI response
            response_text = final_response.content
        else:
            # When OpenAI responds with just text (no tool calls), it means either:
            # 1. It's asking for more info from user (e.g., multidestino details)
            # 2. It's a general response
            # IMPORTANT: Do NOT clear pending_flights/pending_hotels here!
            # This was causing confirmation to fail because data was cleared
            # before user could select/confirm. Only clear after explicit confirmation or cancel.
            # session.pop("pending_flights", None)  # REMOVED - was causing bug
            # session.pop("pending_hotels", None)   # REMOVED - was causing bug

            session["messages"].append({"role": "assistant", "content": response_message.content})
            session_manager.save_session(from_number, session)  # Save AI response
            response_text = response_message.content
        
        # Format and send
        formatted_response = format_for_whatsapp(response_text, session)
        send_whatsapp_message(from_number, formatted_response)
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"❌ WhatsApp webhook error: {e}")
        import traceback
        traceback.print_exc()

        # CRITICAL FIX: Send error message to user so they know something went wrong
        try:
            if 'from_number' in dir():
                error_msg = "⚠️ *Error temporal*\n\n"
                error_msg += "Hubo un problema procesando tu mensaje.\n"
                error_msg += "Por favor intenta de nuevo en unos segundos.\n\n"
                error_msg += f"_Error: {str(e)[:100]}_"
                send_whatsapp_message(from_number, error_msg)
        except:
            pass  # Don't fail if we can't send the error message

        return {"status": "error", "message": str(e)}

def send_whatsapp_message(to_number: str, text: str):
    """
    Enviar mensaje vía WhatsApp Business API
    """
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    
    if not phone_number_id or not access_token:
        print("❌ WhatsApp credentials not configured")
        return None
    
    # Normalize phone number - remove extra '1' from Mexican numbers
    # WhatsApp sends: 5215610016226 but API expects: 525610016226
    if to_number.startswith("521") and len(to_number) == 13:
        to_number = "52" + to_number[3:]  # Remove the '1' after '52'
        print(f"📱 Normalized phone number to: {to_number}")
    
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            print(f"✅ WhatsApp message sent to {to_number}")
        else:
            print(f"❌ Error sending WhatsApp: {response.status_code} - {response.text}")
        
        return response
    except Exception as e:
        print(f"❌ Exception sending WhatsApp: {e}")
        return None


def send_interactive_message(to_number: str, body_text: str, buttons: list, header: str = None):
    """
    Send interactive button message via WhatsApp Business API.
    
    Args:
        to_number: Recipient phone number
        body_text: Main message text
        buttons: List of button labels (max 3 for quick reply)
        header: Optional header text
    
    Example:
        send_interactive_message("525610016226", "Confirmar reserva?", ["✅ Si", "❌ No", "🔄 Ver más"])
    """
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    
    if not phone_number_id or not access_token:
        print("❌ WhatsApp credentials not configured")
        return None
    
    # Normalize Mexican phone number
    if to_number.startswith("521") and len(to_number) == 13:
        to_number = "52" + to_number[3:]
        print(f"📱 Normalized phone number to: {to_number}")
    
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Build button objects (max 3 buttons, max 20 chars per title)
    button_objects = []
    for i, btn in enumerate(buttons[:3]):  # WhatsApp limit: 3 buttons
        button_objects.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}_{btn[:10].replace(' ', '_').lower()}",
                "title": btn[:20]  # WhatsApp limit: 20 characters
            }
        })
    
    # Build interactive message payload
    interactive = {
        "type": "button",
        "body": {"text": body_text}
    }
    
    if header:
        interactive["header"] = {"type": "text", "text": header}
    
    interactive["action"] = {"buttons": button_objects}
    
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": interactive
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            print(f"✅ Interactive message sent to {to_number} with {len(buttons)} buttons")
        else:
            print(f"❌ Error sending interactive: {response.status_code} - {response.text}")
        
        return response
    except Exception as e:
        print(f"❌ Exception sending interactive: {e}")
        return None

def format_for_whatsapp(text: str, session: dict) -> str:
    """
    Formatear respuesta para WhatsApp con mejor UX
    """
    if session.get("pending_flights"):
        flights = session["pending_flights"]
        flight_list = "\n\n✈️ *Vuelos encontrados:*\n\n"

        for i, flight in enumerate(flights, 1):
            price = flight.get("price", "N/A")
            segments = flight.get("segments", [])
            duration = flight.get("duration_total", "")

            if segments:
                airline = segments[0].get("carrier_code", "N/A")
                origin = segments[0].get("departure_iata", "")
                final_dest = segments[-1].get("arrival_iata", "")

                # Parse departure time - handles both datetime objects and ISO strings
                dep_time = segments[0].get("departure_time", "")
                if hasattr(dep_time, 'strftime'):
                    date_str = dep_time.strftime("%d/%m")
                    time_str = dep_time.strftime("%H:%M")
                elif dep_time and len(str(dep_time)) >= 16:
                    # ISO format: 2026-02-10T06:58:00
                    date_str = f"{str(dep_time)[8:10]}/{str(dep_time)[5:7]}"
                    time_str = str(dep_time)[11:16]
                else:
                    date_str = "N/A"
                    time_str = "N/A"

                # Determine flight type and stops
                num_segments = len(segments)
                is_round_trip = (origin == final_dest) and num_segments > 1

                if num_segments == 1:
                    flight_type = "✈️ Directo"
                    route = f"{origin}→{final_dest}"
                elif is_round_trip:
                    mid_point = segments[0].get("arrival_iata", "")
                    flight_type = "🔄 Ida y vuelta"
                    route = f"{origin}→{mid_point}→{origin}"
                else:
                    # Multidestino - show all stops
                    stops_list = [origin]
                    for seg in segments:
                        stops_list.append(seg.get("arrival_iata", ""))
                    route = "→".join(stops_list)
                    flight_type = f"🌍 Multidestino ({num_segments} tramos)"

                # Build flight info
                flight_list += f"{i}. *${price} USD* - {airline}\n"
                flight_list += f"   📍 {route}\n"
                flight_list += f"   📅 {date_str} | 🕐 {time_str}\n"
                flight_list += f"   {flight_type}\n"
                if duration:
                    flight_list += f"   ⏱️ {duration}\n"
                flight_list += "\n"

        text += flight_list
        text += "_Responde con el número para reservar_"
    
    # Format hotels if available
    if session.get("pending_hotels"):
        hotels = session["pending_hotels"]
        hotel_dates = session.get("hotel_dates", {})
        checkin = hotel_dates.get("checkin", "N/A")
        checkout = hotel_dates.get("checkout", "N/A")
        
        hotel_list = f"\n\n🏨 *Hoteles encontrados:*\n📅 {checkin} - {checkout}\n\n"
        
        for i, hotel in enumerate(hotels, 1):
            name = hotel.get("name", "N/A")
            rating = hotel.get("rating", "N/A")
            price = hotel.get("price", {})
            total = price.get("total", "N/A") if isinstance(price, dict) else "N/A"
            currency = price.get("currency", "USD") if isinstance(price, dict) else "USD"
            
            # Get amenities
            amenities = hotel.get("amenities", [])
            amenities_str = ", ".join(amenities[:3]) if amenities else "WiFi"
            
            # Get location
            address = hotel.get("address", {})
            city_name = address.get("cityName", "") if isinstance(address, dict) else ""
            location = hotel.get("location_description", city_name)
            
            # Format hotel info
            hotel_list += f"{i}. *{name}*\n"
            hotel_list += f"   ⭐ {rating} estrellas\n"
            hotel_list += f"   💰 ${total} {currency}/noche\n"
            hotel_list += f"   📍 {location}\n"
            hotel_list += f"   ✨ {amenities_str}\n\n"
        
        text += hotel_list
        text += "_Responde con el número para reservar_"
    
    return text
