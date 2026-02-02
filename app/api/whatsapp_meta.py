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
import re

router = APIRouter()

def parse_iso_duration(duration_str: str) -> str:
    """Convert ISO 8601 duration (PT15H39M) to readable format (15h 39m)"""
    if not duration_str:
        return ""

    # Already readable format (has 'h' but not ISO format)
    if 'h' in duration_str.lower() and 'P' not in duration_str:
        return duration_str

    # Parse ISO 8601 duration: P1DT12H30M or PT15H39M
    # Format: P[days]D[T[hours]H[minutes]M]
    match = re.match(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?', duration_str)
    if match:
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")

        return " ".join(parts) if parts else duration_str

    return duration_str
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
            print(f"🔍 DEBUG interactive object: {interactive}")
            interactive_type = interactive.get("type", "")
            print(f"🔍 DEBUG interactive_type: {interactive_type}")
            button_reply = interactive.get("button_reply", {})
            button_id = button_reply.get("id", "")
            button_title = button_reply.get("title", "")
            
            print(f"📱 Button click from {from_number}: {button_title} (id: {button_id})")
            print(f"📱 DEBUG button_title.lower() = '{button_title.lower()}'")

            # Map button clicks to text commands
            if "confirmar" in button_title.lower() or "✅" in button_title:
                incoming_msg = "si"  # Treat as confirmation
            elif "cancelar" in button_title.lower() or "❌" in button_title:
                incoming_msg = "no"  # Treat as cancellation
            elif "buscar" in button_title.lower() or "🔄" in button_title:
                incoming_msg = "buscar otro"
            elif "auto check-in" in button_title.lower() or "auto checkin" in button_title.lower() or "avisarme" in button_title.lower():
                incoming_msg = "auto checkin"
            elif "check-in" in button_title.lower() or "checkin" in button_title.lower():
                incoming_msg = "checkin"
            elif "equipaje" in button_title.lower() or "maleta" in button_title.lower():
                incoming_msg = "equipaje"
            elif "itinerario" in button_title.lower():
                incoming_msg = "itinerario"
            elif "ayuda" in button_title.lower():
                incoming_msg = "ayuda"
            elif "buscar vuelo" in button_title.lower():
                incoming_msg = "quiero buscar un vuelo"
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

        # DEBUG: Log session state for confirmation debugging
        print(f"🔍 DEBUG Session loaded for {from_number}:")
        print(f"   - selected_hotel: {bool(session.get('selected_hotel'))}")
        print(f"   - selected_flight: {bool(session.get('selected_flight'))}")
        print(f"   - pending_hotels: {len(session.get('pending_hotels', []))}")
        print(f"   - pending_flights: {len(session.get('pending_flights', []))}")
        print(f"   - incoming_msg: {incoming_msg[:50] if incoming_msg else 'None'}...")

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
            help_text = """*Biatriz - Tu Asistente de Viajes* ✈️

*BUSCAR Y RESERVAR*
• vuelo MEX a MAD 15 marzo
• hotel en Madrid del 15 al 18
• reservar sin pagar _(apartar 24h)_

*MIS VIAJES*
• itinerario _(próximo viaje)_
• historial _(viajes pasados)_
• cancelar [PNR]
• reembolso

*EXTRAS DE VUELO*
• equipaje _(agregar maletas)_
• asientos _(elegir lugar)_
• servicios _(comidas, WiFi)_
• checkin / auto checkin

*MILLAS Y ALERTAS*
• millas _(ver programas)_
• agregar millas AM 123456
• eliminar millas AM
• alertas _(ver alertas precio)_
• crear alerta _(después de buscar)_

*UTILIDADES*
• clima cancun
• cambio USD
• estado vuelo AM123
• visa US _(requisitos)_

*MI CUENTA*
• perfil _(ver preferencias)_
• reset _(limpiar sesión)_

_Escribe lo que necesitas en lenguaje natural_ 😊"""
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
                response_text += "\n"

                # Show all segments with proper labels
                for idx, seg in enumerate(segments, 1):
                    seg_origin = seg.get("departure_iata", "")
                    seg_dest = seg.get("arrival_iata", "")
                    dep_time = seg.get("departure_time", "")
                    arr_time = seg.get("arrival_time", "")
                    seg_duration = seg.get("duration", "")
                    seg_airline = seg.get("carrier_code", "N/A")
                    seg_flight_num = seg.get("flight_number", "")

                    # Format departure time
                    dep_str = "N/A"
                    if dep_time:
                        dep_str_raw = str(dep_time)
                        if "T" in dep_str_raw and len(dep_str_raw) >= 16:
                            # ISO format: 2026-02-10T06:58:00
                            dep_str = f"{dep_str_raw[8:10]}/{dep_str_raw[5:7]} {dep_str_raw[11:16]}"
                        elif hasattr(dep_time, 'strftime'):
                            dep_str = dep_time.strftime("%d/%m %H:%M")
                        elif len(dep_str_raw) >= 10:
                            # Format: 2026-02-10 06:58 -> 10/02 06:58
                            dep_str = f"{dep_str_raw[8:10]}/{dep_str_raw[5:7]} {dep_str_raw[11:16]}" if len(dep_str_raw) >= 16 else f"{dep_str_raw[8:10]}/{dep_str_raw[5:7]}"

                    # Format arrival time
                    arr_str = "N/A"
                    if arr_time:
                        arr_str_raw = str(arr_time)
                        if "T" in arr_str_raw and len(arr_str_raw) >= 16:
                            arr_str = f"{arr_str_raw[8:10]}/{arr_str_raw[5:7]} {arr_str_raw[11:16]}"
                        elif hasattr(arr_time, 'strftime'):
                            arr_str = arr_time.strftime("%d/%m %H:%M")
                        elif len(arr_str_raw) >= 10:
                            # Format: 2026-02-10 06:58 -> 10/02 06:58
                            arr_str = f"{arr_str_raw[8:10]}/{arr_str_raw[5:7]} {arr_str_raw[11:16]}" if len(arr_str_raw) >= 16 else f"{arr_str_raw[8:10]}/{arr_str_raw[5:7]}"

                    # Label based on flight type
                    if is_direct:
                        label = "Vuelo"
                    elif is_round_trip:
                        label = "Ida" if idx == 1 else "Regreso"
                    else:
                        label = f"Tramo {idx}"

                    # Flight info line with airline and flight number
                    flight_info = f"{seg_airline}"
                    if seg_flight_num:
                        flight_info += f" {seg_flight_num}"

                    # Parse duration to readable format
                    readable_duration = parse_iso_duration(seg_duration)

                    response_text += f"*{label}:* {seg_origin} → {seg_dest}\n"
                    response_text += f"   ✈️ {flight_info}\n"
                    response_text += f"   🛫 {dep_str} → 🛬 {arr_str}\n"
                    if readable_duration:
                        response_text += f"   ⏱️ Duración: {readable_duration}\n"
                    response_text += "\n"

                # Calculate total duration by summing all segments
                total_minutes = 0
                for seg in segments:
                    seg_dur = seg.get("duration", "")
                    if seg_dur:
                        match = re.match(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?', seg_dur)
                        if match:
                            days = int(match.group(1) or 0)
                            hours = int(match.group(2) or 0)
                            mins = int(match.group(3) or 0)
                            total_minutes += days * 24 * 60 + hours * 60 + mins

                if total_minutes > 0:
                    total_hours = total_minutes // 60
                    remaining_mins = total_minutes % 60
                    if total_hours >= 24:
                        days = total_hours // 24
                        hours = total_hours % 24
                        response_text += f"📊 *Duración total:* {days}d {hours}h {remaining_mins}m\n"
                    else:
                        response_text += f"📊 *Duración total:* {total_hours}h {remaining_mins}m\n"

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
                # Handle both price structures: {price: {total, currency}} or {price_total, currency}
                price_obj = selected.get("price", {})
                if isinstance(price_obj, dict):
                    price = price_obj.get("total", "N/A")
                    currency = price_obj.get("currency", "USD")
                else:
                    price = selected.get("price_total", "N/A")
                    currency = selected.get("currency", "USD")
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

            # Handle case where nothing is selected (session lost due to no Redis)
            if not session.get("selected_flight") and not session.get("selected_hotel"):
                response_text = "⚠️ *Sesión expirada*\n\n"
                response_text += "No encontré tu selección.\n"
                response_text += "Por favor busca de nuevo tu vuelo u hotel.\n\n"
                response_text += "_Escribe 'ayuda' para ver los comandos_"
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}

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

            
            offer_id = flight_dict.get("offer_id")  # Fixed: was "id", should be "offer_id"
            provider = flight_dict.get("provider", "duffel")
            price = flight_dict.get("price", "0.00")

            print(f"🔍 DEBUG booking: offer_id={offer_id}, provider={provider}, price={price}")
            
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

                    response_text = f"✅ *¡Vuelo reservado!*\n\n"
                    response_text += f"📝 *PNR:* {pnr}\n"
                    response_text += f"💰 *Total:* ${price}\n\n"

                    # Show details for each segment
                    total_minutes = 0
                    for idx, seg in enumerate(segments, 1):
                        seg_origin = seg.get("departure_iata", "?")
                        seg_dest = seg.get("arrival_iata", "?")
                        seg_airline = seg.get("carrier_code", "N/A")
                        seg_flight_num = seg.get("flight_number", "")
                        seg_duration = seg.get("duration", "")
                        dep_time = seg.get("departure_time", "")
                        arr_time = seg.get("arrival_time", "")

                        # Format times
                        dep_str = "N/A"
                        if dep_time:
                            dep_raw = str(dep_time)
                            if len(dep_raw) >= 16:
                                dep_str = f"{dep_raw[8:10]}/{dep_raw[5:7]} {dep_raw[11:16]}"

                        arr_str = "N/A"
                        if arr_time:
                            arr_raw = str(arr_time)
                            if len(arr_raw) >= 16:
                                arr_str = f"{arr_raw[8:10]}/{arr_raw[5:7]} {arr_raw[11:16]}"

                        # Flight ID
                        flight_id = seg_airline
                        if seg_flight_num:
                            flight_id += f" {seg_flight_num}"

                        # Parse duration
                        readable_dur = parse_iso_duration(seg_duration)
                        if seg_duration:
                            match = re.match(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?', seg_duration)
                            if match:
                                days = int(match.group(1) or 0)
                                hours = int(match.group(2) or 0)
                                mins = int(match.group(3) or 0)
                                total_minutes += days * 24 * 60 + hours * 60 + mins

                        # Segment label
                        if len(segments) == 1:
                            label = "✈️ Vuelo"
                        else:
                            label = f"✈️ Tramo {idx}"

                        response_text += f"*{label}:* {seg_origin}→{seg_dest}\n"
                        response_text += f"   {flight_id}\n"
                        response_text += f"   🛫 {dep_str} → 🛬 {arr_str}\n"
                        if readable_dur:
                            response_text += f"   ⏱️ {readable_dur}\n"
                        response_text += "\n"

                    # Total duration
                    if total_minutes > 0:
                        total_hours = total_minutes // 60
                        remaining_mins = total_minutes % 60
                        if total_hours >= 24:
                            days = total_hours // 24
                            hours = total_hours % 24
                            response_text += f"📊 *Duración total:* {days}d {hours}h {remaining_mins}m\n\n"
                        else:
                            response_text += f"📊 *Duración total:* {total_hours}h {remaining_mins}m\n\n"

                    response_text += f"✨ *Reserva confirmada*"

                    # SAVE TRIP TO DATABASE for mock bookings
                    from app.models.models import Trip, TripStatusEnum, ProviderSourceEnum
                    from datetime import datetime as dt

                    # Extract departure info from first segment
                    dep_city = segments[0].get("departure_iata") if segments else None
                    arr_city = segments[-1].get("arrival_iata") if segments else None
                    dep_date = None
                    if segments and segments[0].get("departure_time"):
                        try:
                            dep_str = segments[0]["departure_time"]
                            dep_date = dt.fromisoformat(dep_str.replace("Z", "+00:00")).date()
                        except:
                            pass

                    trip = Trip(
                        booking_reference=pnr,
                        user_id=session["user_id"],
                        provider_source=ProviderSourceEnum.DUFFEL,
                        total_amount=float(price) if price else 0,
                        status=TripStatusEnum.TICKETED,
                        departure_city=dep_city,
                        arrival_city=arr_city,
                        departure_date=dep_date,
                        confirmed_at=dt.utcnow().isoformat()
                    )
                    db.add(trip)
                    db.commit()
                    print(f"✅ Mock trip saved to DB: {pnr}")

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

        # Handle Cancel button click (when there's a selected flight or hotel)
        if msg_lower == 'no' and (session.get("selected_flight") or session.get("selected_hotel")):
            # Clear selections
            session.pop("selected_flight", None)
            session.pop("selected_hotel", None)
            session_manager.save_session(from_number, session)

            response_text = "❌ *Reserva cancelada*\n\n"
            response_text += "Puedes buscar otro vuelo u hotel cuando quieras."

            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}

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

        # Ayuda (handled above, this is a fallback)
        # Already handled at top of function

        # ===== NEW FEATURE COMMANDS =====
        # IMPORTANT: Skip these handlers if user is in the middle of a hotel/flight search
        # This allows the AI to handle context-aware conversations
        has_pending_search = session.get("pending_hotel_search") or session.get("pending_flights") or session.get("pending_hotels")

        # EQUIPAJE / BAGGAGE - Only if explicit standalone command
        print(f"🧳 DEBUG checking equipaje: msg_lower='{msg_lower}', contains equipaje: {'equipaje' in msg_lower}")
        is_equipaje_command = msg_lower.strip() in ['equipaje', 'maletas', 'baggage', 'maleta', 'mi equipaje']
        if is_equipaje_command and not has_pending_search:
            from app.services.baggage_service import BaggageService
            from app.services.itinerary_service import ItineraryService

            baggage_service = BaggageService(db)
            itinerary_service = ItineraryService(db)

            user_id = session.get("user_id", f"whatsapp_{from_number}")
            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming and upcoming.get("success"):
                pnr = upcoming.get("booking_reference")
                baggage_data = baggage_service.get_trip_baggage(pnr)
                response = baggage_service.format_baggage_for_whatsapp(baggage_data)
                buttons = baggage_service.format_baggage_buttons(baggage_data)
                send_interactive_message(from_number, response, [b["title"] for b in buttons])
            else:
                send_whatsapp_message(from_number, "No tienes viajes proximos.\n\nBusca un vuelo para ver opciones de equipaje.")

            return {"status": "ok"}

        # CHECK-IN (but NOT if user is providing hotel dates or in middle of search)
        # Skip if message contains both "check in" and "check out" (hotel dates)
        # Skip if message contains numbers (likely dates like "check in 17")
        # Skip if there's a pending hotel/flight search
        is_checkin_command = msg_lower.strip() in ['checkin', 'check-in', 'registrarme', 'mi checkin']
        has_checkout = 'check out' in msg_lower or 'checkout' in msg_lower
        has_numbers = any(char.isdigit() for char in incoming_msg)
        is_hotel_dates = ('check in' in msg_lower and (has_checkout or has_numbers))

        if is_checkin_command and not has_pending_search and not is_hotel_dates:
            from app.services.checkin_service import CheckinService
            from app.services.itinerary_service import ItineraryService

            checkin_service = CheckinService(db)
            itinerary_service = ItineraryService(db)

            user_id = session.get("user_id", f"whatsapp_{from_number}")
            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming and upcoming.get("success"):
                pnr = upcoming.get("booking_reference")
                status = checkin_service.get_checkin_status(pnr)
                response = checkin_service.format_status_for_whatsapp(status)
                buttons = checkin_service.format_checkin_buttons(status)
                send_interactive_message(from_number, response, [b["title"] for b in buttons])
            else:
                send_whatsapp_message(from_number, "No tienes viajes proximos.\n\nBusca un vuelo primero.")

            return {"status": "ok"}

        # Auto check-in activation (actually a reminder with check-in link)
        if 'auto checkin' in msg_lower or 'autocheckin' in msg_lower:
            from app.services.checkin_service import CheckinService
            from app.services.itinerary_service import ItineraryService

            checkin_service = CheckinService(db)
            itinerary_service = ItineraryService(db)

            user_id = session.get("user_id", f"whatsapp_{from_number}")
            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming and upcoming.get("success"):
                pnr = upcoming.get("booking_reference")
                # Get passenger info from profile
                profile = db.query(Profile).filter(Profile.user_id == user_id).first()

                if profile:
                    result = checkin_service.schedule_auto_checkin(
                        user_id=user_id,
                        trip_id=pnr,
                        airline_code="AM",  # Would need to get from trip
                        pnr=pnr,
                        passenger_last_name=profile.legal_last_name,
                        departure_time=upcoming.get("flight", {}).get("departure_date", "")
                    )

                    if result.get("success"):
                        response = f"*Recordatorio de check-in activado*\n\n"
                        response += f"PNR: {pnr}\n"
                        response += f"Te aviso: {result.get('message', '24h antes')}\n\n"
                        response += "Te enviare el link de check-in de la aerolinea cuando se abra."
                    else:
                        response = f"No pude activar recordatorio: {result.get('error')}"
                else:
                    response = "Necesito tu perfil para activar el recordatorio. Escribe 'mi perfil'."
            else:
                response = "No tienes viajes proximos."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # ITINERARIO / MY TRIP
        if any(kw in msg_lower for kw in ['itinerario', 'mi viaje', 'mi reserva', 'mi vuelo']):
            from app.services.itinerary_service import ItineraryService

            itinerary_service = ItineraryService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming:
                response = itinerary_service.format_itinerary_for_whatsapp(upcoming)
                buttons = itinerary_service.format_itinerary_buttons(upcoming)
                send_interactive_message(from_number, response, [b["title"] for b in buttons])
            else:
                send_whatsapp_message(from_number, "No tienes viajes proximos.\n\nBusca un vuelo para comenzar.")

            return {"status": "ok"}

        # HISTORIAL / TRAVEL HISTORY
        if any(kw in msg_lower for kw in ['historial', 'mis viajes', 'history', 'viajes pasados']):
            from app.services.itinerary_service import ItineraryService

            itinerary_service = ItineraryService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            trips = itinerary_service.get_user_itineraries(user_id, include_past=True)

            if trips:
                response = "*Tu historial de viajes*\n\n"
                for i, trip in enumerate(trips[:10], 1):
                    status_icon = {"TICKETED": "", "CONFIRMED": "", "CANCELLED": ""}.get(trip.get("status", ""), "")
                    response += f"{i}. {trip['route']}\n"
                    response += f"   {trip.get('departure_date', 'N/A')} {status_icon}\n"
                    response += f"   PNR: {trip['booking_reference']}\n\n"

                if len(trips) > 10:
                    response += f"...y {len(trips) - 10} viajes mas."

                # Buttons for history
                buttons = ["Buscar vuelo", "Ayuda"]
                send_interactive_message(from_number, response, buttons)
            else:
                send_whatsapp_message(from_number, "No tienes viajes en tu historial.\n\nBusca un vuelo para comenzar.")

            return {"status": "ok"}

        # VISA
        if any(kw in msg_lower for kw in ['visa', 'necesito visa', 'requisitos visa']):
            from app.services.visa_service import VisaService

            visa_service = VisaService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Try to extract destination from message: "visa MAD" or "visa espana"
            dest_match = re.search(r'visa\s+([A-Za-z]{2,3})', msg_lower)

            if dest_match:
                destination = dest_match.group(1).upper()
                result = visa_service.check_visa_for_user(user_id, destination)
                response = visa_service.format_visa_for_whatsapp(result)
                buttons = visa_service.format_visa_buttons(result)
                send_interactive_message(from_number, response, [b["title"] for b in buttons])
            else:
                response = "*Verificar requisitos de visa*\n\n"
                response += "Escribe: visa [destino]\n\n"
                response += "Ejemplos:\n"
                response += "- visa MAD\n"
                response += "- visa US\n"
                response += "- visa JFK\n\n"
                response += "_Usare tu pasaporte registrado para verificar._"
                send_whatsapp_message(from_number, response)

            return {"status": "ok"}

        # CLIMA / WEATHER
        if any(kw in msg_lower for kw in ['clima', 'weather', 'tiempo en', 'pronóstico']):
            from app.services.weather_service import WeatherService
            import asyncio

            weather_service = WeatherService()

            # Extract city from message
            city_match = re.search(r'(?:clima|weather|tiempo en|pronóstico)\s+(?:en\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ\s]+)', msg_lower)
            city = city_match.group(1).strip() if city_match else None

            # If no city, try to get from recent search or ask
            if not city:
                if session.get("pending_flights"):
                    # Get destination from last flight search
                    city = session["pending_flights"][0].get("arrival_iata", "")
                elif session.get("pending_hotel_search"):
                    city = session["pending_hotel_search"].get("city", "")

            if city:
                weather = await weather_service.get_weather(city)
                response = weather_service.format_for_whatsapp(weather)
            else:
                response = "*Clima*\n\nEscribe: clima [ciudad]\n\nEjemplos:\n- clima cancun\n- clima madrid\n- clima miami"

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # TIPO DE CAMBIO / CURRENCY
        if any(kw in msg_lower for kw in ['cambio', 'tipo de cambio', 'moneda', 'currency', 'dolar', 'euro']):
            from app.services.currency_service import CurrencyService
            import asyncio

            currency_service = CurrencyService()

            # Extract destination from message
            dest_match = re.search(r'(?:cambio|moneda|currency)\s+(?:en|para|a)?\s*([A-Za-záéíóúñ\s]+)', msg_lower)
            destination = dest_match.group(1).strip() if dest_match else None

            # Default currencies
            from_curr = "USD"
            to_curr = "MXN"

            if destination:
                to_curr = currency_service.get_currency_for_destination(destination)
            elif session.get("pending_flights"):
                # Get destination currency from flight search
                dest = session["pending_flights"][0].get("arrival_iata", "")
                to_curr = currency_service.get_currency_for_destination(dest)
                destination = dest

            exchange = await currency_service.get_exchange_rate(from_curr, to_curr)
            response = currency_service.format_for_whatsapp(exchange, destination)
            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # ESTADO DE VUELO / FLIGHT STATUS
        if any(kw in msg_lower for kw in ['estado vuelo', 'flight status', 'rastrear vuelo', 'donde esta mi vuelo', 'estado del vuelo']):
            from app.services.flight_status_service import FlightStatusService

            status_service = FlightStatusService()

            # Extract flight number from message
            flight_match = re.search(r'([A-Za-z]{2}\d{1,4})', incoming_msg)
            flight_number = flight_match.group(1) if flight_match else None

            if not flight_number:
                # Try to get from user's bookings
                from app.services.itinerary_service import ItineraryService
                itinerary_service = ItineraryService(db)
                user_id = session.get("user_id", f"whatsapp_{from_number}")
                upcoming = itinerary_service.get_upcoming_trip(user_id)
                if upcoming and upcoming.get("success"):
                    # Would need to store flight number in trip
                    pass

            if flight_number:
                status = await status_service.get_flight_status(flight_number)
                response = status_service.format_for_whatsapp(status)
            else:
                response = "*Estado de vuelo*\n\nEscribe: estado vuelo [número]\n\nEjemplos:\n- estado vuelo AM123\n- estado vuelo AA100"

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # ALERTAS DE PRECIO
        if msg_lower.strip() in ['alertas', 'mis alertas', 'price alerts', 'alertas de precio']:
            from app.services.price_alert_service import PriceAlertService

            alert_service = PriceAlertService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            alerts = alert_service.get_user_alerts(user_id)
            response = alert_service.format_alerts_for_whatsapp(alerts)
            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # CREAR ALERTA
        if any(kw in msg_lower for kw in ['crear alerta', 'nueva alerta', 'avisame cuando baje', 'alerta de precio']):
            from app.services.price_alert_service import PriceAlertService

            alert_service = PriceAlertService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Check if user has pending flights to create alert for
            if session.get("pending_flights"):
                flight = session["pending_flights"][0]
                result = alert_service.create_alert(
                    user_id=user_id,
                    phone_number=from_number,
                    search_type="flight",
                    origin=flight.get("departure_iata"),
                    destination=flight.get("arrival_iata"),
                    departure_date=flight.get("departure_date", ""),
                    current_price=float(flight.get("total_price", 0))
                )
                if result.get("success"):
                    response = f"✅ Alerta creada!\n\nRuta: {flight.get('departure_iata')} → {flight.get('arrival_iata')}\nPrecio actual: ${flight.get('total_price')}\n\nTe avisaré cuando baje el precio."
                else:
                    response = f"❌ No pude crear la alerta: {result.get('error')}"
            else:
                response = "*Crear alerta de precio*\n\nPrimero busca un vuelo o hotel, luego di 'crear alerta' para recibir notificación cuando baje el precio."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # ASIENTOS / SEAT SELECTION
        if msg_lower.strip() in ['asientos', 'seleccionar asiento', 'mapa de asientos', 'seats']:
            from app.services.seat_selection_service import SeatSelectionService

            seat_service = SeatSelectionService()

            # Check if user has selected a flight
            if session.get("selected_flight"):
                offer_id = session["selected_flight"].get("offer_id")
                if offer_id:
                    seat_map = await seat_service.get_seat_map(offer_id)
                    response = seat_service.format_seat_map_for_whatsapp(seat_map)
                else:
                    response = "No pude obtener el mapa de asientos para este vuelo."
            else:
                response = "*Selección de asiento*\n\nPrimero selecciona un vuelo para ver los asientos disponibles."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # AGREGAR MILLAS - Must come BEFORE generic "millas" handler
        if 'agregar millas' in msg_lower or 'agregar viajero' in msg_lower:
            from app.services.loyalty_service import LoyaltyService

            loyalty_service = LoyaltyService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Parse: "agregar millas AM 123456789"
            parts = incoming_msg.split()
            if len(parts) >= 4:
                airline_code = parts[2].upper()
                member_number = parts[3]

                result = loyalty_service.add_loyalty_number(user_id, airline_code, member_number)
                if result.get("success"):
                    response = f"✅ {result['message']}\n\nPrograma: {result['program']}\nNúmero: {result['number']}"
                else:
                    response = f"❌ Error: {result.get('error')}"
            else:
                response = "Para agregar millas escribe:\n'agregar millas [aerolínea] [número]'\n\nEjemplo: agregar millas AM 123456789"

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # ELIMINAR MILLAS - Must come before generic "millas" handler
        if 'eliminar millas' in msg_lower or 'quitar millas' in msg_lower or 'borrar millas' in msg_lower:
            from app.services.loyalty_service import LoyaltyService

            loyalty_service = LoyaltyService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Parse: "eliminar millas AM"
            parts = incoming_msg.split()
            if len(parts) >= 3:
                airline_code = parts[2].upper()

                result = loyalty_service.delete_loyalty(user_id, airline_code)
                if result.get("success"):
                    response = f"✅ {result['message']}"
                else:
                    response = f"❌ {result.get('error', 'Error al eliminar')}"
            else:
                response = "Para eliminar millas escribe:\n'eliminar millas [aerolínea]'\n\nEjemplo: eliminar millas AM"

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # MILLAS / VIAJERO FRECUENTE / LOYALTY
        if any(kw in msg_lower for kw in ['millas', 'viajero frecuente', 'loyalty', 'mis millas', 'puntos']):
            from app.services.loyalty_service import LoyaltyService

            loyalty_service = LoyaltyService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            programs = loyalty_service.get_user_programs(user_id)
            response = loyalty_service.format_for_whatsapp(programs)
            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # SERVICIOS ADICIONALES / COMIDAS / ANCILLARIES
        if any(kw in msg_lower for kw in ['servicios', 'comidas', 'wifi', 'meals', 'extras', 'agregar servicio']):
            from app.services.ancillary_service import AncillaryService

            ancillary_service = AncillaryService()

            if session.get("selected_flight"):
                offer_id = session["selected_flight"].get("offer_id")
                if offer_id:
                    services = await ancillary_service.get_available_services(offer_id)
                    response = ancillary_service.format_services_for_whatsapp(services)
                else:
                    response = "No pude obtener servicios para este vuelo."
            else:
                response = "*Servicios adicionales*\n\nPrimero selecciona un vuelo para ver servicios disponibles (comidas, WiFi, equipaje extra, etc.)"

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # COTIZAR REEMBOLSO
        if any(kw in msg_lower for kw in ['reembolso', 'refund', 'cuanto me devuelven', 'cotizar cancelacion']):
            from app.services.order_management import OrderManager

            order_manager = OrderManager(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Try to get user's recent trip
            from app.services.itinerary_service import ItineraryService
            itinerary_service = ItineraryService(db)
            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming and upcoming.get("success"):
                trip = db.query(Trip).filter(Trip.booking_reference == upcoming.get("booking_reference")).first()

                if trip and trip.duffel_order_id:
                    try:
                        quote = order_manager.get_cancellation_quote(trip.duffel_order_id)
                        response = f"*Cotización de reembolso*\n\n"
                        response += f"PNR: {trip.booking_reference}\n"
                        response += f"Reembolso: ${quote.get('refund_amount', '0')} {quote.get('refund_currency', 'USD')}\n\n"
                        response += "Para cancelar escribe: 'cancelar " + trip.booking_reference + "'"
                    except Exception as e:
                        response = f"No pude cotizar el reembolso: {str(e)}"
                else:
                    response = "No encontré el ID de la orden para cotizar."
            else:
                response = "No tienes viajes próximos para cotizar reembolso."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # CAMBIAR VUELO
        if any(kw in msg_lower for kw in ['cambiar vuelo', 'cambiar fecha', 'modificar vuelo', 'change flight']):
            from app.services.order_change_service import OrderChangeService

            change_service = OrderChangeService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Get user's trip
            from app.services.itinerary_service import ItineraryService
            itinerary_service = ItineraryService(db)
            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming and upcoming.get("success"):
                response = f"*Cambiar vuelo*\n\n"
                response += f"PNR: {upcoming.get('booking_reference')}\n"
                response += f"Vuelo actual: {upcoming.get('flight', {}).get('route', 'N/A')}\n\n"
                response += "Para cambiar, escribe la nueva fecha:\n"
                response += "'cambiar a [fecha]'\n\n"
                response += "Ejemplo: cambiar a 25 marzo"

                session["pending_change"] = {
                    "pnr": upcoming.get("booking_reference"),
                    "order_id": upcoming.get("duffel_order_id")
                }
                session_manager.save_session(from_number, session)
            else:
                response = "No tienes vuelos próximos para cambiar."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # MIS CRÉDITOS DE AEROLÍNEA
        if any(kw in msg_lower for kw in ['mis creditos', 'creditos', 'vouchers', 'mis vouchers', 'airline credits']):
            from app.services.airline_credits_service import AirlineCreditsService

            credits_service = AirlineCreditsService(db)
            user_id = session.get("user_id", f"whatsapp_{from_number}")

            credits = credits_service.get_user_credits(user_id)

            if credits:
                response = "*Mis créditos de aerolínea*\n\n"
                for c in credits:
                    status = "✅" if c.get('is_valid') else "❌"
                    response += f"{status} *{c.get('airline_iata_code', 'N/A')}* - {c.get('credit_name', '')}\n"
                    response += f"   Monto: ${c.get('credit_amount', 0)} {c.get('credit_currency', 'USD')}\n"
                    if c.get('credit_code'):
                        response += f"   Código: {c['credit_code']}\n"
                    response += f"   Expira: {c.get('expires_at', 'N/A')}\n\n"
            else:
                response = "*Mis créditos de aerolínea*\n\nNo tienes créditos guardados.\n\nLos créditos se generan cuando cancelas un vuelo con reembolso en crédito."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # RESERVAR SIN PAGAR / HOLD
        if any(kw in msg_lower for kw in ['reservar sin pagar', 'hold', 'apartar vuelo', 'guardar vuelo', 'pagar despues']):
            from app.services.hold_order_service import HoldOrderService

            hold_service = HoldOrderService()

            if session.get("selected_flight"):
                offer_id = session["selected_flight"].get("offer_id")
                if offer_id:
                    # Check if hold is available
                    hold_check = await hold_service.check_hold_availability(offer_id)

                    if hold_check.get("available"):
                        response = f"✅ *Este vuelo permite reservar sin pagar*\n\n"
                        response += f"Tienes hasta {hold_check.get('hold_hours', 24)} horas para pagar.\n\n"
                        response += "¿Quieres reservar ahora y pagar después?\n\n"
                        response += "Responde 'confirmar hold' para continuar."

                        session["pending_hold"] = True
                        session_manager.save_session(from_number, session)
                    else:
                        response = f"❌ {hold_check.get('message', 'Este vuelo no permite reservar sin pagar.')}"
                else:
                    response = "No pude verificar el vuelo seleccionado."
            else:
                response = "*Reservar sin pagar*\n\nPrimero selecciona un vuelo para verificar si permite reservar sin pagar."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # ===== END NEW FEATURE COMMANDS =====

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

        # Build session context for AI - include all relevant state
        session_context = {
            "pending_hotel_search": session.get("pending_hotel_search"),
            "pending_flights": bool(session.get("pending_flights")),  # True if flights shown
            "pending_hotels": bool(session.get("pending_hotels")),    # True if hotels shown
            "awaiting_flight_confirmation": session.get("awaiting_flight_confirmation"),
            "awaiting_hotel_confirmation": session.get("awaiting_hotel_confirmation"),
            "last_search_type": session.get("last_search_type"),
            "hotel_dates": session.get("hotel_dates"),
            "selected_flight": bool(session.get("selected_flight")),  # True if flight selected
            "selected_hotel": bool(session.get("selected_hotel")),    # True if hotel selected
        }

        response_message = await agent.chat(session["messages"], "", session_context)
        
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
                        landmark=arguments.get("landmark"),
                        hotel_chain=arguments.get("hotel_chain"),
                        star_rating=arguments.get("star_rating"),
                        location=arguments.get("location")
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
            
            final_response = await agent.chat(session["messages"], "", session_context)
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
            cabin = flight.get("cabin_class", "ECONOMY")
            refundable = flight.get("refundable", False)

            if segments:
                num_segments = len(segments)
                origin = segments[0].get("departure_iata", "")
                final_dest = segments[-1].get("arrival_iata", "")

                # Header with price and refundable status
                refund_tag = "✅ Reembolsable" if refundable else ""
                flight_list += f"━━━━━━━━━━━━━━━━━━━━\n"
                flight_list += f"*{i}. ${price} USD* {refund_tag}\n"

                # Show each segment with full details
                for seg_idx, seg in enumerate(segments):
                    seg_airline = seg.get("carrier_code", "N/A")
                    seg_flight_num = seg.get("flight_number", "")
                    seg_origin = seg.get("departure_iata", "")
                    seg_dest = seg.get("arrival_iata", "")
                    seg_duration = seg.get("duration", "")

                    # Parse departure time
                    dep_time = seg.get("departure_time", "")
                    if hasattr(dep_time, 'strftime'):
                        dep_str = dep_time.strftime("%d/%m %H:%M")
                    elif dep_time and len(str(dep_time)) >= 16:
                        dep_str = f"{str(dep_time)[8:10]}/{str(dep_time)[5:7]} {str(dep_time)[11:16]}"
                    else:
                        dep_str = "N/A"

                    # Parse arrival time
                    arr_time = seg.get("arrival_time", "")
                    if hasattr(arr_time, 'strftime'):
                        arr_str = arr_time.strftime("%H:%M")
                    elif arr_time and len(str(arr_time)) >= 16:
                        arr_str = str(arr_time)[11:16]
                    else:
                        arr_str = "N/A"

                    # Flight identifier (airline + flight number)
                    flight_id = f"{seg_airline}"
                    if seg_flight_num:
                        flight_id += f" {seg_flight_num}"

                    # Detect if round trip (origin == final destination) or multidestino
                    is_round_trip = (origin == final_dest) and num_segments >= 2

                    # Segment label with direct/stops indicator
                    # Each segment is a direct flight leg
                    if num_segments == 1:
                        seg_label = "✈️ DIRECTO"
                        flight_list += f"\n   {seg_label}: {seg_origin}→{seg_dest}\n"
                    elif is_round_trip and seg_idx == 0:
                        seg_label = "🛫 IDA"
                        flight_list += f"\n   {seg_label}: {seg_origin}→{seg_dest} (Directo)\n"
                    elif is_round_trip and seg_idx == 1:
                        seg_label = "🛬 VUELTA"
                        flight_list += f"\n   {seg_label}: {seg_origin}→{seg_dest} (Directo)\n"
                    else:
                        seg_label = f"✈️ Tramo {seg_idx + 1}"
                        flight_list += f"\n   {seg_label}: {seg_origin}→{seg_dest} (Directo)\n"
                    flight_list += f"   ✈️ {flight_id} | {dep_str}→{arr_str}\n"
                    if seg_duration:
                        readable_seg_duration = parse_iso_duration(seg_duration)
                        flight_list += f"   ⏱️ {readable_seg_duration}\n"

                # Calculate total duration by summing segments
                total_minutes = 0
                for seg in segments:
                    seg_dur = seg.get("duration", "")
                    if seg_dur:
                        # Parse ISO duration to minutes
                        match = re.match(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?', seg_dur)
                        if match:
                            days = int(match.group(1) or 0)
                            hours = int(match.group(2) or 0)
                            mins = int(match.group(3) or 0)
                            total_minutes += days * 24 * 60 + hours * 60 + mins

                if total_minutes > 0:
                    total_hours = total_minutes // 60
                    remaining_mins = total_minutes % 60
                    if total_hours >= 24:
                        days = total_hours // 24
                        hours = total_hours % 24
                        flight_list += f"\n   📊 Duración total: {days}d {hours}h {remaining_mins}m\n"
                    else:
                        flight_list += f"\n   📊 Duración total: {total_hours}h {remaining_mins}m\n"

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
            chain = hotel.get("chain", "")
            price = hotel.get("price", {})
            total = price.get("total", "N/A") if isinstance(price, dict) else "N/A"
            currency = price.get("currency", "USD") if isinstance(price, dict) else "USD"

            # Get amenities (show top 4)
            amenities = hotel.get("amenities", [])
            amenities_str = ", ".join(amenities[:4]) if amenities else "WiFi"

            # Get location
            address = hotel.get("address", {})
            city_name = address.get("cityName", "") if isinstance(address, dict) else ""
            location = hotel.get("location_description", city_name)

            # Star rating emoji
            stars = "⭐" * int(rating) if rating.isdigit() else "⭐⭐⭐⭐"

            # Format hotel info
            hotel_list += f"━━━━━━━━━━━━━━━━━━━━\n"
            hotel_list += f"*{i}. {name}*\n"
            if chain:
                hotel_list += f"   🏢 Cadena: {chain}\n"
            hotel_list += f"   {stars} ({rating} estrellas)\n"
            hotel_list += f"   💰 ${total} {currency}/noche\n"
            hotel_list += f"   📍 {location}\n"
            hotel_list += f"   ✨ {amenities_str}\n\n"
        
        text += hotel_list
        text += "_Responde con el número para reservar_"
    
    return text
