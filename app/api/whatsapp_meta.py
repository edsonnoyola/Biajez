from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import JSONResponse
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


def detect_time_of_day_from_text(text: str) -> str:
    """
    Detect time_of_day filter from natural language.
    Returns: MORNING, AFTERNOON, EVENING, NIGHT, or ANY
    """
    text_lower = text.lower()

    # EVENING: 18:00-22:00
    evening_keywords = [
        "en la noche", "noche", "nocturno", "evening",
        "despues de las 6", "despues de las 18", "6pm", "7pm", "8pm", "9pm"
    ]
    for kw in evening_keywords:
        if kw in text_lower:
            return "EVENING"

    # NIGHT: 22:00-06:00 (red eye)
    night_keywords = ["muy tarde", "red eye", "medianoche", "madrugada"]
    for kw in night_keywords:
        if kw in text_lower:
            return "NIGHT"

    # MORNING: 06:00-12:00
    morning_keywords = [
        "en la manana", "mañana", "temprano", "morning",
        "6am", "7am", "8am", "9am", "10am", "11am", "antes del mediodia"
    ]
    for kw in morning_keywords:
        if kw in text_lower:
            return "MORNING"

    # AFTERNOON: 12:00-18:00
    afternoon_keywords = [
        "en la tarde", "tarde", "afternoon", "mediodia",
        "12pm", "1pm", "2pm", "3pm", "4pm", "5pm", "despues del mediodia"
    ]
    for kw in afternoon_keywords:
        if kw in text_lower:
            return "AFTERNOON"

    return "ANY"


def detect_cabin_from_text(text: str) -> str:
    """
    Detect cabin class from natural language.
    Returns: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST
    """
    text_lower = text.lower()

    # BUSINESS
    business_keywords = ["business", "bussines", "bussinwss", "ejecutiva", "ejecutivo", "clase ejecutiva"]
    for kw in business_keywords:
        if kw in text_lower:
            return "BUSINESS"

    # FIRST
    first_keywords = ["primera clase", "first class", "primera"]
    for kw in first_keywords:
        if kw in text_lower:
            return "FIRST"

    # PREMIUM_ECONOMY
    premium_keywords = ["premium economy", "premium"]
    for kw in premium_keywords:
        if kw in text_lower:
            return "PREMIUM_ECONOMY"

    return "ECONOMY"


agent = AntigravityAgent()
flight_aggregator = FlightAggregator()

# DEPRECATED: Now using Redis session manager
# user_sessions = {}

