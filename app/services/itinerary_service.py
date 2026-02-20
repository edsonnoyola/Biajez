"""
Itinerary Service - Combines flight + hotel data for complete trip view
Enriched with Duffel API data
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.models import Trip, Profile, TripStatusEnum


class ItineraryService:
    """Service for generating complete trip itineraries"""

    def __init__(self, db: Session):
        self.db = db

    def get_user_itineraries(self, user_id: str, include_past: bool = False) -> List[Dict]:
        """
        Get all itineraries for a user

        Args:
            user_id: User ID
            include_past: Include past trips

        Returns:
            List of itinerary summaries
        """
        query = self.db.query(Trip).filter(Trip.user_id == user_id)

        if not include_past:
            # Only include non-cancelled and future trips
            query = query.filter(Trip.status != TripStatusEnum.CANCELLED)
            today = datetime.now().date()
            query = query.filter(
                (Trip.departure_date >= today) | (Trip.departure_date == None)
            )

        trips = query.order_by(Trip.departure_date.asc()).all()

        return [self._format_trip_summary(trip) for trip in trips]

    def get_trip_itinerary(self, pnr: str, user_id: str = None) -> Dict:
        """
        Get detailed itinerary for a specific trip

        Args:
            pnr: Booking reference
            user_id: Optional user ID for verification

        Returns:
            Dict with complete trip details (enriched from Duffel if available)
        """
        query = self.db.query(Trip).filter(Trip.booking_reference == pnr)

        if user_id:
            query = query.filter(Trip.user_id == user_id)

        trip = query.first()

        if not trip:
            return {"success": False, "error": "Trip not found"}

        # Get user profile for passenger info
        profile = self.db.query(Profile).filter(Profile.user_id == trip.user_id).first()

        # Base itinerary from database
        itinerary = {
            "success": True,
            "booking_reference": trip.booking_reference,
            "status": trip.status.value if trip.status else "UNKNOWN",
            "provider": trip.provider_source.value if trip.provider_source else "UNKNOWN",
            "total_amount": float(trip.total_amount) if trip.total_amount else 0,

            # Flight details
            "flight": {
                "departure_city": trip.departure_city,
                "arrival_city": trip.arrival_city,
                "departure_date": trip.departure_date.isoformat() if trip.departure_date else None,
                "return_date": trip.return_date.isoformat() if trip.return_date else None,
            },

            # Check-in info
            "checkin": {
                "status": trip.checkin_status,
                "boarding_pass_url": trip.boarding_pass_url
            },

            # Documents
            "documents": {
                "ticket_url": trip.ticket_url,
                "invoice_url": trip.invoice_url
            },

            # Passenger info
            "passenger": {
                "name": f"{profile.legal_first_name} {profile.legal_last_name}" if profile else "Unknown",
                "email": profile.email if profile else None,
                "phone": profile.phone_number if profile else None
            } if profile else None,

            # Baggage
            "baggage": json.loads(trip.baggage_services) if trip.baggage_services else [],

            # Metadata
            "duffel_order_id": trip.duffel_order_id,
            "confirmed_at": trip.confirmed_at
        }

        # Enrich with Duffel data if available
        if trip.duffel_order_id:
            duffel_data = self._get_duffel_order_details(trip.duffel_order_id)
            if duffel_data:
                itinerary["segments"] = duffel_data.get("segments", [])
                itinerary["passengers"] = duffel_data.get("passengers", [])
                itinerary["conditions"] = duffel_data.get("conditions", {})

        return itinerary

    def _get_duffel_order_details(self, order_id: str) -> Optional[Dict]:
        """Fetch order details from Duffel API"""
        import os
        import requests

        try:
            duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
            if not duffel_token:
                return None

            headers = {
                "Authorization": f"Bearer {duffel_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "Duffel-Version": "v2"
            }

            response = requests.get(
                f"https://api.duffel.com/air/orders/{order_id}",
                headers=headers,
                timeout=15
            )

            if response.status_code != 200:
                return None

            order_data = response.json()["data"]

            # Extract segments
            segments = []
            for slice_data in order_data.get("slices", []):
                for segment in slice_data.get("segments", []):
                    segments.append({
                        "origin": segment.get("origin", {}).get("iata_code"),
                        "destination": segment.get("destination", {}).get("iata_code"),
                        "departure_time": segment.get("departing_at"),
                        "arrival_time": segment.get("arriving_at"),
                        "flight_number": f"{segment.get('marketing_carrier', {}).get('iata_code', '')}{segment.get('marketing_carrier_flight_number', '')}",
                        "aircraft": segment.get("aircraft", {}).get("name"),
                        "duration": segment.get("duration")
                    })

            # Extract passengers
            passengers = [{
                "name": f"{p.get('given_name', '')} {p.get('family_name', '')}",
                "type": p.get("type")
            } for p in order_data.get("passengers", [])]

            # Extract conditions (may be None)
            conditions = order_data.get("conditions") or {}
            refund_info = conditions.get("refund_before_departure") or {}
            change_info = conditions.get("change_before_departure") or {}

            return {
                "segments": segments,
                "passengers": passengers,
                "conditions": {
                    "refundable": refund_info.get("allowed", False),
                    "changeable": change_info.get("allowed", False)
                }
            }

        except Exception as e:
            print(f"Error fetching Duffel order: {e}")
            return None

    def get_upcoming_trip(self, user_id: str) -> Optional[Dict]:
        """Get the next upcoming trip for a user"""
        today = datetime.now().date()

        trip = self.db.query(Trip).filter(
            Trip.user_id == user_id,
            Trip.status != TripStatusEnum.CANCELLED,
            Trip.departure_date >= today
        ).order_by(Trip.departure_date.asc()).first()

        if not trip:
            return None

        return self.get_trip_itinerary(trip.booking_reference, user_id)

    def _format_trip_summary(self, trip: Trip) -> Dict:
        """Format a trip as a summary"""
        return {
            "booking_reference": trip.booking_reference,
            "route": f"{trip.departure_city or 'Unknown'} → {trip.arrival_city or 'Unknown'}",
            "departure_date": trip.departure_date.isoformat() if trip.departure_date else None,
            "return_date": trip.return_date.isoformat() if trip.return_date else None,
            "status": trip.status.value if trip.status else "UNKNOWN",
            "total_amount": float(trip.total_amount) if trip.total_amount else 0,
            "checkin_status": trip.checkin_status
        }

    def format_itinerary_for_whatsapp(self, itinerary: Dict) -> str:
        """Format detailed itinerary for WhatsApp - concise Spanish version"""
        if not itinerary.get("success"):
            return f"No encontre ese viaje.\n\nEscribe 'mis viajes' para ver tus reservas."

        lines = []

        # Header with route
        flight = itinerary.get("flight", {})
        dep_city = flight.get("departure_city", "???")
        arr_city = flight.get("arrival_city", "???")
        lines.append(f"*{dep_city} → {arr_city}*")

        # Segments from Duffel (if available)
        segments = itinerary.get("segments", [])
        if segments:
            for seg in segments:
                flight_num = seg.get("flight_number", "")
                dep_time = seg.get("departure_time", "")
                if dep_time:
                    # Format: "12 Feb 18:05"
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(dep_time.replace("Z", ""))
                        formatted = dt.strftime("%d %b %H:%M")
                        lines.append(f"{flight_num} | {formatted}")
                    except:
                        lines.append(f"{flight_num}")
        else:
            dep_date = flight.get("departure_date", "")
            if dep_date:
                lines.append(f"{dep_date}")

        # Passenger & PNR
        passenger = itinerary.get("passenger")
        if passenger:
            lines.append(f"{passenger.get('name', '')}")
        lines.append(f"PNR: {itinerary['booking_reference']}")

        # Status icons
        status = itinerary.get("status", "")
        checkin = itinerary.get("checkin", {})
        checkin_status = checkin.get("status", "NOT_CHECKED_IN")

        status_line = []
        if status == "TICKETED":
            status_line.append("Confirmado")
        elif status == "CANCELLED":
            status_line.append("Cancelado")

        if checkin_status == "CHECKED_IN":
            status_line.append("Check-in listo")

        if status_line:
            lines.append(" | ".join(status_line))

        # Price
        lines.append(f"${itinerary['total_amount']:.0f} USD")

        return "\n".join(lines)

    def format_itinerary_buttons(self, itinerary: Dict) -> list:
        """Get interactive buttons for itinerary"""
        buttons = []

        checkin = itinerary.get("checkin", {})
        if checkin.get("status") != "CHECKED_IN":
            buttons.append({"id": "btn_checkin", "title": "Check-in"})

        buttons.append({"id": "btn_equipaje", "title": "Equipaje"})

        if len(buttons) < 3:
            buttons.append({"id": "btn_ayuda", "title": "Ayuda"})

        return buttons

    def format_itineraries_list_for_whatsapp(self, itineraries: List[Dict]) -> str:
        """Format list of itineraries for WhatsApp - concise Spanish"""
        if not itineraries:
            return "No tienes viajes proximos.\n\nBusca un vuelo para comenzar."

        lines = ["*Tus viajes*\n"]

        for i, trip in enumerate(itineraries[:5], 1):
            route = trip.get('route', '???')
            dep_date = trip.get('departure_date', '')
            pnr = trip.get('booking_reference', '')

            # Format date nicely
            if dep_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(dep_date)
                    dep_date = dt.strftime("%d %b")
                except:
                    pass

            lines.append(f"{i}. {route}")
            lines.append(f"   {dep_date} | {pnr}")

        if len(itineraries) > 5:
            lines.append(f"\n+{len(itineraries) - 5} viajes mas")

        return "\n".join(lines)
