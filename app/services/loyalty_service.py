"""
Loyalty Programs Service - Manage frequent flyer numbers and earn miles
"""

import os
import httpx
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.models import LoyaltyProgram


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
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
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
                existing.program_number = member_number
                if tier:
                    existing.tier_level = tier
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
                    program_number=member_number,
                    tier_level=tier
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
                "program_name": self.PROGRAMS.get(p.airline_code, {}).get("name", f"{p.airline_code} Program"),
                "member_number": p.program_number,
                "tier": p.tier_level,
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
                "member_number": program.program_number,
                "program_name": self.PROGRAMS.get(program.airline_code, {}).get("name", f"{program.airline_code} Program")
            }
        return None

    def delete_loyalty(self, user_id: str, airline_code: str) -> Dict:
        """Remove a loyalty program"""
        program = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.user_id == user_id,
            LoyaltyProgram.airline_code == airline_code.upper()
        ).first()

        if program:
            program_name = self.PROGRAMS.get(program.airline_code, {}).get("name", program.airline_code)
            self.db.delete(program)
            self.db.commit()
            return {"success": True, "message": f"Programa {program_name} eliminado"}

        return {"success": False, "error": "Programa no encontrado"}

    async def update_offer_with_loyalty(self, offer_id: str, passenger_id: str, user_id: str) -> Dict:
        """
        Per Duffel docs: PATCH /air/offers/{offer_id}/passengers/{passenger_id}
        Updates an offer's passenger with loyalty_programme_accounts before booking.
        This is Flow 2 from docs - apply loyalty after search but before booking.
        """
        try:
            import httpx

            # Get user's loyalty programs
            programs = self.db.query(LoyaltyProgram).filter(
                LoyaltyProgram.user_id == user_id
            ).all()

            if not programs:
                return {"success": False, "message": "No tienes programas de viajero frecuente registrados."}

            # Get user profile for name (required by Duffel)
            from app.models.models import Profile
            profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()
            if not profile:
                return {"success": False, "error": "Perfil no encontrado"}

            # Build loyalty accounts list
            loyalty_accounts = [{
                "airline_iata_code": p.airline_code,
                "account_number": p.program_number
            } for p in programs]

            url = f"{self.base_url}/air/offers/{offer_id}/passengers/{passenger_id}"
            payload = {
                "data": {
                    "given_name": profile.legal_first_name,
                    "family_name": profile.legal_last_name,
                    "loyalty_programme_accounts": loyalty_accounts
                }
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.patch(url, headers=self.headers, json=payload)

                if response.status_code == 200:
                    print(f"✈️ Updated offer {offer_id} passenger with {len(loyalty_accounts)} loyalty programs")
                    return {
                        "success": True,
                        "message": f"Millas aplicadas al vuelo ({len(loyalty_accounts)} programas)",
                        "programs_applied": [p.airline_code for p in programs]
                    }
                else:
                    error_data = response.json()
                    errors = error_data.get("errors", [{}])
                    error_msg = errors[0].get("message", "Error al aplicar millas") if errors else "Error desconocido"
                    print(f"❌ Loyalty PATCH failed: {error_msg}")
                    return {"success": False, "error": error_msg}

        except Exception as e:
            print(f"Error updating offer with loyalty: {e}")
            return {"success": False, "error": str(e)}

    async def apply_loyalty_to_booking(self, order_id: str, loyalty_number: str, airline_code: str) -> Dict:
        """
        Loyalty cannot be added after booking per Duffel.
        It's automatically included at search time and booking time.
        """
        return {
            "success": False,
            "message": "Tus millas se aplican automaticamente al buscar y reservar. Ya estan guardadas para futuras reservas."
        }

    def format_for_whatsapp(self, programs: List[Dict]) -> str:
        """Format loyalty programs for WhatsApp"""
        if not programs:
            return "*Mis programas de viajero frecuente*\n\nNo tienes programas registrados.\n\nPara agregar: 'agregar millas AM 123456789'\n\n_Al agregar tus millas, se aplican automaticamente al buscar vuelos para obtener mejores precios._"

        msg = "*Mis programas de viajero frecuente*\n\n"

        for p in programs:
            tier_str = f" ({p['tier']})" if p.get('tier') else ""
            msg += f"✈️ *{p['airline']}*\n"
            msg += f"   {p['program_name']}{tier_str}\n"
            msg += f"   Número: {p['member_number']}\n\n"

        msg += "✅ _Se aplican automaticamente al buscar y reservar._\n\n"
        msg += "_Para agregar: 'agregar millas [aerolínea] [número]'_\n"
        msg += "_Para eliminar: 'eliminar millas [aerolínea]'_"

        return msg
