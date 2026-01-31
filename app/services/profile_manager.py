"""
Profile Manager Service
Manages executive traveler profiles and preferences
"""
from sqlalchemy.orm import Session
from app.models.models import Profile, LoyaltyProgram
from datetime import datetime, date
import uuid


def normalize_phone(phone: str) -> str:
    """Normalize Mexican phone number to 52 + 10 digits"""
    phone = phone.replace("+", "").replace(" ", "").strip()
    if phone.startswith("521") and len(phone) == 13:
        return "52" + phone[3:]
    return phone


def get_or_create_profile(db: Session, phone_number: str) -> Profile:
    """
    Get existing profile by phone number or create a new one with defaults.
    Returns the Profile object.
    """
    normalized = normalize_phone(phone_number)
    
    # Try to find existing profile
    profile = db.query(Profile).filter(
        (Profile.phone_number == normalized) | 
        (Profile.phone_number == phone_number)
    ).first()
    
    if profile:
        return profile
    
    # Create new profile with minimal required data
    profile = Profile(
        user_id=str(uuid.uuid4()),
        legal_first_name="Usuario",
        legal_last_name="WhatsApp",
        dob=date(1990, 1, 1),  # Default DOB
        gender="M",
        passport_number="PENDING",
        passport_expiry=date(2030, 1, 1),
        passport_country="MX",
        phone_number=normalized,
        seat_preference="ANY",
        flight_class_preference="ECONOMY",
        hotel_preference="4_STAR"
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return profile


def update_preference(db: Session, phone_number: str, field: str, value: str) -> bool:
    """
    Update a specific preference field for a user.
    Returns True if successful, False otherwise.
    """
    profile = get_or_create_profile(db, phone_number)
    
    valid_fields = {
        "seat_preference": ["WINDOW", "AISLE", "MIDDLE", "ANY"],
        "flight_class_preference": ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"],
        "hotel_preference": ["3_STAR", "4_STAR", "5_STAR"],
        "preferred_airline": None,  # Any IATA code
        "baggage_preference": ["CARRY_ON", "CHECKED_1", "CHECKED_2"]
    }
    
    if field not in valid_fields:
        return False
    
    # Validate value if there are constraints
    if valid_fields[field] and value.upper() not in valid_fields[field]:
        return False
    
    setattr(profile, field, value.upper())
    db.commit()
    return True


def get_preferences_summary(db: Session, phone_number: str) -> str:
    """
    Get a formatted summary of user preferences for display in WhatsApp.
    """
    profile = get_or_create_profile(db, phone_number)
    
    # Build summary
    seat_icons = {"WINDOW": "🪟", "AISLE": "🚶", "MIDDLE": "👤", "ANY": "✨"}
    class_icons = {"ECONOMY": "💺", "PREMIUM_ECONOMY": "💺✨", "BUSINESS": "🛋️", "FIRST": "👑"}
    hotel_icons = {"3_STAR": "⭐⭐⭐", "4_STAR": "⭐⭐⭐⭐", "5_STAR": "⭐⭐⭐⭐⭐"}
    
    seat = profile.seat_preference or "ANY"
    flight_class = profile.flight_class_preference or "ECONOMY"
    hotel = profile.hotel_preference or "4_STAR"
    airline = profile.preferred_airline or "Cualquiera"
    
    summary = f"""👤 *Tu Perfil Ejecutivo*

✈️ *Preferencias de Vuelo*
{seat_icons.get(seat, '✨')} Asiento: {seat.replace('_', ' ').title()}
{class_icons.get(flight_class, '💺')} Clase: {flight_class.replace('_', ' ').title()}
🛫 Aerolínea: {airline}

🏨 *Preferencias de Hotel*
{hotel_icons.get(hotel, '⭐⭐⭐⭐')} Categoría: {hotel.replace('_', ' ')}

📧 Email: {profile.email or 'No configurado'}
📱 Teléfono: {profile.phone_number}

_Escribe "cambiar asiento ventana" o "cambiar clase business" para actualizar._"""
    
    return summary


def add_loyalty_program(db: Session, phone_number: str, airline_code: str, program_number: str) -> bool:
    """
    Add a loyalty program to the user's profile.
    """
    profile = get_or_create_profile(db, phone_number)
    
    # Check if already exists
    existing = db.query(LoyaltyProgram).filter(
        LoyaltyProgram.user_id == profile.user_id,
        LoyaltyProgram.airline_code == airline_code.upper()
    ).first()
    
    if existing:
        existing.program_number = program_number
        db.commit()
        return True
    
    # Create new
    program = LoyaltyProgram(
        user_id=profile.user_id,
        airline_code=airline_code.upper(),
        program_number=program_number
    )
    db.add(program)
    db.commit()
    return True


def get_loyalty_programs(db: Session, phone_number: str) -> list:
    """
    Get all loyalty programs for a user.
    """
    profile = get_or_create_profile(db, phone_number)
    return db.query(LoyaltyProgram).filter(
        LoyaltyProgram.user_id == profile.user_id
    ).all()