# AUTHORIZED NUMBERS - loaded from env var (comma-separated)
_auth_env = os.getenv("AUTHORIZED_NUMBERS", "")
AUTHORIZED_NUMBERS = [n.strip() for n in _auth_env.split(",") if n.strip()]

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
    if not AUTHORIZED_NUMBERS:
        # No restriction configured - allow all
        return True
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
    
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")

    if mode == "subscribe" and verify_token and token == verify_token:
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

        # Save to Redis for debug (last 20 webhook events)
        try:
            import redis as _r
            _rc = _r.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            _rc.lpush("webhook_log", json.dumps({"ts": str(datetime.now()), "body": body})[:2000])
            _rc.ltrim("webhook_log", 0, 19)
        except:
            pass

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
        message_id = message.get("id")

        # ===== DEDUPLICACIÓN DE MENSAJES =====
        # WhatsApp puede enviar el mismo webhook múltiples veces
        # Usar un set en memoria para rastrear mensajes procesados
        if not hasattr(whatsapp_webhook, '_processed_messages'):
            whatsapp_webhook._processed_messages = set()

        if message_id in whatsapp_webhook._processed_messages:
            print(f"⏭️ Mensaje duplicado ignorado: {message_id}")
            return {"status": "ok", "duplicate": True}

        # Agregar al set (limitar a últimos 1000 para no consumir memoria)
        whatsapp_webhook._processed_messages.add(message_id)
        if len(whatsapp_webhook._processed_messages) > 1000:
            # Limpiar mensajes antiguos
            whatsapp_webhook._processed_messages = set(list(whatsapp_webhook._processed_messages)[-500:])

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
            elif "asiento" in button_title.lower():
                incoming_msg = "asientos"
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

        # DEBUG: Log session state
        print(f"🔍 SESSION for {from_number}: user_id={session.get('user_id')}, flights={len(session.get('pending_flights', []))}, selected={bool(session.get('selected_flight'))}, msg={incoming_msg[:30] if incoming_msg else 'None'}")

        # Initialize session if new user
        if not session.get("user_id"):
            from app.db.database import engine
            from sqlalchemy import text

            # Normalize phone number for lookup
            normalized_phone = normalize_mx_number(from_number)

            # Try multiple phone variations to find profile (using raw SQL that works)
            phone_variations = [
                from_number,
                normalized_phone,
                f"whatsapp_{from_number}",  # user_id format
                f"whatsapp_{normalized_phone}",
            ]

            print(f"🔍 Looking for profile with phone variations: {phone_variations}")

            user_id = None
            with engine.connect() as conn:
                # Search by phone_number column
                for phone_var in phone_variations:
                    result = conn.execute(
                        text("SELECT user_id FROM profiles WHERE phone_number = :phone LIMIT 1"),
                        {"phone": phone_var}
                    )
                    row = result.fetchone()
                    if row:
                        user_id = row[0]
                        print(f"✅ Found profile by phone_number={phone_var}: {user_id}")
                        break

                # Also search by user_id if not found by phone
                if not user_id:
                    for phone_var in phone_variations:
                        result = conn.execute(
                            text("SELECT user_id FROM profiles WHERE user_id = :uid LIMIT 1"),
                            {"uid": phone_var}
                        )
                        row = result.fetchone()
                        if row:
                            user_id = row[0]
                            print(f"✅ Found profile by user_id={phone_var}: {user_id}")
                            break

            if not user_id:
                # Create new WhatsApp user
                user_id = f"whatsapp_{from_number}"
                print(f"📱 New WhatsApp user (no profile found): {user_id}")

            session["user_id"] = user_id
            session_manager.save_session(from_number, session)

            # NOTE: Welcome message removed - was causing issues after Reset
            # The AI will greet naturally when appropriate

        # ============================================
        # REGISTRO DE PERFIL - HANDLER PRIORITARIO
        # Usa SQL directo porque SQLAlchemy ORM no commitea en PostgreSQL
        # ============================================
        from app.models.models import Profile
        from app.db.database import engine
        from sqlalchemy import text
        from datetime import datetime as dt

        msg_lower = incoming_msg.lower().strip()
        session_user_id = session.get("user_id")

        # Helper function to update profile with raw SQL
        def update_profile_sql(user_id, **fields):
            updates = []
            params = {"user_id": user_id}
            for key, value in fields.items():
                # IMPORTANT: Allow None values to set columns to NULL
                updates.append(f"{key} = :{key}")
                params[key] = value
            if updates:
                sql = f"UPDATE profiles SET {', '.join(updates)} WHERE user_id = :user_id"
                with engine.connect() as conn:
                    conn.execute(text(sql), params)
                    conn.commit()
                    print(f"   SQL UPDATE: {', '.join(f'{k}={v}' for k,v in fields.items())}")

        # Get current profile state with raw SQL
        def get_profile_sql(user_id):
            sql = "SELECT * FROM profiles WHERE user_id = :user_id"
            with engine.connect() as conn:
                result = conn.execute(text(sql), {"user_id": user_id})
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
            return None

        reg_profile_data = get_profile_sql(session_user_id) if session_user_id else None
        print(f"🔍 DEBUG Registration Check:")
        print(f"   session_user_id={session_user_id}")
        print(f"   profile found={reg_profile_data is not None}")
        print(f"   registration_step={reg_profile_data.get('registration_step') if reg_profile_data else 'N/A'}")
        print(f"   msg_lower={msg_lower[:50]}...")

        # CANCELAR REGISTRO - permite salir del flujo de registro
        if msg_lower in ['cancelar', 'salir', 'exit', 'reset', 'reiniciar', 'borrar', 'limpiar'] and reg_profile_data and reg_profile_data.get('registration_step'):
            update_profile_sql(session_user_id, registration_step=None)

            # Si es reset, también limpiar sesión
            if msg_lower in ['reset', 'reiniciar', 'borrar', 'limpiar']:
                session_manager.delete_session(from_number)
                send_whatsapp_message(from_number, "✅ Sesión reiniciada y registro cancelado.\n\n¿A dónde quieres viajar?")
            else:
                send_whatsapp_message(from_number, "❌ Registro cancelado.\n\nPuedes escribir *registrar* cuando quieras continuar.")
            return {"status": "ok"}

        # Iniciar registro
        if msg_lower in ['registrar', 'registro', 'actualizar perfil', 'editar perfil']:
            if not reg_profile_data:
                # Create new profile with raw SQL
                sql = """INSERT INTO profiles (user_id, phone_number, legal_first_name, legal_last_name,
                         gender, dob, passport_number, passport_expiry, passport_country, registration_step)
                         VALUES (:user_id, :phone, '', '', 'M', '1990-01-01', '', '2030-01-01', 'XX', 'nombre')"""
                with engine.connect() as conn:
                    conn.execute(text(sql), {"user_id": session_user_id, "phone": from_number})
                    conn.commit()
            else:
                update_profile_sql(session_user_id, registration_step="nombre")

            response_text = "👤 *Registro de Perfil*\n\n"
            response_text += "Vamos a registrar tus datos para poder reservar vuelos.\n\n"
            response_text += "📛 *Paso 1/6:* ¿Cuál es tu *nombre completo* como aparece en tu identificación?\n\n"
            response_text += "_Ejemplo: Juan Carlos Pérez García_\n\n"
            response_text += "_(Escribe *cancelar* en cualquier momento para salir)_"
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}

        # Procesar pasos del registro si está en uno
        # IMPORTANTE: Solo procesar si registration_step está activo Y no es None/null/empty
        current_step = reg_profile_data.get('registration_step') if reg_profile_data else None

        # SAFEGUARD: Double check that step is actually set
        if current_step and str(current_step).lower() not in ['none', 'null', '']:
            step = current_step
            print(f"📝 REGISTRATION FLOW ACTIVE: step={step}, processing message: {incoming_msg[:30]}...")
            response_text = ""

            if step == "nombre":
                parts = incoming_msg.strip().split()
                if len(parts) >= 2:
                    first_name = " ".join(parts[:-1])
                    last_name = parts[-1]
                else:
                    first_name = incoming_msg.strip()
                    last_name = "."

                update_profile_sql(session_user_id, legal_first_name=first_name, legal_last_name=last_name, registration_step="email")
                response_text = f"✅ Nombre: *{first_name} {last_name}*\n\n"
                response_text += "📧 *Paso 2/6:* ¿Cuál es tu *email*?\n\n"
                response_text += "_Aquí recibirás confirmaciones de reserva_"

            elif step == "email":
                if "@" in incoming_msg and "." in incoming_msg:
                    email = incoming_msg.strip().lower()
                    update_profile_sql(session_user_id, email=email, registration_step="nacimiento")
                    response_text = f"✅ Email: *{email}*\n\n"
                    response_text += "📅 *Paso 3/6:* ¿Cuál es tu *fecha de nacimiento*?\n\n"
                    response_text += "_Formato: DD/MM/AAAA (ejemplo: 15/03/1990)_"
                else:
                    response_text = "❌ Email inválido. Por favor ingresa un email válido.\n\n"
                    response_text += "_Ejemplo: juan@gmail.com_"

            elif step == "nacimiento":
                try:
                    fecha = incoming_msg.strip().replace("-", "/")
                    parsed_date = None
                    for fmt in ["%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]:
                        try:
                            parsed_date = dt.strptime(fecha, fmt).date()
                            break
                        except:
                            continue

                    if not parsed_date:
                        raise ValueError("Fecha inválida")

                    update_profile_sql(session_user_id, dob=str(parsed_date), registration_step="genero")
                    response_text = f"✅ Nacimiento: *{parsed_date}*\n\n"
                    response_text += "🚻 *Paso 4/6:* ¿Cuál es tu *género*?\n\n"
                    response_text += "Responde: *M* (Masculino) o *F* (Femenino)"
                except:
                    response_text = "❌ Fecha inválida.\n\nPor favor usa el formato: *DD/MM/AAAA*\n_Ejemplo: 15/03/1990_"

            elif step == "genero":
                genero = incoming_msg.strip().upper()
                if genero in ["M", "F", "MASCULINO", "FEMENINO", "HOMBRE", "MUJER"]:
                    gender_val = "M" if genero in ["M", "MASCULINO", "HOMBRE"] else "F"
                    update_profile_sql(session_user_id, gender=gender_val, registration_step="pasaporte")
                    response_text = f"✅ Género: *{'Masculino' if gender_val == 'M' else 'Femenino'}*\n\n"
                    response_text += "🛂 *Paso 5/6:* ¿Tienes *pasaporte*?\n\n"
                    response_text += "Responde *SI* para registrarlo o *NO* para omitir\n"
                    response_text += "_El pasaporte es necesario para vuelos internacionales_"
                else:
                    response_text = "❌ Por favor responde *M* o *F*"

            elif step == "pasaporte":
                if incoming_msg.strip().lower() in ["si", "sí", "yes", "s"]:
                    update_profile_sql(session_user_id, registration_step="pasaporte_numero")
                    response_text = "🛂 *Número de pasaporte:*\n\n_Ingresa el número de tu pasaporte_"
                elif incoming_msg.strip().lower() in ["no", "n", "omitir"]:
                    update_profile_sql(session_user_id, registration_step=None, passport_number="N/A", passport_country="XX", passport_expiry="2099-01-01")
                    profile = get_profile_sql(session_user_id)
                    response_text = "✅ *¡Perfil registrado!*\n\n"
                    response_text += f"👤 {profile['legal_first_name']} {profile['legal_last_name']}\n"
                    response_text += f"📧 {profile['email']}\n"
                    response_text += f"📅 {profile['dob']}\n\n"
                    response_text += "Ya puedes reservar vuelos nacionales.\n"
                    response_text += "_Para vuelos internacionales necesitarás pasaporte._"
                else:
                    response_text = "Por favor responde *SI* o *NO*"

            elif step == "pasaporte_numero":
                passport = incoming_msg.strip().upper()
                # Encrypt passport before storing
                from app.utils.encryption import encrypt_value
                encrypted_passport = encrypt_value(passport)
                update_profile_sql(session_user_id, passport_number=encrypted_passport, registration_step="pasaporte_pais")
                response_text = f"✅ Pasaporte: *{passport}*\n\n"
                response_text += "🌍 *País emisor del pasaporte:*\n\n_Código de 2 letras (MX, US, ES, etc.)_"

            elif step == "pasaporte_pais":
                country = incoming_msg.strip().upper()[:2]
                update_profile_sql(session_user_id, passport_country=country, registration_step="pasaporte_vencimiento")
                response_text = f"✅ País: *{country}*\n\n"
                response_text += "📅 *Fecha de vencimiento del pasaporte:*\n\n_Formato: DD/MM/AAAA_"

            elif step == "pasaporte_vencimiento":
                try:
                    fecha = incoming_msg.strip().replace("-", "/")
                    parsed_date = None
                    for fmt in ["%d/%m/%Y", "%Y/%m/%d"]:
                        try:
                            parsed_date = dt.strptime(fecha, fmt).date()
                            break
                        except:
                            continue

                    if parsed_date:
                        update_profile_sql(session_user_id, passport_expiry=str(parsed_date), registration_step=None)
                        profile = get_profile_sql(session_user_id)
                        response_text = "✅ *¡Perfil completo!*\n\n"
                        response_text += f"👤 {profile['legal_first_name']} {profile['legal_last_name']}\n"
                        response_text += f"📧 {profile['email']}\n"
                        response_text += f"📅 Nacimiento: {profile['dob']}\n"
                        from app.utils.encryption import decrypt_value
                        _decrypted_pp = decrypt_value(str(profile['passport_number']))
                        passport_display = _decrypted_pp[-4:] if len(_decrypted_pp) > 4 else _decrypted_pp
                        response_text += f"🛂 Pasaporte: {profile['passport_country']} - ***{passport_display}\n"
                        response_text += f"   Vence: {profile['passport_expiry']}\n\n"
                        response_text += "🎉 *Ya puedes reservar vuelos nacionales e internacionales!*"
                    else:
                        response_text = "❌ Fecha inválida. Usa formato: *DD/MM/AAAA*\n_Ejemplo: 15/06/2030_\n\n_(Escribe *cancelar* para salir)_"
                except Exception as e:
                    print(f"ERROR in pasaporte_vencimiento: {e}")
                    response_text = "❌ Fecha inválida. Usa formato: *DD/MM/AAAA*"

            if response_text:
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}

        # ============================================
        # FIN HANDLER DE REGISTRO PRIORITARIO
        # ============================================

        # ===== HELP COMMAND =====
        if incoming_msg.lower() in ["ayuda", "help", "que puedes hacer", "qué puedes hacer", "comandos", "menu", "menú"]:
            help_text = """*Biatriz - Tu Asistente de Viajes* ✈️

*BUSCAR Y RESERVAR*
• vuelo MEX a MAD 15 marzo
• hotel en Madrid del 15 al 18
• apartar vuelo _(reservar sin pagar)_
• pagar _(completar pago pendiente)_

*MIS VIAJES*
• itinerario _(próximo viaje)_
• historial _(viajes pasados)_
• cancelar vuelo
• cambiar vuelo

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
        if incoming_msg.lower().strip() in ["mi perfil", "perfil", "ver perfil", "mis datos"]:
            from app.models.models import Profile

            profile = db.query(Profile).filter(Profile.user_id == session.get("user_id")).first()

            if not profile or not profile.legal_first_name or profile.legal_first_name in ["", "WhatsApp"]:
                response_text = "👤 *Tu perfil está vacío*\n\n"
                response_text += "Escribe *registrar* para completar tus datos."
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}

            # Mostrar datos personales
            response_text = "👤 *Tu Perfil*\n\n"
            response_text += f"📛 Nombre: {profile.legal_first_name} {profile.legal_last_name}\n"
            response_text += f"📧 Email: {profile.email or 'No registrado'}\n"
            response_text += f"📅 Nacimiento: {profile.dob}\n"
            response_text += f"🚻 Género: {'Masculino' if str(profile.gender) == 'GenderEnum.M' or str(profile.gender) == 'M' else 'Femenino'}\n"

            if profile.passport_number and profile.passport_number not in ["", "N/A", "000000000"]:
                from app.utils.encryption import decrypt_value
                _dec_pp = decrypt_value(profile.passport_number)
                passport_display = f"***{_dec_pp[-4:]}" if len(_dec_pp) > 4 else _dec_pp
                response_text += f"🛂 Pasaporte: {passport_display}\n"
                response_text += f"   País: {profile.passport_country}\n"
                response_text += f"   Vence: {profile.passport_expiry}\n"

            # Mostrar preferencias
            response_text += "\n✈️ *Preferencias de Vuelo*\n"
            response_text += f"   Asiento: {profile.seat_preference or 'ANY'}\n"
            response_text += f"   Clase: {profile.flight_class_preference or 'ECONOMY'}\n"
            if profile.preferred_airline:
                response_text += f"   Aerolínea: {profile.preferred_airline}\n"

            response_text += f"\n🏨 *Hotel:* {profile.hotel_preference or '4_STAR'}\n"

            # Estado del perfil
            is_complete = profile.legal_first_name and profile.email and profile.dob
            if is_complete:
                response_text += "\n✅ *Perfil completo* - Puedes reservar vuelos"
            else:
                response_text += "\n⚠️ Escribe 'registrar' para completar"

            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}

        # Solo preferencias
        if incoming_msg.lower().strip() == "preferencias":
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
        
        # ===== HANDLE SLICE SELECTION FOR FLIGHT CHANGE (round trips) =====
        # IMPORTANT: Skip if pending_flights exists (user is selecting a flight, not a slice)
        _pending_change = session.get("pending_change", {})
        if isinstance(_pending_change, dict) and _pending_change.get("awaiting_slice_selection") and incoming_msg.strip().isdigit() and not session.get("pending_flights"):
            slice_idx = int(incoming_msg.strip()) - 1
            slices_info = _pending_change.get("slices", [])
            if 0 <= slice_idx < len(slices_info):
                selected = slices_info[slice_idx]
                session["pending_change"] = {
                    "pnr": _pending_change.get("pnr"),
                    "order_id": _pending_change.get("order_id"),
                    "selected_slice": selected
                }
                session_manager.save_session(from_number, session)
                send_whatsapp_message(from_number,
                    f"Seleccionaste: {selected['origin']} → {selected['destination']} | {selected['date']}\n\n"
                    f"Escribe la nueva fecha:\nEjemplo: cambiar 25 marzo")
            else:
                send_whatsapp_message(from_number, f"❌ Opción inválida. Elige entre 1 y {len(slices_info)}.")
            return {"status": "ok"}

        # ===== HANDLE PENDING FLIGHT CHANGE: "cambiar a [fecha]" =====
        # Accept: "cambiar a 25 marzo", "cambiar al 25 marzo", "cambiar 25 marzo", "25 marzo", etc.
        # IMPORTANT: Skip if pending_flights exists (user is selecting a flight, not changing one)
        _has_pending_change = isinstance(_pending_change, dict) and _pending_change.get("order_id") and not _pending_change.get("awaiting_slice_selection") and not session.get("pending_change_offers") and not session.get("pending_flights")
        _is_change_msg = False
        _change_date_text = ""
        if _has_pending_change:
            import re as _re
            # Skip if user is sending a command (not a date)
            _change_commands = ['cambiar vuelo', 'cambiar fecha', 'modificar vuelo', 'cancelar vuelo',
                               'cancelar', 'buscar', 'vuelo', 'hotel', 'ayuda', 'hola', 'mis viajes',
                               'reset', 'reiniciar', 'menu', 'menú', 'inicio', 'no']
            _is_command = any(msg_lower.strip() == cmd or msg_lower.strip().startswith(cmd + ' ') for cmd in _change_commands if ' ' in cmd) or msg_lower.strip() in _change_commands
            if not _is_command:
                # Match "cambiar a/al/para [date]" or "cambiar [date]" or just a date when pending
                _change_match = _re.match(r'^cambiar\s+(?:a\s+|al\s+|para\s+|para\s+el\s+|el\s+)?(.+)$', msg_lower)
                if _change_match:
                    _is_change_msg = True
                    _change_date_text = _change_match.group(1).strip()
                elif not any(kw in msg_lower for kw in _change_commands):
                    # If pending_change is set and message looks like a date (not a command), try parsing it
                    _is_change_msg = True
                    _change_date_text = msg_lower.strip()

        if _is_change_msg and _change_date_text:
            import requests as _requests
            from app.utils.date_parser import SmartDateParser

            pending = session["pending_change"]
            order_id = pending.get("order_id")
            change_pnr = pending.get("pnr")

            if not order_id:
                send_whatsapp_message(from_number, "❌ No se encontró el ID de la orden para cambiar.")
                session.pop("pending_change", None)
                session_manager.save_session(from_number, session)
                return {"status": "ok"}

            # Parse the new date from user message
            date_text = _change_date_text
            new_date = SmartDateParser.parse_single_date(date_text)

            if not new_date:
                send_whatsapp_message(from_number, "❌ No entendí la fecha. Ejemplos:\n• cambiar a 25 marzo\n• cambiar a 15/04/2026\n• cambiar a marzo 20")
                return {"status": "ok"}

            try:
                token = os.getenv("DUFFEL_ACCESS_TOKEN")
                duffel_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "Duffel-Version": "v2"
                }

                # Check if we have a pre-selected slice (from "cambiar vuelo" step)
                selected_slice = pending.get("selected_slice")

                # Fetch order from Duffel to get current slice IDs
                order_resp = _requests.get(f"https://api.duffel.com/air/orders/{order_id}", headers=duffel_headers)
                if order_resp.status_code != 200:
                    print(f"❌ Order fetch failed: {order_resp.status_code} - {order_resp.text[:300]}")
                    send_whatsapp_message(from_number, "❌ No se pudo obtener la información de tu vuelo.\n\nIntenta de nuevo en unos minutos.")
                    return {"status": "ok"}

                order_data = order_resp.json()["data"]
                slices = order_data.get("slices", [])

                if not slices:
                    send_whatsapp_message(from_number, "❌ No se encontraron segmentos en la orden.")
                    return {"status": "ok"}

                # Build slices to remove and add
                slices_to_remove = []
                slices_to_add = []

                if selected_slice:
                    # Only change the selected slice, keep others
                    target_slice_id = selected_slice.get("id")
                    for s in slices:
                        if s["id"] == target_slice_id:
                            slices_to_remove.append({"slice_id": s["id"]})
                            slices_to_add.append({
                                "origin": selected_slice.get("origin", ""),
                                "destination": selected_slice.get("destination", ""),
                                "departure_date": new_date,
                                "cabin_class": "economy"
                            })
                            break
                    if not slices_to_remove:
                        # Fallback: slice ID not found, change first slice
                        s = slices[0]
                        slices_to_remove.append({"slice_id": s["id"]})
                        origin_data = s.get("origin", {})
                        dest_data = s.get("destination", {})
                        slices_to_add.append({
                            "origin": origin_data.get("iata_code", "") if isinstance(origin_data, dict) else str(origin_data),
                            "destination": dest_data.get("iata_code", "") if isinstance(dest_data, dict) else str(dest_data),
                            "departure_date": new_date,
                            "cabin_class": "economy"
                        })
                else:
                    # No pre-selected slice - change all (single leg or legacy flow)
                    for s in slices:
                        slices_to_remove.append({"slice_id": s["id"]})
                        origin_data = s.get("origin", {})
                        dest_data = s.get("destination", {})
                        orig_code = origin_data.get("iata_code", "") if isinstance(origin_data, dict) else str(origin_data)
                        dest_code = dest_data.get("iata_code", "") if isinstance(dest_data, dict) else str(dest_data)
                        slices_to_add.append({
                            "origin": orig_code,
                            "destination": dest_code,
                            "departure_date": new_date,
                            "cabin_class": "economy"
                        })

                # Create change request with Duffel
                change_url = "https://api.duffel.com/air/order_change_requests"
                change_payload = {
                    "data": {
                        "order_id": order_id,
                        "slices": {
                            "remove": slices_to_remove,
                            "add": slices_to_add
                        }
                    }
                }
                change_resp = _requests.post(change_url, json=change_payload, headers=duffel_headers)

                if change_resp.status_code != 201:
                    error_msg = change_resp.text
                    if "order_change_not_possible" in error_msg or "not changeable" in error_msg or "invalid_state_error" in error_msg:
                        send_whatsapp_message(from_number, "❌ Esta aerolínea no permite cambios en este boleto.\n\nPuedes cancelar y reservar uno nuevo.")
                    elif "no_available" in error_msg or "sold_out" in error_msg:
                        send_whatsapp_message(from_number, f"❌ No hay vuelos disponibles para {new_date}. Intenta otra fecha.")
                    else:
                        # Log full error but show clean message to user
                        print(f"❌ Change request failed: {change_resp.status_code} - {error_msg[:300]}")
                        send_whatsapp_message(from_number, "❌ No se pudo solicitar el cambio de vuelo.\n\nIntenta de nuevo o contacta soporte.")
                    session.pop("pending_change", None)
                    session_manager.save_session(from_number, session)
                    return {"status": "ok"}

                change_request = change_resp.json()["data"]
                offers = change_request.get("order_change_offers", [])

                if not offers:
                    send_whatsapp_message(from_number, f"❌ No hay opciones de cambio disponibles para {new_date}.\n\nIntenta con otra fecha: 'cambiar a [fecha]'")
                    return {"status": "ok"}

                # Show change options to user
                response_text = f"*Opciones de cambio para {new_date}:*\n\n"
                change_offers_list = []

                for idx, offer in enumerate(offers[:5]):  # Max 5 options
                    change_amount = offer.get("change_total_amount", "0")
                    change_currency = offer.get("change_total_currency", "USD")
                    penalty = offer.get("penalty_total_amount", "0")
                    new_total = offer.get("new_total_amount", "0")

                    # Get new flight details
                    # Duffel returns slices as {"add": [...], "remove": [...]}, not a list
                    slices_data = offer.get("slices", {})
                    new_slices = slices_data.get("add", []) if isinstance(slices_data, dict) else slices_data if isinstance(slices_data, list) else []
                    route_info = ""
                    for ns in new_slices:
                        segs = ns.get("segments", [])
                        if segs:
                            first_seg = segs[0]
                            dep_time = first_seg.get("departing_at", "")[:16].replace("T", " ")
                            _carrier_data = first_seg.get("marketing_carrier", {})
                            carrier = _carrier_data.get("iata_code", "") if isinstance(_carrier_data, dict) else str(_carrier_data)
                            flight_no = first_seg.get("marketing_carrier_flight_number", "")
                            route_info += f"   {carrier} {flight_no} - {dep_time}\n"

                    response_text += f"*{idx + 1}.* Diferencia: ${change_amount} {change_currency}\n"
                    if float(penalty) > 0:
                        response_text += f"   Penalidad: ${penalty}\n"
                    response_text += f"   Nuevo total: ${new_total} {change_currency}\n"
                    if route_info:
                        response_text += route_info
                    response_text += "\n"

                    change_offers_list.append({
                        "offer_id": offer["id"],
                        "change_amount": change_amount,
                        "new_total": new_total,
                        "currency": change_currency
                    })

                response_text += "Envía el *número* de la opción para confirmar el cambio.\n"
                response_text += "O escribe *cancelar* para no cambiar."

                session["pending_change_offers"] = change_offers_list
                session["pending_change"]["change_request_id"] = change_request["id"]
                session_manager.save_session(from_number, session)

                send_whatsapp_message(from_number, response_text)
            except Exception as e:
                print(f"❌ Flight change error: {e}")
                send_whatsapp_message(from_number, "❌ Hubo un error al procesar el cambio.\n\nIntenta de nuevo en unos minutos.")

            return {"status": "ok"}

        # ===== HANDLE CHANGE OFFER SELECTION (number) =====
        if incoming_msg.strip().isdigit() and session.get("pending_change_offers"):
            import requests as _requests

            offer_idx = int(incoming_msg.strip()) - 1
            offers = session["pending_change_offers"]

            if offer_idx < 0 or offer_idx >= len(offers):
                send_whatsapp_message(from_number, f"❌ Opción inválida. Elige entre 1 y {len(offers)}.")
                return {"status": "ok"}

            selected_offer = offers[offer_idx]
            offer_id = selected_offer["offer_id"]

            try:
                token = os.getenv("DUFFEL_ACCESS_TOKEN")
                duffel_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "Duffel-Version": "v2"
                }

                # Step 2: Create pending order change
                create_url = "https://api.duffel.com/air/order_changes"
                create_payload = {
                    "data": {
                        "selected_order_change_offer": offer_id
                    }
                }
                resp = _requests.post(create_url, json=create_payload, headers=duffel_headers)

                if resp.status_code in [200, 201]:
                    change_data = resp.json()["data"]
                    change_id = change_data["id"]
                    new_order_id = change_data.get("order_id", "")

                    # Step 3: Confirm the change with payment (REQUIRED)
                    # First, fetch the actual change amount from Duffel to avoid payment mismatch
                    confirm_url = f"https://api.duffel.com/air/order_changes/{change_id}/actions/confirm"
                    payment_amount = selected_offer.get("change_amount", "0")
                    payment_currency = selected_offer.get("currency", "USD")

                    # Only include payment if there's an actual charge (change_total_amount > 0)
                    confirm_payload = {"data": {}}
                    if float(payment_amount) > 0:
                        confirm_payload["data"]["payment"] = {
                            "amount": str(payment_amount),
                            "currency": payment_currency,
                            "type": "balance"
                        }

                    print(f"DEBUG: Confirming change {change_id} with payment: {payment_amount} {payment_currency}")
                    confirm_resp = _requests.post(confirm_url, json=confirm_payload, headers=duffel_headers)
                    if confirm_resp.status_code not in [200, 201]:
                        print(f"❌ Change confirm failed: {confirm_resp.status_code} - {confirm_resp.text[:300]}")
                        send_whatsapp_message(from_number, "❌ No se pudo confirmar el cambio de vuelo.\n\nIntenta de nuevo o busca otra opción.")
                        # Clean up on failure so user isn't stuck
                        session.pop("pending_change", None)
                        session.pop("pending_change_offers", None)
                        session_manager.save_session(from_number, session)
                        return {"status": "ok"}

                    # Extract new flight info from the confirmed change response
                    confirmed_data = confirm_resp.json().get("data", {})
                    confirmed_new_total = confirmed_data.get("new_total_amount", selected_offer.get("new_total", "0"))
                    confirmed_currency = confirmed_data.get("new_total_currency", payment_currency)
                    confirmed_penalty = confirmed_data.get("penalty_total_amount", "0")
                    confirmed_change_amt = confirmed_data.get("change_total_amount", payment_amount)

                    # Extract new departure date from confirmed slices
                    new_departure_date = None
                    confirmed_slices = confirmed_data.get("slices", {})
                    added_slices = confirmed_slices.get("add", []) if isinstance(confirmed_slices, dict) else []
                    for aslice in added_slices:
                        segs = aslice.get("segments", [])
                        if segs:
                            dep_at = segs[0].get("departing_at", "")
                            if dep_at:
                                new_departure_date = dep_at[:10]
                                break

                    # Update DB via raw SQL
                    from sqlalchemy import text as _text
                    pnr = session.get("pending_change", {}).get("pnr")
                    user_id = session.get("user_id", "")
                    if pnr:
                        try:
                            with engine.connect() as conn:
                                # Use a safe UPDATE that only touches columns that definitely exist
                                update_params = {
                                    "new_total": float(confirmed_new_total) if confirmed_new_total else 0,
                                    "pnr": pnr,
                                    "uid": user_id
                                }
                                update_sql = "UPDATE trips SET total_amount = :new_total"

                                # Update departure_date if we have the new date
                                if new_departure_date:
                                    update_sql += ", departure_date = :new_dep_date"
                                    update_params["new_dep_date"] = new_departure_date

                                # Try to update change-specific columns (may not exist in older DBs)
                                try:
                                    update_sql_full = update_sql + ", previous_order_id = duffel_order_id, change_penalty_amount = :penalty WHERE booking_reference = :pnr AND user_id = :uid"
                                    update_params["penalty"] = float(confirmed_penalty) if confirmed_penalty else 0
                                    conn.execute(_text(update_sql_full), update_params)
                                except Exception as col_err:
                                    print(f"⚠️ Change columns not available, using basic update: {col_err}")
                                    conn.rollback()
                                    update_sql += " WHERE booking_reference = :pnr AND user_id = :uid"
                                    conn.execute(_text(update_sql), update_params)

                                conn.commit()
                                print(f"✅ Trip {pnr} updated after change: total={confirmed_new_total}, date={new_departure_date}")
                        except Exception as db_err:
                            print(f"⚠️ DB update after change failed: {db_err}")

                    response_text = f"✅ *¡Vuelo cambiado exitosamente!*\n\n"
                    response_text += f"📝 *PNR:* {pnr}\n"
                    if float(confirmed_change_amt) > 0:
                        response_text += f"💳 *Diferencia cobrada:* ${confirmed_change_amt} {confirmed_currency}\n"
                    elif float(confirmed_change_amt) < 0:
                        response_text += f"💰 *Reembolso:* ${abs(float(confirmed_change_amt))} {confirmed_currency}\n"
                    else:
                        response_text += f"✨ *Sin costo adicional*\n"
                    if float(confirmed_penalty) > 0:
                        response_text += f"⚠️ *Penalidad:* ${confirmed_penalty} {confirmed_currency}\n"
                    response_text += f"💰 *Nuevo total:* ${confirmed_new_total} {confirmed_currency}"
                    if new_departure_date:
                        response_text += f"\n📅 *Nueva fecha:* {new_departure_date}"

                    # Clean up session
                    session.pop("pending_change", None)
                    session.pop("pending_change_offers", None)
                    session_manager.save_session(from_number, session)

                    send_whatsapp_message(from_number, response_text)
                else:
                    print(f"❌ Change confirm alt failed: {resp.status_code} - {resp.text[:300]}")
                    send_whatsapp_message(from_number, "❌ No se pudo confirmar el cambio de vuelo.\n\nIntenta de nuevo o busca otra opción.")
                    # Clean up on failure
                    session.pop("pending_change", None)
                    session.pop("pending_change_offers", None)
                    session_manager.save_session(from_number, session)

            except Exception as e:
                print(f"❌ Change confirmation error: {e}")
                # Clean up on any error
                session.pop("pending_change", None)
                session.pop("pending_change_offers", None)
                session_manager.save_session(from_number, session)
                send_whatsapp_message(from_number, "❌ Hubo un error al cambiar tu vuelo.\n\nIntenta de nuevo en unos minutos.")

            return {"status": "ok"}

        # ===== SEAT CODE HANDLER (e.g. "12A") =====
        _seat_match = re.match(r'^(\d{1,2}[A-Ka-k])$', incoming_msg.strip())
        if _seat_match and session.get("pending_seat_selection"):
            seat_code = _seat_match.group(1).upper()
            seat_data = session["pending_seat_selection"]
            order_id = seat_data.get("order_id")
            seat_map = seat_data.get("seat_map")
            seat_pnr = seat_data.get("pnr", "")

            from app.services.seat_selection_service import SeatSelectionService
            seat_service = SeatSelectionService()
            seat_info = seat_service.find_seat_service_id(seat_map, seat_code)

            if not seat_info:
                send_whatsapp_message(from_number, f"❌ Asiento *{seat_code}* no disponible. Elige otro del mapa.")
                return {"status": "ok"}

            result = await seat_service.select_seat(
                order_id, seat_info["service_id"],
                amount=seat_info.get("price", "0"),
                currency=seat_info.get("currency", "USD")
            )
            if result.get("success"):
                response_text = f"✅ *Asiento {seat_code} confirmado*\n\n"
                response_text += f"PNR: {seat_pnr}\n"
                response_text += "Tu asiento ha sido asignado."
            else:
                response_text = f"❌ No se pudo asignar el asiento: {result.get('error', 'Error desconocido')}"

            session.pop("pending_seat_selection", None)
            session_manager.save_session(from_number, session)
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}

        # ===== BAGGAGE SELECTION HANDLER (digit when pending_baggage) =====
        if incoming_msg.strip().isdigit() and session.get("pending_baggage") and not session.get("pending_flights") and not session.get("pending_change_offers"):
            bag_idx = int(incoming_msg.strip()) - 1
            bag_data = session["pending_baggage"]
            options = bag_data.get("options", [])
            bag_order_id = bag_data.get("order_id")
            bag_pnr = bag_data.get("pnr", "")

            if 0 <= bag_idx < len(options):
                selected_option = options[bag_idx]
                service_id = selected_option.get("id")

                from app.services.baggage_service import BaggageService
                baggage_service = BaggageService(db)
                # Pass price info so Duffel gets correct payment.amount+currency
                svc_prices = [{"id": service_id, "amount": selected_option.get("price", "0"), "currency": selected_option.get("currency", "USD")}]
                result = baggage_service.add_baggage(bag_order_id, [service_id], service_prices=svc_prices)

                if result.get("success"):
                    price = selected_option.get("price", "0")
                    currency = selected_option.get("currency", "USD")
                    response_text = f"✅ *Maleta agregada*\n\n"
                    response_text += f"PNR: {bag_pnr}\n"
                    response_text += f"Costo: ${price} {currency}\n"
                    response_text += f"Nuevo total: ${result.get('new_total', 'N/A')} {result.get('currency', 'USD')}"
                else:
                    response_text = f"❌ No se pudo agregar la maleta: {result.get('error', 'Error desconocido')}"

                session.pop("pending_baggage", None)
                session_manager.save_session(from_number, session)
                send_whatsapp_message(from_number, response_text)
            else:
                send_whatsapp_message(from_number, f"❌ Opción inválida. Elige entre 1 y {len(options)}.")
            return {"status": "ok"}

        # Check if selecting flight by number
        print(f"🔍 DEBUG Flight Selection: msg='{incoming_msg}', isdigit={incoming_msg.strip().isdigit()}, pending_flights={len(session.get('pending_flights', []))}, redis_enabled={session_manager.enabled}")
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
                
                # Store last booking info for context (so user can say "same dates" later)
                session["last_booking"] = {
                    "type": "hotel",
                    "destination": hotel.get("location", hotel_name),
                    "checkin": hotel_dates.get('checkin'),
                    "checkout": hotel_dates.get('checkout'),
                    "dates": f"{hotel_dates.get('checkin')} to {hotel_dates.get('checkout')}"
                }
                session["selected_hotel"] = None
                session["hotel_dates"] = None
                session_manager.save_session(from_number, session)

                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}

            # Real booking with Duffel Stays (4-step flow: search > rates > quote > book)
            from app.models.models import Profile
            profile = db.query(Profile).filter(Profile.user_id == session["user_id"]).first()
            if not profile:
                response_text = "❌ Necesitas un perfil para reservar hoteles.\nEscribe *registrar* para crear tu perfil."
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}

            try:
                from app.services.duffel_stays import DuffelStaysEngine
                duffel_stays = DuffelStaysEngine()

                search_result_id = hotel.get("search_result_id") or hotel.get("offerId")

                if not search_result_id:
                    response_text = "❌ No se pudo procesar esta reserva. Busca hoteles de nuevo."
                    send_whatsapp_message(from_number, response_text)
                    return {"status": "ok"}

                # Step 2: Fetch all rates for this hotel
                send_whatsapp_message(from_number, "🔄 Obteniendo disponibilidad y tarifas...")
                rates_data = duffel_stays.fetch_all_rates(search_result_id)

                if not rates_data.get("success") or not rates_data.get("rooms"):
                    response_text = "❌ Este hotel ya no tiene habitaciones disponibles.\n\nIntenta buscar de nuevo."
                    send_whatsapp_message(from_number, response_text)
                    session["selected_hotel"] = None
                    session_manager.save_session(from_number, session)
                    return {"status": "ok"}

                # Use the cheapest rate
                cheapest_room = rates_data["rooms"][0]
                selected_rate_id = cheapest_room.get("rate_id")

                # Step 3: Create quote (confirms availability + final price)
                quote_data = duffel_stays.create_quote(selected_rate_id)

                if not quote_data.get("success"):
                    response_text = f"❌ {quote_data.get('error', 'No se pudo confirmar disponibilidad')}\n\nIntenta con otra opción."
                    send_whatsapp_message(from_number, response_text)
                    session["selected_hotel"] = None
                    session_manager.save_session(from_number, session)
                    return {"status": "ok"}

                quote_id = quote_data.get("quote_id")
                final_amount = quote_data.get("total_amount", "0")
                final_currency = quote_data.get("total_currency", "USD")

                # Step 4: Book using quote_id
                guest_info = {
                    "given_name": profile.legal_first_name,
                    "family_name": profile.legal_last_name,
                    "email": profile.email,
                    "phone_number": profile.phone_number
                }

                booking_result = duffel_stays.book_hotel(quote_id, guest_info)

                if not booking_result.get("success"):
                    response_text = f"❌ {booking_result.get('error', 'Error al reservar hotel')}\n\nIntenta de nuevo."
                    send_whatsapp_message(from_number, response_text)
                    session["selected_hotel"] = None
                    session_manager.save_session(from_number, session)
                    return {"status": "ok"}

                confirmation = booking_result.get("confirmation_number", "N/A")
                total = booking_result.get("total_amount", final_amount)
                currency = booking_result.get("total_currency", final_currency)
                check_in = booking_result.get("check_in_date", "")
                check_out = booking_result.get("check_out_date", "")

                response_text = f"✅ *¡Reserva de hotel confirmada!*\n\n"
                response_text += f"🏨 {hotel_name}\n"
                response_text += f"📝 Confirmación: *{confirmation}*\n"
                if check_in and check_out:
                    response_text += f"📅 {check_in} → {check_out}\n"
                response_text += f"💰 Total: ${total} {currency}\n\n"
                response_text += "✨ _Reserva confirmada._"

                # Save trip to DB
                try:
                    from app.services.booking_execution import save_trip_sql
                    save_trip_sql(
                        booking_reference=confirmation or f"HTL-{os.urandom(3).hex().upper()}",
                        user_id=profile.user_id,
                        provider_source="DUFFEL",
                        total_amount=float(total) if total else 0,
                        status="TICKETED",
                        invoice_url=""
                    )
                except Exception as db_err:
                    print(f"⚠️ Could not save hotel trip to DB: {db_err}")

                session["selected_hotel"] = None
                session_manager.save_session(from_number, session)
                
            except Exception as e:
                print(f"❌ Hotel booking error: {e}")
                response_text = "❌ Hubo un error al procesar la reserva.\n\nIntenta de nuevo en unos minutos."
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # Hotel selection moved above to prevent AI interception
        
        # Check if confirming booking
        # IMPORTANT: Skip this handler if user is in profile registration flow
        # Use raw SQL instead of ORM for reliability on PostgreSQL
        user_in_registration = False
        _confirm_uid = session.get("user_id")
        if _confirm_uid:
            with engine.connect() as conn:
                _reg_result = conn.execute(
                    text("SELECT registration_step FROM profiles WHERE user_id = :uid"),
                    {"uid": _confirm_uid}
                )
                _reg_row = _reg_result.fetchone()
                if _reg_row and _reg_row[0]:
                    user_in_registration = True
                    print(f"⚠️ User {_confirm_uid} is in registration step: {_reg_row[0]}")

        if incoming_msg.lower() in ['si', 'sí', 'yes', 'confirmar'] and not user_in_registration:
            print(f"🔍 DEBUG Confirmation attempt:")
            print(f"   - from_number: {from_number}")
            print(f"   - incoming_msg: {incoming_msg}")
            print(f"   - selected_flight exists: {bool(session.get('selected_flight'))}")
            print(f"   - selected_hotel exists: {bool(session.get('selected_hotel'))}")
            print(f"   - session user_id: {session.get('user_id')}")

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

            # ORIGINAL WORKING LOGIC: Simple profile lookup, no profile_complete check
            # Restored from commit 4a1781c which worked correctly
            from datetime import datetime as dt

            flight = session["selected_flight"]
            offer_id = flight.get("offer_id")
            provider = flight.get("provider")
            amount = float(flight.get("price", 0))

            # Simple profile lookup using ORM (this is how it worked originally)
            profile = db.query(Profile).filter(Profile.user_id == session["user_id"]).first()
            if not profile:
                # Create default profile - same as original working code
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
                try:
                    db.commit()
                except:
                    db.rollback()

            print(f"🔍 CONFIRM: user_id={session.get('user_id')}, profile={profile.legal_first_name if profile else 'None'}, provider={provider}")
            
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
                # MOCK BOOKING FOR TEST FLIGHTS ONLY
                # Real Duffel/Amadeus flights should go through the orchestrator
                if offer_id and offer_id.startswith("MOCK_"):
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

                    # Save trip using raw SQL (ORM doesn't persist on Render)
                    from app.services.booking_execution import save_trip_sql
                    save_trip_sql(
                        booking_reference=pnr,
                        user_id=session["user_id"],
                        provider_source="DUFFEL",
                        total_amount=float(price) if price else 0,
                        status="TICKETED",
                        departure_city=dep_city,
                        arrival_city=arr_city,
                        departure_date=dep_date,
                        confirmed_at=dt.utcnow().isoformat()
                    )

                    # Store last booking info for context (so user can say "same dates" later)
                    session["last_booking"] = {
                        "type": "vuelo",
                        "origin": dep_city,
                        "destination": arr_city,
                        "checkin": str(dep_date) if dep_date else None,
                        "checkout": None,
                        "dates": str(dep_date) if dep_date else "N/A"
                    }
                    send_whatsapp_message(from_number, response_text)
                    session.pop("selected_flight", None)
                    session.pop("pending_flights", None)
                    session_manager.save_session(from_number, session)
                    return {"status": "ok"}

                # REAL BOOKING (for production flight IDs - Duffel/Amadeus)
                print(f"🎫 REAL BOOKING: {offer_id} via {provider}")
                orchestrator = BookingOrchestrator(db)
                booking_result = orchestrator.execute_booking(
                    session["user_id"], offer_id, provider, amount
                )

                pnr = booking_result.get("pnr", "N/A")
                ticket_url = booking_result.get("ticket_url", "")

                # Get flight details for confirmation
                segments = flight_dict.get("segments", [])
                airline = segments[0].get("carrier_code", "N/A") if segments else "N/A"

                # Extract origin/destination
                dep_city = segments[0].get("departure_iata", "???") if segments else "???"
                arr_city = segments[-1].get("arrival_iata", "???") if segments else "???"
                dep_date = segments[0].get("departure_time", "")[:10] if segments else ""

                response_text = f"✅ *¡VUELO RESERVADO!*\n\n"
                response_text += f"📝 *PNR:* `{pnr}`\n"
                response_text += f"✈️ *Aerolínea:* {airline}\n"
                response_text += f"🛫 *Ruta:* {dep_city} → {arr_city}\n"
                response_text += f"📅 *Fecha:* {dep_date}\n"
                response_text += f"💰 *Total:* ${amount} USD\n"
                # Show change policy from selected flight metadata
                flight_metadata = flight_dict.get("metadata") or {}
                if flight_metadata.get("changeable"):
                    penalty = flight_metadata.get("change_penalty")
                    if penalty and float(penalty) > 0:
                        response_text += f"🔄 *Cambio:* Penalización ${penalty}\n"
                    else:
                        response_text += f"🔄 *Cambio:* Sin costo\n"
                # Show e-ticket if available
                eticket = booking_result.get("eticket_number")
                if eticket:
                    response_text += f"🎫 *E-ticket:* {eticket}\n"
                response_text += "\n✨ _Reserva REAL confirmada en la aerolínea_\n"
                if ticket_url:
                    response_text += f"🎫 Ticket: {ticket_url}"

                # Store last booking for context (include offer_id and order_id for post-booking services)
                duffel_order_id = booking_result.get("duffel_order_id")
                booking_offer_id = booking_result.get("offer_id")
                session["last_booking"] = {
                    "type": "vuelo",
                    "origin": dep_city,
                    "destination": arr_city,
                    "checkin": dep_date,
                    "checkout": None,
                    "dates": dep_date,
                    "pnr": pnr,
                    "duffel_order_id": duffel_order_id,
                    "offer_id": booking_offer_id
                }

                session["selected_flight"] = None
                session["pending_flights"] = []
                # Clear any stale post-booking states
                session.pop("pending_seat_selection", None)
                session.pop("pending_baggage", None)
                session_manager.save_session(from_number, session)
                
            except Exception as e:
                error_msg = str(e)
                # Also get detail from HTTPException if available
                error_detail = getattr(e, 'detail', error_msg)
                print(f"❌ Booking error: {error_detail}")

                # Log to DATABASE (raw SQL - always works on Render)
                try:
                    from sqlalchemy import text as _text
                    with engine.connect() as _err_conn:
                        _err_conn.execute(
                            _text("""INSERT INTO booking_errors (ts, phone, offer_id, provider, amount, error)
                                     VALUES (:ts, :phone, :oid, :prov, :amt, :err)"""),
                            {
                                "ts": datetime.now().isoformat(),
                                "phone": str(from_number),
                                "oid": str(offer_id)[:200] if offer_id else "N/A",
                                "prov": str(provider)[:50] if provider else "N/A",
                                "amt": str(amount),
                                "err": str(error_detail)[:2000]
                            }
                        )
                        _err_conn.commit()
                except Exception as db_log_err:
                    print(f"⚠️ DB error log failed: {db_log_err}")
                    # Fallback: log to Redis
                    try:
                        import redis as _rlog
                        _rc_log = _rlog.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
                        _rc_log.lpush("booking_errors", json.dumps({
                            "ts": datetime.now().isoformat(),
                            "phone": str(from_number),
                            "offer_id": str(offer_id)[:80] if offer_id else "N/A",
                            "error": str(error_detail)[:1000]
                        }))
                        _rc_log.ltrim("booking_errors", 0, 49)
                    except:
                        pass

                error_str = str(error_detail)
                if "offer_no_longer_available" in error_str or "price_changed" in error_str:
                    response_text = "⚠️ *Tarifa expirada*\n\n"
                    response_text += "Esa oferta ya no está disponible (el precio cambió o se agotó).\n"
                    response_text += "Por favor busca el vuelo nuevamente para obtener el precio actualizado."
                elif "insufficient_balance" in error_str.lower():
                    response_text = "💰 *Balance insuficiente*\n\n"
                    response_text += "No hay fondos suficientes para completar esta reserva.\n"
                    response_text += "El administrador debe agregar fondos en Duffel."
                elif "passenger" in error_str.lower() or "invalid" in error_str.lower():
                    response_text = "⚠️ *Error de datos*\n\n"
                    response_text += "La aerolínea rechazó la reserva por un problema con tus datos.\n\n"
                    response_text += "Escribe *registrar* para verificar y actualizar tu información."
                else:
                    response_text = "❌ *Error en la reserva*\n\n"
                    response_text += "Hubo un problema procesando tu solicitud.\n"
                    response_text += "Por favor intenta buscar y reservar nuevamente."


            # For Duffel bookings, show post-booking action buttons
            if provider and provider.upper() == "DUFFEL" and session.get("last_booking", {}).get("duffel_order_id"):
                send_interactive_message(from_number, response_text,
                    ["Elegir asiento", "Agregar maleta", "Ver itinerario"])
            else:
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
            import requests
            from sqlalchemy import text

            # Extract PNR from message
            words = incoming_msg.split()
            pnr = words[-1].upper()  # Assume PNR is last word

            # If user wrote "cancelar vuelo/viaje/reserva/mi" etc., show their trips instead
            _non_pnr_words = ['VUELO', 'VIAJE', 'RESERVA', 'MI', 'MIS', 'RESERVACION', 'BOLETO', 'TICKET', 'VUELOS', 'VIAJES']
            if pnr in _non_pnr_words:
                _uid = session.get("user_id", f"whatsapp_{from_number}")
                with engine.connect() as conn:
                    _user_trips = conn.execute(
                        text("SELECT booking_reference, departure_city, arrival_city, status FROM trips WHERE user_id = :uid AND status != 'CANCELLED' ORDER BY departure_date DESC NULLS LAST LIMIT 5"),
                        {"uid": _uid}
                    ).fetchall()
                if _user_trips:
                    response_text = "*¿Cuál reserva quieres cancelar?*\n\n"
                    for _t in _user_trips:
                        _route = f"{_t[1] or '?'} → {_t[2] or '?'}"
                        response_text += f"• *{_t[0]}* — {_route}\n"
                    response_text += "\nEscribe: *cancelar [PNR]*"
                else:
                    response_text = "No tienes reservas activas para cancelar."
                send_whatsapp_message(from_number, response_text)
                return {"status": "ok"}

            # Look up trip using raw SQL
            with engine.connect() as conn:
                trip_row = conn.execute(
                    text("SELECT booking_reference, user_id, provider_source, status, duffel_order_id FROM trips WHERE booking_reference = :pnr AND user_id = :uid"),
                    {"pnr": pnr, "uid": session.get("user_id", f"whatsapp_{from_number}")}
                ).fetchone()

            if not trip_row:
                response_text = f"❌ No encontré reserva con PNR: {pnr}"
            elif trip_row[3] == "CANCELLED":
                response_text = f"ℹ️ La reserva {pnr} ya está cancelada"
            else:
                provider_source = trip_row[2]
                duffel_order_id = trip_row[4]

                # Cancel with Duffel if it's a Duffel booking (2-step process)
                if provider_source == "DUFFEL" and duffel_order_id:
                    try:
                        token = os.getenv("DUFFEL_ACCESS_TOKEN")
                        duffel_headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Accept-Encoding": "gzip",
                            "Duffel-Version": "v2"
                        }

                        # Step 1: Create cancellation request (gets quote)
                        cancel_url = "https://api.duffel.com/air/order_cancellations"
                        cancel_data = {"data": {"order_id": duffel_order_id}}
                        resp1 = requests.post(cancel_url, json=cancel_data, headers=duffel_headers)

                        if resp1.status_code in [200, 201]:
                            cancellation = resp1.json()["data"]
                            cancellation_id = cancellation["id"]
                            refund_amount = cancellation.get("refund_amount", "0")
                            refund_currency = cancellation.get("refund_currency", "USD")

                            # Step 2: Confirm the cancellation
                            confirm_url = f"https://api.duffel.com/air/order_cancellations/{cancellation_id}/actions/confirm"
                            resp2 = requests.post(confirm_url, headers=duffel_headers)

                            if resp2.status_code in [200, 201]:
                                # Update DB via raw SQL
                                with engine.connect() as conn:
                                    conn.execute(
                                        text("UPDATE trips SET status = 'CANCELLED', refund_amount = :refund WHERE booking_reference = :pnr"),
                                        {"refund": float(refund_amount), "pnr": pnr}
                                    )
                                    conn.commit()
                                response_text = f"✅ Reserva {pnr} cancelada exitosamente\n\nReembolso: ${refund_amount} {refund_currency}"
                            else:
                                print(f"❌ Cancel confirm failed: {resp2.status_code} - {resp2.text[:300]}")
                                response_text = f"❌ No se pudo confirmar la cancelación de {pnr}.\n\nIntenta de nuevo o contacta soporte."
                        else:
                            # Parse Duffel error for user-friendly message
                            print(f"❌ Cancel request failed: {resp1.status_code} - {resp1.text[:300]}")
                            try:
                                err_data = resp1.json().get("errors", [{}])
                                err_code = err_data[0].get("code", "") if err_data else ""
                                err_type = err_data[0].get("type", "") if err_data else ""
                            except Exception:
                                err_code = ""
                                err_type = ""

                            if "not_found" in err_type or resp1.status_code == 404:
                                response_text = f"❌ No se encontró la orden para {pnr} en Duffel.\n\nEs posible que ya haya sido cancelada o que el vuelo ya paso."
                            elif "already_cancelled" in err_code:
                                response_text = f"ℹ️ La reserva {pnr} ya fue cancelada anteriormente."
                                # Also update local DB
                                with engine.connect() as conn:
                                    conn.execute(text("UPDATE trips SET status = 'CANCELLED' WHERE booking_reference = :pnr"), {"pnr": pnr})
                                    conn.commit()
                            else:
                                response_text = f"❌ No se pudo cancelar {pnr}.\n\nIntenta de nuevo en unos minutos."
                    except Exception as e:
                        print(f"❌ Cancel exception: {e}")
                        response_text = f"❌ Hubo un error al cancelar {pnr}.\n\nIntenta de nuevo o contacta soporte."
                else:
                    # Non-Duffel booking: just mark as cancelled in DB via raw SQL
                    with engine.connect() as conn:
                        conn.execute(
                            text("UPDATE trips SET status = 'CANCELLED' WHERE booking_reference = :pnr"),
                            {"pnr": pnr}
                        )
                        conn.commit()
                    response_text = f"✅ Reserva {pnr} cancelada"

            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # ===== HOTEL SEARCH - DIRECT HANDLER =====
        hotel_keywords = ['hotel', 'hospedaje', 'alojamiento', 'habitación', 'donde quedarme']
        if any(keyword in msg_lower for keyword in hotel_keywords):
            from app.services.hotel_engine import HotelEngine
            from app.utils.date_parser import SmartDateParser

            # Extract city
            city = None
            for pattern in ['en ', 'in ']:
                if pattern in msg_lower:
                    parts = msg_lower.split(pattern)
                    if len(parts) > 1:
                        # Get words after pattern, skip date words
                        words = parts[1].split()
                        for word in words:
                            if word not in ['del', 'el', 'la', 'los', 'las', 'de', 'al', 'para', 'checkin', 'checkout'] and len(word) > 2:
                                city = word.replace(',', '').replace('.', '')
                                break
                        if city:
                            break

            if not city:
                send_whatsapp_message(from_number, "🏨 ¿En qué ciudad buscas hotel?\nEjemplo: hotel en cancun del 20 al 23 febrero")
                return {"status": "ok"}

            # Parse dates from message
            checkin, checkout = SmartDateParser.parse_date_range(incoming_msg)

            if not checkin or not checkout:
                # Store city and ask for dates
                session["pending_hotel_search"] = {"city": city}
                session_manager.save_session(from_number, session)
                send_whatsapp_message(from_number, f"🏨 Buscando en *{city.title()}*\n\n📅 ¿Cuáles son las fechas?\nEjemplo: del 20 al 23 de febrero")
                return {"status": "ok"}

            # Search hotels
            hotel_engine = HotelEngine()
            hotels = hotel_engine.search_hotels(city=city, checkin=checkin, checkout=checkout)

            if hotels:
                session["pending_hotels"] = hotels[:5]
                session["hotel_dates"] = {"checkin": checkin, "checkout": checkout}
                session_manager.save_session(from_number, session)

                response_text = f"🏨 *Hoteles en {city.title()}*\n📅 {checkin} al {checkout}\n\n"
                for i, h in enumerate(hotels[:5], 1):
                    name = h.get('name', 'N/A')[:35]
                    price = h.get('price', 'N/A')
                    response_text += f"{i}. {name} - ${price}/noche\n"
                response_text += "\n📩 Responde con el número para ver detalles"
            else:
                response_text = f"😔 No encontré hoteles en {city.title()} para esas fechas."

            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}

        # # Legacy handler (commented out)
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
                response_text = "❌ Hubo un error al buscar hoteles.\n\nIntenta de nuevo en unos minutos."
            
            send_whatsapp_message(from_number, response_text)
            return {"status": "ok"}
        
        # Ayuda
        msg_lower = incoming_msg.lower().strip()
        
        # EMERGENCY RESET COMMAND
        if msg_lower in ["reset", "reiniciar", "borrar", "limpiar"]:
            # Clear session
            session_manager.delete_session(from_number)

            # Also clear registration_step with RAW SQL (ORM doesn't commit properly)
            try:
                from app.db.database import engine as reset_engine
                from sqlalchemy import text as reset_text
                user_id = session.get("user_id")
                if user_id:
                    with reset_engine.connect() as conn:
                        conn.execute(reset_text("UPDATE profiles SET registration_step = NULL WHERE user_id = :uid"), {"uid": user_id})
                        conn.commit()
                        print(f"🔄 EMERGENCY RESET: cleared registration_step for {user_id}")
            except Exception as e:
                print(f"❌ EMERGENCY RESET error: {e}")

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
        is_equipaje_command = msg_lower.strip() in ['equipaje', 'maletas', 'baggage', 'maleta', 'mi equipaje', 'agregar maleta']
        if is_equipaje_command and not has_pending_search:
            from app.services.baggage_service import BaggageService
            from app.services.itinerary_service import ItineraryService

            baggage_service = BaggageService(db)
            itinerary_service = ItineraryService(db)

            user_id = session.get("user_id", f"whatsapp_{from_number}")

            # Check last_booking first (just booked a flight)
            last_booking = session.get("last_booking", {})
            bag_order_id = last_booking.get("duffel_order_id")
            bag_pnr = last_booking.get("pnr", "")

            if not bag_order_id:
                # Fall back to upcoming trip
                upcoming = itinerary_service.get_upcoming_trip(user_id)
                if upcoming and upcoming.get("success"):
                    bag_order_id = upcoming.get("duffel_order_id")
                    bag_pnr = upcoming.get("booking_reference", "")

            if bag_order_id:
                baggage_data = baggage_service.get_baggage_options(bag_order_id)
                response = baggage_service.format_baggage_for_whatsapp(baggage_data)

                # If there are purchasable options, store in session for selection
                available = baggage_data.get("available_options", [])
                if available:
                    session["pending_baggage"] = {
                        "order_id": bag_order_id,
                        "pnr": bag_pnr,
                        "options": available[:5]
                    }
                    session_manager.save_session(from_number, session)
                    response += "\n\n_Responde con el número para agregar_"

                send_whatsapp_message(from_number, response)
            else:
                send_whatsapp_message(from_number, "No tienes viajes próximos.\n\nBusca un vuelo para ver opciones de equipaje.")

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
                    # Extract real airline code from trip segments
                    airline_code = "XX"
                    departure_time_iso = upcoming.get("flight", {}).get("departure_date", "")
                    segments = upcoming.get("segments", [])
                    if segments:
                        flight_num = segments[0].get("flight_number", "")
                        if flight_num and len(flight_num) >= 2:
                            airline_code = flight_num[:2]  # e.g. "BA1234" -> "BA"
                        # Use segment departure time (more precise than date)
                        seg_dep = segments[0].get("departure_time", "")
                        if seg_dep:
                            departure_time_iso = seg_dep

                    result = checkin_service.schedule_auto_checkin(
                        user_id=user_id,
                        trip_id=pnr,
                        airline_code=airline_code,
                        pnr=pnr,
                        passenger_last_name=profile.legal_last_name,
                        departure_time=departure_time_iso
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

        # ASIENTOS / SEAT SELECTION (post-booking flow)
        if msg_lower.strip() in ['asientos', 'seleccionar asiento', 'mapa de asientos', 'seats', 'elegir asiento']:
            from app.services.seat_selection_service import SeatSelectionService

            seat_service = SeatSelectionService()

            # Check for post-booking seat selection (last_booking has order_id)
            last_booking = session.get("last_booking", {})
            offer_id = last_booking.get("offer_id")
            order_id = last_booking.get("duffel_order_id")
            booking_pnr = last_booking.get("pnr", "")

            if not offer_id:
                # Fall back to selected flight (pre-booking)
                if session.get("selected_flight"):
                    offer_id = session["selected_flight"].get("offer_id")

            if not offer_id:
                # Try to find from upcoming trip
                from app.services.itinerary_service import ItineraryService
                itinerary_service = ItineraryService(db)
                user_id = session.get("user_id", f"whatsapp_{from_number}")
                upcoming = itinerary_service.get_upcoming_trip(user_id)
                if upcoming and upcoming.get("success"):
                    order_id = upcoming.get("duffel_order_id")
                    booking_pnr = upcoming.get("booking_reference", "")

            if offer_id:
                # Strip DUFFEL:: prefix if present
                clean_offer = offer_id.split("::")[1] if "::" in offer_id else offer_id
                seat_map = await seat_service.get_seat_map(clean_offer)
                response = seat_service.format_seat_map_for_whatsapp(seat_map)

                # Store state for seat code handler
                if order_id and not seat_map.get("error"):
                    session["pending_seat_selection"] = {
                        "order_id": order_id,
                        "seat_map": seat_map,
                        "pnr": booking_pnr
                    }
                    session_manager.save_session(from_number, session)
            else:
                response = "*Selección de asiento*\n\nNo encontré un vuelo reciente. Reserva un vuelo primero."

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
                    response = f"✅ {result['message']}\n\nPrograma: {result['program']}\nNúmero: {result['number']}\n\n_Se aplicara automaticamente al buscar y reservar vuelos._"
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
                        print(f"❌ Refund quote error: {e}")
                        response = "❌ No pude cotizar el reembolso.\n\nIntenta de nuevo en unos minutos."
                else:
                    response = "No encontré el ID de la orden para cotizar."
            else:
                response = "No tienes viajes próximos para cotizar reembolso."

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # CAMBIAR VUELO
        if any(kw in msg_lower for kw in ['cambiar vuelo', 'cambiar fecha', 'modificar vuelo', 'change flight']):
            import requests as _requests
            user_id = session.get("user_id", f"whatsapp_{from_number}")
            # Clear any previous change state
            session.pop("pending_change", None)
            session.pop("pending_change_offers", None)

            # Get user's trip from DB
            from app.services.itinerary_service import ItineraryService
            itinerary_service = ItineraryService(db)
            upcoming = itinerary_service.get_upcoming_trip(user_id)

            if upcoming and upcoming.get("success"):
                order_id = upcoming.get("duffel_order_id")
                pnr = upcoming.get("booking_reference")
                flight = upcoming.get("flight", {})
                dep_city = flight.get("departure_city", "???")
                arr_city = flight.get("arrival_city", "???")

                # Fetch slices from Duffel for accurate info
                slices_info = []
                if order_id:
                    try:
                        token = os.getenv("DUFFEL_ACCESS_TOKEN")
                        duffel_headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Accept-Encoding": "gzip",
                            "Duffel-Version": "v2"
                        }
                        order_resp = _requests.get(f"https://api.duffel.com/air/orders/{order_id}", headers=duffel_headers)
                        if order_resp.status_code == 200:
                            order_data = order_resp.json()["data"]
                            for s in order_data.get("slices", []):
                                origin_data = s.get("origin", {})
                                dest_data = s.get("destination", {})
                                orig_code = origin_data.get("iata_code", "") if isinstance(origin_data, dict) else str(origin_data)
                                dest_code = dest_data.get("iata_code", "") if isinstance(dest_data, dict) else str(dest_data)
                                # Get first segment for flight info
                                segs = s.get("segments", [])
                                flight_info = ""
                                dep_date = ""
                                if segs:
                                    first_seg = segs[0]
                                    carrier = first_seg.get("marketing_carrier", {})
                                    carrier_code = carrier.get("iata_code", "") if isinstance(carrier, dict) else ""
                                    flight_num = first_seg.get("marketing_carrier_flight_number", "")
                                    dep_at = first_seg.get("departing_at", "")
                                    dep_date = dep_at[:10] if dep_at else ""
                                    dep_time = dep_at[11:16] if len(dep_at) > 16 else ""
                                    flight_info = f"{carrier_code} {flight_num} {dep_time}"
                                slices_info.append({
                                    "id": s["id"],
                                    "origin": orig_code,
                                    "destination": dest_code,
                                    "date": dep_date,
                                    "flight_info": flight_info
                                })
                    except Exception as e:
                        print(f"Error fetching Duffel slices: {e}")

                response = f"*Cambiar vuelo*\n\nPNR: {pnr}\n"

                if len(slices_info) > 1:
                    # Round trip or multi-leg - let user choose which slice to change
                    response += "Selecciona qué vuelo cambiar:\n\n"
                    for idx, sl in enumerate(slices_info):
                        response += f"*{idx + 1}.* {sl['origin']} → {sl['destination']} | {sl['date']} | {sl['flight_info']}\n"
                    response += "\nEnvía el número del vuelo que quieres cambiar."
                    session["pending_change"] = {
                        "pnr": pnr,
                        "order_id": order_id,
                        "slices": slices_info,
                        "awaiting_slice_selection": True
                    }
                elif len(slices_info) == 1:
                    # Single slice - show it and ask for date
                    sl = slices_info[0]
                    response += f"Vuelo: {sl['origin']} → {sl['destination']} | {sl['date']} | {sl['flight_info']}\n\n"
                    response += "Escribe la nueva fecha:\n"
                    response += "Ejemplo: cambiar 25 marzo"
                    session["pending_change"] = {
                        "pnr": pnr,
                        "order_id": order_id,
                        "selected_slice": slices_info[0]
                    }
                else:
                    response += f"Vuelo: {dep_city} → {arr_city}\n\n"
                    response += "Escribe la nueva fecha:\n"
                    response += "Ejemplo: cambiar 25 marzo"
                    session["pending_change"] = {
                        "pnr": pnr,
                        "order_id": order_id
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

        # CONFIRMAR HOLD - Create held order after user confirmed
        if msg_lower.strip() in ['confirmar hold', 'confirmar reserva sin pagar', 'si hold'] and session.get("pending_hold"):
            from app.services.hold_order_service import HoldOrderService

            hold_service = HoldOrderService()
            selected = session.get("selected_flight", {})
            offer_id = selected.get("offer_id")

            if not offer_id:
                send_whatsapp_message(from_number, "❌ No hay vuelo seleccionado. Busca un vuelo primero.")
                session.pop("pending_hold", None)
                session_manager.save_session(from_number, session)
                return {"status": "ok"}

            # Build passenger from profile (same as booking flow)
            user_id = session.get("user_id", f"whatsapp_{from_number}")
            from sqlalchemy import text
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT user_id, legal_first_name, legal_last_name, email, dob, gender, phone_number FROM profiles WHERE user_id = :uid"),
                    {"uid": user_id}
                ).fetchone()

            if not row or not row[1] or not row[4]:
                send_whatsapp_message(from_number, "❌ Perfil incompleto. Escribe 'registrar' para completar tus datos.")
                session.pop("pending_hold", None)
                session_manager.save_session(from_number, session)
                return {"status": "ok"}

            # Get passenger_id from offer
            passenger_id = selected.get("passenger_id") or selected.get("metadata", {}).get("passenger_id", "")

            passengers = [{
                "id": passenger_id,
                "type": "adult",
                "given_name": row[1],
                "family_name": row[2] or row[1],
                "email": row[3] or f"{from_number}@whatsapp.temp",
                "born_on": str(row[4]),
                "gender": "m" if str(row[5]).lower() in ['m', 'male', 'masculino'] else "f",
                "phone_number": f"+{row[6] or from_number}",
                "title": "mr" if str(row[5]).lower() in ['m', 'male', 'masculino'] else "ms"
            }]

            result = await hold_service.create_hold_order(offer_id, passengers)

            if result.get("success"):
                # Save held order in session
                session["held_order"] = {
                    "order_id": result["order_id"],
                    "pnr": result.get("booking_reference"),
                    "amount": result.get("total_amount"),
                    "currency": result.get("total_currency"),
                    "payment_required_by": result.get("payment_required_by"),
                }

                # Save to DB as PENDING trip
                try:
                    segments = selected.get("segments", [])
                    dep_city = segments[0].get("departure_iata", "") if segments else ""
                    arr_city = segments[-1].get("arrival_iata", "") if segments else ""
                    dep_date = segments[0].get("departure_time", "")[:10] if segments else ""

                    with engine.connect() as conn:
                        conn.execute(text(
                            "INSERT INTO trips (booking_reference, user_id, status, departure_city, arrival_city, "
                            "departure_date, total_amount, duffel_order_id) VALUES (:pnr, :uid, 'PENDING', :dep, :arr, :date, :amt, :oid)"
                        ), {
                            "pnr": result.get("booking_reference", ""),
                            "uid": user_id,
                            "dep": dep_city,
                            "arr": arr_city,
                            "date": dep_date,
                            "amt": float(result.get("total_amount", 0)),
                            "oid": result["order_id"]
                        })
                        conn.commit()
                except Exception as db_err:
                    print(f"⚠️ Hold trip DB save failed (non-critical): {db_err}")

                response = hold_service.format_hold_for_whatsapp(result)
            else:
                response = f"❌ {result.get('error', 'No se pudo apartar el vuelo')}"

            session.pop("pending_hold", None)
            session.pop("selected_flight", None)
            session.pop("pending_flights", None)
            session_manager.save_session(from_number, session)
            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # PAGAR - Pay for a held order
        if msg_lower.strip() in ['pagar', 'pagar vuelo', 'pagar reserva', 'completar pago']:
            from app.services.hold_order_service import HoldOrderService

            hold_service = HoldOrderService()
            held = session.get("held_order", {})
            order_id = held.get("order_id")

            if not order_id:
                # Try to find held order from DB
                user_id = session.get("user_id", f"whatsapp_{from_number}")
                from sqlalchemy import text
                try:
                    with engine.connect() as conn:
                        row = conn.execute(
                            text("SELECT duffel_order_id, booking_reference, total_amount FROM trips WHERE user_id = :uid AND status = 'PENDING' ORDER BY id DESC LIMIT 1"),
                            {"uid": user_id}
                        ).fetchone()
                        if row:
                            order_id = row[0]
                            held = {"order_id": row[0], "pnr": row[1], "amount": row[2]}
                except Exception:
                    pass

            if not order_id:
                send_whatsapp_message(from_number, "No tienes reservas pendientes de pago.\n\nBusca un vuelo y usa 'reservar sin pagar' para apartar.")
                return {"status": "ok"}

            send_whatsapp_message(from_number, "💳 Procesando pago...")

            result = await hold_service.pay_held_order(order_id)

            if result.get("success"):
                # Update trip status to CONFIRMED
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text("UPDATE trips SET status = 'CONFIRMED' WHERE duffel_order_id = :oid"),
                            {"oid": order_id}
                        )
                        conn.commit()
                except Exception as db_err:
                    print(f"⚠️ Trip status update failed: {db_err}")

                # Save as last_booking for post-booking flows
                session["last_booking"] = {
                    "duffel_order_id": order_id,
                    "pnr": result.get("booking_reference", held.get("pnr", "")),
                }
                session.pop("held_order", None)
                session_manager.save_session(from_number, session)

                response = hold_service.format_payment_for_whatsapp(result)

                # Send email + WhatsApp notification
                try:
                    from app.services.push_notification_service import PushNotificationService
                    push_svc = PushNotificationService()
                    pnr = result.get("booking_reference", "")
                    amount = float(result.get("amount_paid", 0))
                    currency = result.get("currency", "USD")
                    import asyncio
                    asyncio.ensure_future(push_svc.send_booking_confirmation(
                        from_number, pnr, held.get("route", ""), "", amount, currency
                    ))
                except Exception:
                    pass
            else:
                if result.get("price_changed"):
                    response = "⚠️ El precio cambio desde que apartaste el vuelo.\n\nIntenta de nuevo con 'pagar'."
                else:
                    response = f"❌ {result.get('error', 'Error de pago')}"

            send_whatsapp_message(from_number, response)
            return {"status": "ok"}

        # RESERVAR SIN PAGAR / HOLD - Check if offer is holdable
        if any(kw in msg_lower for kw in ['reservar sin pagar', 'apartar vuelo', 'guardar vuelo', 'apartar']):
            from app.services.hold_order_service import HoldOrderService

            hold_service = HoldOrderService()

            if session.get("selected_flight"):
                offer_id = session["selected_flight"].get("offer_id")
                if offer_id:
                    hold_check = await hold_service.check_hold_availability(offer_id)

                    if hold_check.get("available"):
                        hours = hold_check.get('hold_hours', 24)
                        has_guarantee = hold_check.get('has_price_guarantee', False)

                        response = f"✅ *Este vuelo permite apartar sin pagar*\n\n"
                        response += f"Tienes hasta *{hours} horas* para pagar.\n"
                        if has_guarantee:
                            response += "El precio esta garantizado.\n\n"
                        else:
                            response += "⚠️ El precio puede cambiar antes de pagar.\n\n"
                        response += "Responde *confirmar hold* para apartar."

                        session["pending_hold"] = True
                        session_manager.save_session(from_number, session)
                    else:
                        response = f"❌ {hold_check.get('message', 'Este vuelo requiere pago inmediato.')}"
                else:
                    response = "No pude verificar el vuelo seleccionado."
            else:
                response = "Primero selecciona un vuelo para apartar.\n\nBusca un vuelo y elige uno con numero."

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
        # Get last booking info for context references like "same dates"
        last_booking = session.get("last_booking", {})

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
            # Context for "same dates" / "same destination" references
            "last_booking": last_booking,
            "last_booking_dates": last_booking.get("dates") if last_booking else None,
            "last_booking_destination": last_booking.get("destination") if last_booking else None,
        }

        response_message = await agent.chat(session["messages"], "", session_context)
        
        if response_message.tool_calls:
            session["messages"].append(response_message.model_dump())
            session_manager.save_session(from_number, session)  # Save after AI response
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                tool_result = None

                # DEBUG: Log what arguments AI is passing
                print(f"🔍 AI TOOL CALL: {function_name}")
                print(f"🔍 AI ARGUMENTS: {json.dumps(arguments, indent=2)}")

                if function_name == "search_hybrid_flights":
                    # Get filters from AI arguments
                    time_filter = arguments.get("time_of_day", "ANY")
                    cabin_filter = arguments.get("cabin", "ECONOMY")
                    airline_filter = arguments.get("airline")

                    # CRITICAL FALLBACK: If AI didn't detect filters, parse from user message
                    if time_filter == "ANY":
                        detected_time = detect_time_of_day_from_text(incoming_msg)
                        if detected_time != "ANY":
                            print(f"🔧 FALLBACK: AI missed time_of_day, detected '{detected_time}' from message")
                            time_filter = detected_time

                    if cabin_filter == "ECONOMY":
                        detected_cabin = detect_cabin_from_text(incoming_msg)
                        if detected_cabin != "ECONOMY":
                            print(f"🔧 FALLBACK: AI missed cabin, detected '{detected_cabin}' from message")
                            cabin_filter = detected_cabin

                    print(f"⚠️ FLIGHT SEARCH FILTERS - time_of_day={time_filter}, cabin={cabin_filter}, airline={airline_filter}")

                    tool_result = await flight_aggregator.search_hybrid_flights(
                        arguments["origin"],
                        arguments["destination"],
                        arguments["date"],
                        arguments.get("return_date"),
                        cabin_filter,
                        airline_filter,
                        time_filter,
                        arguments.get("passengers", 1),  # num_passengers
                        user_id=session.get("user_id")  # Pass user_id for loyalty programme in search
                    )
                    tool_result = [f.dict() for f in tool_result]

                    if tool_result:
                        session["pending_flights"] = tool_result[:5]
                        # Clear any leftover change state from previous flow
                        session.pop("pending_change", None)
                        session.pop("pending_change_offers", None)
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
                        # Clear any leftover change state from previous flow
                        session.pop("pending_change", None)
                        session.pop("pending_change_offers", None)
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
                    # Tell AI NOT to invent data - results will be shown by format_for_whatsapp
                    compact_result = f"Found {len(tool_result)} results. DO NOT list prices or times - they will be shown automatically. Just say a brief intro like 'Aquí están las opciones:' or 'Encontré X vuelos disponibles:'"
                else:
                    compact_result = json.dumps(tool_result, default=str)[:500]  # Limit size

                session["messages"].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": compact_result
                })
                session_manager.save_session(from_number, session)  # Save after tool result

            # If we have pending flights/hotels, use simple intro instead of AI-generated response
            if session.get("pending_flights") or session.get("pending_hotels"):
                # Don't let AI invent data - just use a simple intro
                if session.get("pending_flights"):
                    response_text = f"Encontré {len(session['pending_flights'])} vuelos disponibles:"
                else:
                    response_text = f"Encontré {len(session['pending_hotels'])} hoteles disponibles:"
            else:
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
                error_msg += "Por favor intenta de nuevo en unos segundos."
                send_whatsapp_message(from_number, error_msg)
        except:
            pass  # Don't fail if we can't send the error message

        # ALWAYS return 200 to prevent WhatsApp from retrying endlessly
        return JSONResponse(status_code=200, content={"status": "error", "message": str(e)})

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
        flight_list = "\n\n✈️ *Vuelos encontrados:*\n🔄 _Solo vuelos con cambio permitido_\n\n"

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

                # Header with price and change conditions
                metadata = flight.get("metadata") or {}
                change_tag = ""
                if metadata.get("changeable"):
                    penalty = metadata.get("change_penalty")
                    if penalty and float(penalty) > 0:
                        change_tag = f"🔄 Cambio: ${penalty}"
                    else:
                        change_tag = "🔄 Cambio gratis"
                refund_tag = "✅ Reembolsable" if refundable else ""
                tags = " ".join(t for t in [change_tag, refund_tag] if t)
                flight_list += f"━━━━━━━━━━━━━━━━━━━━\n"
                flight_list += f"*{i}. ${price} USD* {tags}\n"

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
