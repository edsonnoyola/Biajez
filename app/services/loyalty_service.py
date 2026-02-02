"""
Loyalty Programs Service - Manage frequent flyer numbers and earn miles
"""

import os
import httpx
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text
from app.db.database import Base
import json

class LoyaltyProgram(Base):
    """User loyalty program memberships"""
    __tablename__ = "loyalty_programs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    airline_code = Column(String)  # IATA code (AM, AA, UA, etc.)
    program_name = Column(String)  # Club Premier, AAdvantage, etc.
    member_number = Column(String)
    tier_status = Column(String)   # Gold, Platinum, etc.
    extra_data = Column(Text)      # JSON for additional data


class LoyaltyService:
    """Manage loyalty programs and apply to bookings"""

    # Known loyalty programs
    PROGRAMS = {
        "AM": {"name": "Club Premier", "airline": "Aeroméxico"},
        "AA": {"name": "AAdvantage", "airline": "American Airlines"},
        "UA": {"name": "MileagePlus", "airline": "United Airlines"},
        "DL": {"name": "SkyMiles", "airline": "Delta Air Lines"},
        "IB": {"name": "Iberia Plus", "airline": "Iberia"},
        "BA": {"name": "Executive Club", "airline": "British Airways"},
        "AF": {"name": "Flying Blue", "airline": "Air France"},
        "LH": {"name": "Miles & More", "airline": "Lufthansa"},
        "Y4": {"name": "V.Club", "airline": "Volaris"},
        "VB": {"name": "Viajero Frecuente", "airline": "VivaAerobus"},
    }

    def __init__(self, db: Session):
        self.db = db
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Duffel-Version": "v2"
        }

    def add_loyalty_number(self, user_id: str, airline_code: str, member_number: str, tier: str = None) -> Dict:
        """Add or update a loyalty program membership"""
        try:
            airline_code = airline_code.upper()
            program_info = self.PROGRAMS.get(airline_code, {"name": f"{airline_code} Program", "airline": airline_code})

            # Check if exists
            existing = self.db.query(LoyaltyProgram).filter(
                LoyaltyProgram.user_id == user_id,
                LoyaltyProgram.airline_code == airline_code
            ).first()

            if existing:
                existing.member_number = member_number
                if tier:
                    existing.tier_status = tier
                self.db.commit()
                return {
                    "success": True,
                    "message": f"Número de {program_info['name']} actualizado",
                    "program": program_info['name'],
                    "number": member_number
                }
            else:
                new_program = LoyaltyProgram(
                    user_id=user_id,
                    airline_code=airline_code,
                    program_name=program_info['name'],
                    member_number=member_number,
                    tier_status=tier
                )
                self.db.add(new_program)
                self.db.commit()
                return {
                    "success": True,
                    "message": f"Agregado a {program_info['name']}",
                    "program": program_info['name'],
                    "number": member_number
                }

        except Exception as e:
            print(f"Error adding loyalty: {e}")
            return {"success": False, "error": str(e)}

    def get_user_programs(self, user_id: str) -> List[Dict]:
        """Get all loyalty programs for a user"""
        programs = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.user_id == user_id
        ).all()

        return [
            {
                "airline_code": p.airline_code,
                "program_name": p.program_name,
                "member_number": p.member_number,
                "tier": p.tier_status,
                "airline": self.PROGRAMS.get(p.airline_code, {}).get("airline", p.airline_code)
            }
            for p in programs
        ]

    def get_loyalty_for_airline(self, user_id: str, airline_code: str) -> Optional[Dict]:
        """Get loyalty number for specific airline"""
        program = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.user_id == user_id,
            LoyaltyProgram.airline_code == airline_code.upper()
        ).first()

        if program:
            return {
                "airline_code": program.airline_code,
                "member_number": program.member_number,
                "program_name": program.program_name
            }
        return None

    def delete_loyalty(self, user_id: str, airline_code: str) -> Dict:
        """Remove a loyalty program"""
        program = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.user_id == user_id,
            LoyaltyProgram.airline_code == airline_code.upper()
        ).first()

        if program:
            self.db.delete(program)
            self.db.commit()
            return {"success": True, "message": f"Programa {program.program_name} eliminado"}

        return {"success": False, "error": "Programa no encontrado"}

    async def apply_loyalty_to_booking(self, order_id: str, loyalty_number: str, airline_code: str) -> Dict:
        """Apply loyalty number to an existing Duffel order"""
        try:
            # Duffel doesn't support adding loyalty after booking
            # This would need to be added during the booking process
            # For now, return info about this limitation
            return {
                "success": False,
                "message": "Los números de viajero frecuente deben agregarse antes de reservar. Tu número está guardado para futuras reservas."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def format_for_whatsapp(self, programs: List[Dict]) -> str:
        """Format loyalty programs for WhatsApp"""
        if not programs:
            return "*Mis programas de viajero frecuente*\n\nNo tienes programas registrados.\n\nPara agregar: 'agregar millas AM 123456789'"

        msg = "*Mis programas de viajero frecuente*\n\n"

        for p in programs:
            tier_str = f" ({p['tier']})" if p.get('tier') else ""
            msg += f"✈️ *{p['airline']}*\n"
            msg += f"   {p['program_name']}{tier_str}\n"
            msg += f"   Número: {p['member_number']}\n\n"

        msg += "_Para agregar: 'agregar millas [aerolínea] [número]'_\n"
        msg += "_Para eliminar: 'eliminar millas [aerolínea]'_"

        return msg
