import uuid
from sqlalchemy import Column, String, Date, Enum, ForeignKey, Numeric, Integer, Text, DateTime, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.database import Base
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

# --- DTOs (Pydantic) ---
class FlightSegment(BaseModel):
    carrier_code: str
    flight_number: str
    departure_iata: str
    arrival_iata: str
    departure_time: datetime
    arrival_time: datetime
    duration: str

class AntigravityFlight(BaseModel):
    offer_id: str
    provider: str
    price: Decimal
    currency: str
    segments: List[FlightSegment]
    duration_total: str
    cabin_class: str
    refundable: bool = False
    metadata: Optional[Dict[str, Any]] = None
    score: float = 0.0

class GenderEnum(str, enum.Enum):
    M = "M"
    F = "F"
    X = "X"

class ProviderSourceEnum(str, enum.Enum):
    AMADEUS = "AMADEUS"
    DUFFEL = "DUFFEL"
    AMADEUS_HOTEL = "AMADEUS_HOTEL"

class TripStatusEnum(str, enum.Enum):
    TICKETED = "TICKETED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

class PaymentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"

class CreditTypeEnum(str, enum.Enum):
    ETICKET = "eticket"
    MCO = "mco"

class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    legal_first_name = Column(String, nullable=False)
    legal_last_name = Column(String, nullable=False)
    dob = Column(Date, nullable=False)
    gender = Column(Enum(GenderEnum), nullable=False)
    passport_number = Column(String, nullable=False) # Encrypted in application layer
    passport_expiry = Column(Date, nullable=False)
    passport_country = Column(String(2), nullable=False)
    known_traveler_number = Column(String, nullable=True)
    redress_number = Column(String, nullable=True)
    seat_preference = Column(String, default="ANY") # WINDOW, AISLE, MIDDLE, ANY
    seat_position_preference = Column(String, default="WINDOW") # TOP, MIDDLE, BOTTOM (for seat row position)
    baggage_preference = Column(String, default="CARRY_ON") # CARRY_ON, CHECKED_1, CHECKED_2
    hotel_preference = Column(String, default="4_STAR") # 3_STAR, 4_STAR, 5_STAR
    flight_class_preference = Column(String, default="ECONOMY") # ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST
    preferred_airline = Column(String, nullable=True) # IATA code (e.g., "AA", "DL", "AM")
    preferred_hotel_chains = Column(String, nullable=True) # Comma-separated (e.g., "Marriott,Hilton,Hyatt")
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    preferred_seats = Column(String, nullable=True) # Comma-separated list of 3 seats
    preferred_hotels = Column(String, nullable=True) # Comma-separated list of hotels
    registration_step = Column(String, nullable=True)  # Track registration progress: nombre, email, nacimiento, genero, pasaporte, etc.

    loyalty_programs = relationship("LoyaltyProgram", back_populates="user")

class LoyaltyProgram(Base):
    __tablename__ = "loyalty_programs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("profiles.user_id"), nullable=False)
    airline_code = Column(String, nullable=False)
    program_number = Column(String, nullable=False)
    tier_level = Column(String, nullable=True)

    user = relationship("Profile", back_populates="loyalty_programs")

