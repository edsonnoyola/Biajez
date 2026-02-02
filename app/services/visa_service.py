"""
Visa Service - Check visa requirements between countries
Uses cached data + external APIs (Sherpa, VisaList, etc.)
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.models.models import VisaRequirement, Profile
import uuid


class VisaService:
    """Service for checking visa requirements"""

    # Common visa-free destinations for major passport holders
    # This is a simplified cache - in production, use Sherpa API or similar
    VISA_FREE_MAP = {
        "MX": {  # Mexican passport
            "visa_free": ["US", "CA", "GB", "ES", "FR", "DE", "IT", "JP", "BR", "AR", "CL", "PE", "CO"],
            "visa_on_arrival": ["TH", "ID", "MY", "TR"],
            "e_visa": ["IN", "AU", "NZ", "AE", "EG"]
        },
        "US": {  # US passport
            "visa_free": ["CA", "MX", "GB", "ES", "FR", "DE", "IT", "JP", "AU", "NZ", "BR", "AR", "CL", "TH", "MY", "ID"],
            "visa_on_arrival": ["TR", "EG", "JO"],
            "e_visa": ["IN", "AU", "VN", "KE"]
        },
        "ES": {  # Spanish passport (EU)
            "visa_free": ["US", "CA", "MX", "GB", "FR", "DE", "IT", "JP", "AU", "NZ", "BR", "AR", "CL", "TH", "MY", "ID"],
            "visa_on_arrival": ["TR", "EG", "JO"],
            "e_visa": ["IN", "AU", "VN"]
        }
    }

    # IATA to country code mapping
    IATA_TO_COUNTRY = {
        "MEX": "MX", "CUN": "MX", "GDL": "MX", "MTY": "MX",
        "JFK": "US", "LAX": "US", "ORD": "US", "MIA": "US", "SFO": "US",
        "MAD": "ES", "BCN": "ES",
        "LHR": "GB", "LGW": "GB",
        "CDG": "FR", "ORY": "FR",
        "FCO": "IT", "MXP": "IT",
        "FRA": "DE", "MUC": "DE",
        "NRT": "JP", "HND": "JP",
        "SYD": "AU", "MEL": "AU",
        "GRU": "BR", "GIG": "BR",
        "EZE": "AR",
        "SCL": "CL",
        "LIM": "PE",
        "BOG": "CO",
        "BKK": "TH",
        "SIN": "SG",
        "HKG": "HK",
        "DXB": "AE",
        "DEL": "IN", "BOM": "IN"
    }

    def __init__(self, db: Session):
        self.db = db
        self.sherpa_api_key = os.getenv("SHERPA_API_KEY")

    def check_visa_requirement(
        self,
        passport_country: str,
        destination: str,
        user_id: str = None
    ) -> Dict:
        """
        Check visa requirement for a destination

        Args:
            passport_country: 2-letter country code of passport
            destination: IATA airport code or country code
            user_id: Optional user ID to get passport from profile

        Returns:
            Dict with visa requirement info
        """
        # Normalize inputs
        passport_country = passport_country.upper()
        destination = destination.upper()

        # Convert IATA to country code if needed
        if len(destination) == 3:
            destination_country = self.IATA_TO_COUNTRY.get(destination, destination[:2])
        else:
            destination_country = destination

        # Check cache first
        cached = self.db.query(VisaRequirement).filter(
            VisaRequirement.passport_country == passport_country,
            VisaRequirement.destination_country == destination_country
        ).first()

        if cached:
            # Check if cache is still fresh (less than 30 days old)
            last_updated = datetime.fromisoformat(cached.last_updated)
            if (datetime.utcnow() - last_updated).days < 30:
                return self._format_cached_result(cached)

        # Try external API if available
        if self.sherpa_api_key:
            api_result = self._check_sherpa_api(passport_country, destination_country)
            if api_result.get("success"):
                self._cache_result(passport_country, destination_country, api_result)
                return api_result

        # Fall back to local map
        return self._check_local_map(passport_country, destination_country)

    def check_visa_for_user(self, user_id: str, destination: str) -> Dict:
        """Check visa requirements using user's passport country"""
        profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()

        if not profile or not profile.passport_country:
            return {
                "success": False,
                "error": "Please update your passport country in your profile."
            }

        return self.check_visa_requirement(
            passport_country=profile.passport_country,
            destination=destination,
            user_id=user_id
        )

    def _check_local_map(self, passport_country: str, destination_country: str) -> Dict:
        """Check against local visa-free map"""
        passport_info = self.VISA_FREE_MAP.get(passport_country, {})

        if destination_country in passport_info.get("visa_free", []):
            return {
                "success": True,
                "visa_required": False,
                "visa_on_arrival": False,
                "e_visa_available": False,
                "passport_country": passport_country,
                "destination_country": destination_country,
                "message": f"No visa required for {passport_country} passport holders visiting {destination_country}.",
                "max_stay_days": 90,
                "notes": "Tourist visits typically allow 90 days. Check official sources for current requirements."
            }
        elif destination_country in passport_info.get("visa_on_arrival", []):
            return {
                "success": True,
                "visa_required": True,
                "visa_on_arrival": True,
                "e_visa_available": False,
                "passport_country": passport_country,
                "destination_country": destination_country,
                "message": f"Visa on arrival available for {passport_country} passport holders in {destination_country}.",
                "notes": "Visa can be obtained at the airport upon arrival. Bring cash for visa fee."
            }
        elif destination_country in passport_info.get("e_visa", []):
            return {
                "success": True,
                "visa_required": True,
                "visa_on_arrival": False,
                "e_visa_available": True,
                "passport_country": passport_country,
                "destination_country": destination_country,
                "message": f"E-Visa required for {passport_country} passport holders visiting {destination_country}.",
                "notes": "Apply online before your trip. Processing typically takes 3-7 days."
            }
        else:
            return {
                "success": True,
                "visa_required": True,
                "visa_on_arrival": False,
                "e_visa_available": False,
                "passport_country": passport_country,
                "destination_country": destination_country,
                "message": f"Visa likely required for {passport_country} passport holders visiting {destination_country}.",
                "notes": "Please check with the embassy or consulate for specific requirements."
            }

    def _check_sherpa_api(self, passport_country: str, destination_country: str) -> Dict:
        """Check visa requirements via Sherpa API"""
        try:
            # Sherpa API endpoint (example - adjust to actual API)
            url = "https://api.joinsherpa.com/v2/entry-requirements"
            headers = {
                "Authorization": f"Bearer {self.sherpa_api_key}",
                "Content-Type": "application/json"
            }
            params = {
                "nationality": passport_country,
                "destination": destination_country
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Parse Sherpa response (adjust based on actual API format)
                return {
                    "success": True,
                    "visa_required": data.get("visa_required", True),
                    "visa_on_arrival": data.get("visa_on_arrival", False),
                    "e_visa_available": data.get("e_visa", False),
                    "passport_country": passport_country,
                    "destination_country": destination_country,
                    "message": data.get("summary", ""),
                    "requirements_text": data.get("requirements", ""),
                    "notes": data.get("notes", "")
                }

        except Exception as e:
            print(f"Sherpa API error: {e}")

        return {"success": False, "error": "API unavailable"}

    def _cache_result(self, passport_country: str, destination_country: str, result: Dict) -> None:
        """Cache visa requirement result"""
        existing = self.db.query(VisaRequirement).filter(
            VisaRequirement.passport_country == passport_country,
            VisaRequirement.destination_country == destination_country
        ).first()

        if existing:
            existing.visa_required = result.get("visa_required", True)
            existing.visa_on_arrival = result.get("visa_on_arrival", False)
            existing.e_visa_available = result.get("e_visa_available", False)
            existing.requirements_text = result.get("requirements_text")
            existing.notes = result.get("notes")
            existing.last_updated = datetime.utcnow().isoformat()
        else:
            visa_req = VisaRequirement(
                id=f"vr_{str(uuid.uuid4())[:20]}",
                passport_country=passport_country,
                destination_country=destination_country,
                visa_required=result.get("visa_required", True),
                visa_on_arrival=result.get("visa_on_arrival", False),
                e_visa_available=result.get("e_visa_available", False),
                max_stay_days=result.get("max_stay_days"),
                requirements_text=result.get("requirements_text"),
                notes=result.get("notes"),
                last_updated=datetime.utcnow().isoformat()
            )
            self.db.add(visa_req)

        self.db.commit()

    def _format_cached_result(self, cached: VisaRequirement) -> Dict:
        """Format cached result as response Dict"""
        return {
            "success": True,
            "visa_required": cached.visa_required,
            "visa_on_arrival": cached.visa_on_arrival,
            "e_visa_available": cached.e_visa_available,
            "passport_country": cached.passport_country,
            "destination_country": cached.destination_country,
            "max_stay_days": cached.max_stay_days,
            "requirements_text": cached.requirements_text,
            "notes": cached.notes,
            "cached": True
        }

    def format_visa_for_whatsapp(self, result: Dict) -> str:
        """Format visa requirements for WhatsApp - concise Spanish"""
        if not result.get("success"):
            return "No pude verificar visa.\n\nAsegurate de tener tu pasaporte en el perfil."

        dest = result.get('destination_country', '??')

        # Country names
        country_names = {
            "ES": "Espana", "US": "Estados Unidos", "FR": "Francia",
            "DE": "Alemania", "IT": "Italia", "GB": "Reino Unido",
            "JP": "Japon", "BR": "Brasil", "AR": "Argentina",
            "IN": "India", "TR": "Turquia", "AU": "Australia",
            "TH": "Tailandia", "MX": "Mexico"
        }
        dest_name = country_names.get(dest, dest)

        lines = [f"*Visa para {dest_name}*\n"]

        if not result.get("visa_required"):
            lines.append("No necesitas visa")
            if result.get("max_stay_days"):
                lines.append(f"Estancia max: {result['max_stay_days']} dias")
        elif result.get("visa_on_arrival"):
            lines.append("Visa al llegar")
            lines.append("La tramitas en el aeropuerto")
        elif result.get("e_visa_available"):
            lines.append("Requiere e-Visa")
            lines.append("Tramitala online antes de viajar")
        else:
            lines.append("Requiere visa")
            lines.append("Contacta la embajada")

        lines.append("\n_Verifica en fuentes oficiales_")

        return "\n".join(lines)

    def format_visa_buttons(self, result: Dict) -> list:
        """Get interactive buttons for visa check"""
        buttons = []

        buttons.append({"id": "btn_itinerario", "title": "Ver itinerario"})
        buttons.append({"id": "btn_ayuda", "title": "Ayuda"})

        return buttons