class Trip(Base):
    __tablename__ = "trips"

    booking_reference = Column(String, primary_key=True) # PNR is unique
    user_id = Column(String, ForeignKey("profiles.user_id"), nullable=False)
    provider_source = Column(Enum(ProviderSourceEnum), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(TripStatusEnum), nullable=False)
    invoice_url = Column(String, nullable=True)
    
    # NEW: Order management fields
    duffel_order_id = Column(String, nullable=True)  # ord_0000... from Duffel
    refund_amount = Column(Numeric(10, 2), nullable=True)  # Refund if cancelled
    departure_city = Column(String, nullable=True)  # For order history display
    arrival_city = Column(String, nullable=True)
    departure_date = Column(Date, nullable=True)
    return_date = Column(Date, nullable=True)
    ticket_url = Column(String, nullable=True)  # Path to generated ticket
    trip_id = Column(String, nullable=True)  # Additional ID for tracking
    pnr_code = Column(String, nullable=True)  # Duplicate of booking_reference for convenience
    
    # Order change fields
    change_request_id = Column(String, nullable=True)  # ocr_0000... from Duffel
    change_penalty_amount = Column(Numeric(10, 2), nullable=True)  # Penalty for change
    previous_order_id = Column(String, nullable=True)  # Original order if this was changed
    
    # Booking confirmation timestamp (for Duffel Stays Go-Live compliance)
    confirmed_at = Column(String, nullable=True)  # ISO timestamp when booking was confirmed
    
    # Payment relationship
    payment_id = Column(String, ForeignKey("payments.id"), nullable=True)
    payment = relationship("Payment", back_populates="trip")

    # NEW: Baggage and check-in fields
    baggage_services = Column(Text, nullable=True)  # JSON of purchased baggage services
    checkin_status = Column(String, default='NOT_CHECKED_IN')  # NOT_CHECKED_IN, SCHEDULED, CHECKED_IN, FAILED
    boarding_pass_url = Column(String, nullable=True)  # URL to boarding pass PDF

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True)  # Stripe Payment Intent ID (pi_xxx)
    user_id = Column(String, ForeignKey("profiles.user_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(Enum(PaymentStatusEnum), default=PaymentStatusEnum.PENDING, nullable=False)
    
    # Stripe-specific fields
    stripe_customer_id = Column(String, nullable=True)  # cus_xxx for repeat customers
    payment_method_id = Column(String, nullable=True)  # pm_xxx
    client_secret = Column(String, nullable=True)  # For frontend confirmation
    
    # Booking context
    offer_id = Column(String, nullable=True)  # Flight offer being purchased
    provider = Column(String, nullable=True)  # DUFFEL, AMADEUS, etc.
    
    # Metadata
    error_message = Column(String, nullable=True)  # If payment failed
    created_at = Column(String, nullable=False)  # ISO timestamp
    updated_at = Column(String, nullable=True)  # ISO timestamp
    
    # Relationship
    trip = relationship("Trip", back_populates="payment", uselist=False)

class AirlineCredit(Base):
    __tablename__ = "airline_credits"
    
    id = Column(String, primary_key=True, default=lambda: f"acd_{str(uuid.uuid4())[:20]}")
    user_id = Column(String, ForeignKey("profiles.user_id"), nullable=False)
    airline_iata_code = Column(String(2), nullable=False)
    credit_amount = Column(Numeric(10, 2), nullable=False)
    credit_currency = Column(String(3), nullable=False)
    credit_code = Column(String, nullable=True)  # Airline's credit code
    credit_name = Column(String, nullable=True)  # e.g., "Future Flight Credit"
    expires_at = Column(String, nullable=True)  # ISO datetime
    spent_at = Column(String, nullable=True)  # ISO datetime when used
    invalidated_at = Column(String, nullable=True)  # ISO datetime if invalidated
    order_id = Column(String, nullable=True)  # Original order that generated credit
    passenger_id = Column(String, nullable=True)
    issued_on = Column(Date, nullable=False)  # Date credit was issued
    type = Column(Enum(CreditTypeEnum), nullable=False)  # eticket or mco
    created_at = Column(String, nullable=False)  # ISO datetime

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    event_data = Column(String, nullable=False)
    processed = Column(Integer, default=0)
    processed_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
    error_message = Column(String, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("profiles.user_id"), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    read = Column(Integer, default=0)
    action_required = Column(Integer, default=0)
    related_order_id = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
    extra_data = Column(Text, nullable=True)  # JSON for additional notification data

    profile = relationship("Profile")


# --- NEW TABLES FOR FEATURES 4-10 ---

class CheckinStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AutoCheckin(Base):
    """Auto check-in scheduling for trips"""
    __tablename__ = "auto_checkins"

    id = Column(String, primary_key=True, default=lambda: f"aci_{str(uuid.uuid4())[:20]}")
    user_id = Column(String, ForeignKey("profiles.user_id"), nullable=False)
    trip_id = Column(String, ForeignKey("trips.booking_reference"), nullable=False)
    airline_code = Column(String(2), nullable=False)  # IATA code
    pnr = Column(String, nullable=False)
    passenger_last_name = Column(String, nullable=False)  # Required for check-in
    scheduled_time = Column(String, nullable=False)  # ISO timestamp - when to attempt check-in
    status = Column(Enum(CheckinStatusEnum), default=CheckinStatusEnum.PENDING)
    checkin_result = Column(Text, nullable=True)  # JSON result from airline
    error_message = Column(String, nullable=True)
    processed_at = Column(String, nullable=True)  # ISO timestamp when processed
    created_at = Column(String, nullable=False)

    profile = relationship("Profile")
    trip = relationship("Trip")


class VisaRequirement(Base):
    """Cached visa requirements between countries"""
    __tablename__ = "visa_requirements"

    id = Column(String, primary_key=True, default=lambda: f"vr_{str(uuid.uuid4())[:20]}")
    passport_country = Column(String(2), nullable=False)  # ISO country code
    destination_country = Column(String(2), nullable=False)  # ISO country code
    visa_required = Column(Boolean, nullable=False)
    visa_on_arrival = Column(Boolean, default=False)
    e_visa_available = Column(Boolean, default=False)
    max_stay_days = Column(Integer, nullable=True)
    requirements_text = Column(Text, nullable=True)  # Detailed requirements
    notes = Column(Text, nullable=True)  # Additional notes
    last_updated = Column(String, nullable=False)  # ISO timestamp

    # Unique constraint on passport+destination
    __table_args__ = (
        {'extend_existing': True},
    )
