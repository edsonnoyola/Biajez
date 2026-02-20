"""
Check-in Service - Handles automatic and manual check-in for flights
"""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.models import Trip, AutoCheckin, Profile, CheckinStatusEnum, Notification
import uuid


class CheckinService:
    """Service for managing flight check-ins"""

    # Check-in window (most airlines open 24h before departure)
    CHECKIN_WINDOW_HOURS = 24

    # Airlines with API check-in support (expand as needed)
    SUPPORTED_AIRLINES = {
        "AM": "Aeromexico",
        "AA": "American Airlines",
        "UA": "United Airlines",
        "DL": "Delta Air Lines",
        "BA": "British Airways",
        "IB": "Iberia"
    }

    def __init__(self, db: Session):
        self.db = db
        self.duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")

    def schedule_auto_checkin(
        self,
        user_id: str,
        trip_id: str,
        airline_code: str,
        pnr: str,
        passenger_last_name: str,
        departure_time: str
    ) -> Dict:
        """
        Schedule automatic check-in for a flight

        Args:
            user_id: User ID
            trip_id: Trip booking reference
            airline_code: Airline IATA code
            pnr: PNR/confirmation number
            passenger_last_name: Passenger's last name
            departure_time: ISO format departure time

        Returns:
            Dict with scheduling result
        """
        try:
            # Parse departure time
            dep_time = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))

            # Calculate check-in time (24h before, minus 1 minute for safety)
            checkin_time = dep_time - timedelta(hours=self.CHECKIN_WINDOW_HOURS, minutes=1)

            # Don't schedule if check-in window has passed
            if checkin_time < datetime.now(dep_time.tzinfo or None):
                return {
                    "success": False,
                    "error": "La ventana de check-in ya abrio. Haz check-in directamente en la aerolinea."
                }

            # Check for existing auto check-in
            existing = self.db.query(AutoCheckin).filter(
                AutoCheckin.trip_id == trip_id,
                AutoCheckin.status.in_([CheckinStatusEnum.PENDING, CheckinStatusEnum.SCHEDULED])
            ).first()

            if existing:
                return {
                    "success": True,
                    "checkin_id": existing.id,
                    "message": "Ya tienes recordatorio de check-in programado",
                    "scheduled_time": existing.scheduled_time
                }

            # Create auto check-in record
            auto_checkin = AutoCheckin(
                id=f"aci_{str(uuid.uuid4())[:20]}",
                user_id=user_id,
                trip_id=trip_id,
                airline_code=airline_code.upper(),
                pnr=pnr,
                passenger_last_name=passenger_last_name,
                scheduled_time=checkin_time.isoformat(),
                status=CheckinStatusEnum.SCHEDULED,
                created_at=datetime.utcnow().isoformat()
            )

            self.db.add(auto_checkin)
            self.db.commit()

            return {
                "success": True,
                "checkin_id": auto_checkin.id,
                "message": f"Recordatorio de check-in programado para {checkin_time.strftime('%d/%m %H:%M')}",
                "scheduled_time": checkin_time.isoformat(),
                "airline": self.SUPPORTED_AIRLINES.get(airline_code.upper(), airline_code)
            }

        except Exception as e:
            print(f"Error scheduling auto check-in: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_checkin_status(self, trip_id: str) -> Dict:
        """Get check-in status for a trip"""
        trip = self.db.query(Trip).filter(Trip.booking_reference == trip_id).first()

        if not trip:
            return {"success": False, "error": "No encontré ese viaje"}

        auto_checkin = self.db.query(AutoCheckin).filter(
            AutoCheckin.trip_id == trip_id
        ).first()

        result = {
            "success": True,
            "trip_id": trip_id,
            "checkin_status": trip.checkin_status,
            "boarding_pass_url": trip.boarding_pass_url
        }

        if auto_checkin:
            result["auto_checkin"] = {
                "id": auto_checkin.id,
                "scheduled_time": auto_checkin.scheduled_time,
                "status": auto_checkin.status.value,
                "error_message": auto_checkin.error_message
            }

        return result

    async def process_pending_checkins(self) -> Dict:
        """
        Process all pending auto check-ins that are due
        Called by scheduler every 15 minutes
        """
        now = datetime.utcnow()

        # Find check-ins that are due
        pending = self.db.query(AutoCheckin).filter(
            AutoCheckin.status == CheckinStatusEnum.SCHEDULED,
            AutoCheckin.scheduled_time <= now.isoformat()
        ).all()

        print(f"Processing {len(pending)} pending check-ins...")

        processed = 0
        successful = 0

        for checkin in pending:
            try:
                checkin.status = CheckinStatusEnum.IN_PROGRESS
                self.db.commit()

                result = await self._execute_checkin(checkin)

                if result.get("success"):
                    checkin.status = CheckinStatusEnum.COMPLETED
                    checkin.checkin_result = json.dumps(result)
                    successful += 1

                    # Update trip status
                    trip = self.db.query(Trip).filter(
                        Trip.booking_reference == checkin.trip_id
                    ).first()
                    if trip:
                        trip.checkin_status = "CHECKED_IN"
                        if result.get("boarding_pass_url"):
                            trip.boarding_pass_url = result["boarding_pass_url"]

                    # Notify user
                    await self._notify_checkin_success(checkin, result)
                else:
                    checkin.status = CheckinStatusEnum.FAILED
                    checkin.error_message = result.get("error", "Unknown error")

                    # Notify user of failure
                    await self._notify_checkin_failure(checkin, result.get("error"))

                checkin.processed_at = datetime.utcnow().isoformat()
                processed += 1

            except Exception as e:
                print(f"Error processing check-in {checkin.id}: {e}")
                checkin.status = CheckinStatusEnum.FAILED
                checkin.error_message = str(e)

        self.db.commit()

        return {
            "processed": processed,
            "successful": successful,
            "failed": processed - successful
        }

    async def _execute_checkin(self, checkin: AutoCheckin) -> Dict:
        """
        Execute the actual check-in via Duffel API

        Duffel provides order management - we use their API to get
        check-in information and airline deep links
        """
        trip = self.db.query(Trip).filter(
            Trip.booking_reference == checkin.trip_id
        ).first()

        if not trip or not trip.duffel_order_id:
            return {
                "success": False,
                "error": "No encontré el viaje o no es una reserva de Duffel"
            }

        return await self._checkin_via_duffel(trip.duffel_order_id, checkin)

    async def _checkin_via_duffel(self, order_id: str, checkin: AutoCheckin) -> Dict:
        """
        Check-in via Duffel API

        Uses Duffel's order endpoint to get airline check-in URLs
        and booking details for check-in
        """
        import requests

        try:
            # Get order details from Duffel
            url = f"https://api.duffel.com/air/orders/{order_id}"
            headers = {
                "Authorization": f"Bearer {self.duffel_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "Duffel-Version": "v2"
            }

            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                print(f"❌ Duffel order fetch for checkin failed: {response.status_code} - {response.text[:300]}")
                return {
                    "success": False,
                    "error": "No se pudo obtener la información del vuelo desde Duffel"
                }

            order_data = response.json()["data"]

            # Extract airline and booking info
            slices = order_data.get("slices", [])
            if not slices:
                return {"success": False, "error": "No se encontraron segmentos de vuelo"}

            first_segment = slices[0].get("segments", [{}])[0]
            airline_code = first_segment.get("operating_carrier", {}).get("iata_code", checkin.airline_code)
            booking_reference = order_data.get("booking_reference")

            # Get passengers with seat assignments
            passengers = order_data.get("passengers", [])
            seat_assignments = []

            for slice_data in slices:
                for segment in slice_data.get("segments", []):
                    for pax in segment.get("passengers", []):
                        seat = pax.get("seat", {})
                        if seat:
                            seat_assignments.append({
                                "passenger": pax.get("passenger_id"),
                                "seat": seat.get("designator"),
                                "segment": f"{segment.get('origin', {}).get('iata_code')}-{segment.get('destination', {}).get('iata_code')}"
                            })

            # Build airline check-in URL
            airline_checkin_urls = {
                "AM": "https://aeromexico.com/es-mx/check-in",
                "AA": "https://www.aa.com/reservation/flightCheckInViewReservationsAccess.do",
                "UA": "https://www.united.com/en/us/checkin",
                "DL": "https://www.delta.com/mytrips/",
                "BA": "https://www.britishairways.com/travel/olcilandingpagealiast/public/en_gb",
                "IB": "https://www.iberia.com/es/check-in/",
                "AF": "https://www.airfrance.com/check-in",
                "LH": "https://www.lufthansa.com/online-check-in"
            }

            checkin_url = airline_checkin_urls.get(
                airline_code.upper(),
                f"https://www.{airline_code.lower()}.com/checkin"
            )

            return {
                "success": True,
                "message": "Información de check-in obtenida",
                "order_id": order_id,
                "booking_reference": booking_reference,
                "airline": airline_code,
                "checkin_url": checkin_url,
                "seat_assignments": seat_assignments,
                "passengers": [p.get("given_name", "") + " " + p.get("family_name", "") for p in passengers],
                "note": f"Usa tu PNR {booking_reference} para hacer check-in en {checkin_url}"
            }

        except Exception as e:
            print(f"Duffel check-in error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _notify_checkin_success(self, checkin: AutoCheckin, result: Dict) -> None:
        """Notify user that check-in window is open with airline link"""
        from app.services.push_notification_service import PushNotificationService

        checkin_url = result.get("checkin_url", "")
        airline = result.get("airline", checkin.airline_code)

        # Create notification
        notification = Notification(
            id=f"not_{str(uuid.uuid4())[:20]}",
            user_id=checkin.user_id,
            type="checkin_reminder",
            title="Check-in disponible",
            message=f"Ya puedes hacer check-in para {checkin.pnr}",
            read=0,
            action_required=1,
            created_at=datetime.utcnow().isoformat(),
            extra_data=json.dumps(result)
        )

        self.db.add(notification)
        self.db.commit()

        # Send WhatsApp with check-in link
        profile = self.db.query(Profile).filter(Profile.user_id == checkin.user_id).first()
        if profile and profile.phone_number:
            push_service = PushNotificationService()
            await push_service.send_checkin_reminder(
                phone_number=profile.phone_number,
                pnr=checkin.pnr,
                airline=airline,
                checkin_url=checkin_url
            )

    async def _notify_checkin_failure(self, checkin: AutoCheckin, error: str) -> None:
        """Notify user of check-in failure"""
        from app.services.push_notification_service import PushNotificationService

        notification = Notification(
            id=f"not_{str(uuid.uuid4())[:20]}",
            user_id=checkin.user_id,
            type="checkin_failed",
            title="Check-in no disponible",
            message=f"No se pudo hacer check-in para {checkin.pnr}. Hazlo directamente en la aerolínea.",
            read=0,
            action_required=1,
            created_at=datetime.utcnow().isoformat()
        )

        self.db.add(notification)
        self.db.commit()

        print(f"❌ Check-in failed for {checkin.pnr}: {error}")

        profile = self.db.query(Profile).filter(Profile.user_id == checkin.user_id).first()
        if profile and profile.phone_number:
            push_service = PushNotificationService()

            # Build airline check-in URL if available
            airline_checkin_urls = {
                "AM": "https://aeromexico.com/es-mx/check-in",
                "AA": "https://www.aa.com/reservation/flightCheckInViewReservationsAccess.do",
                "UA": "https://www.united.com/en/us/checkin",
                "DL": "https://www.delta.com/mytrips/",
                "BA": "https://www.britishairways.com/travel/olcilandingpagealiast/public/en_gb",
                "IB": "https://www.iberia.com/es/check-in/",
            }
            checkin_url = airline_checkin_urls.get(checkin.airline_code.upper(), "")

            msg = f"⚠️ No pudimos hacer check-in automático para *{checkin.pnr}*.\n\n"
            msg += "Haz check-in directamente en la aerolínea:\n"
            if checkin_url:
                msg += f"{checkin_url}\n"
            msg += f"\nUsa tu PNR: *{checkin.pnr}*"

            await push_service.send_message(
                phone_number=profile.phone_number,
                message=msg
            )

    def format_status_for_whatsapp(self, status: Dict) -> str:
        """Format check-in status for WhatsApp - concise Spanish"""
        if not status.get("success"):
            return "No encontre ese vuelo.\n\nEscribe 'mis viajes' para ver tus reservas."

        lines = []
        pnr = status.get('trip_id', '')

        status_text = status.get("checkin_status", "NOT_CHECKED_IN")

        if status_text == "CHECKED_IN":
            lines.append("*Check-in completado*")
            lines.append(f"PNR: {pnr}")
            if status.get("boarding_pass_url"):
                lines.append("Pase de abordar listo")
        else:
            lines.append("*Check-in pendiente*")
            lines.append(f"PNR: {pnr}")

            if status.get("auto_checkin"):
                ac = status["auto_checkin"]
                ac_status = ac.get('status', '')

                if ac_status == "SCHEDULED":
                    # Parse and format time
                    scheduled = ac.get('scheduled_time', '')
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(scheduled)
                        formatted = dt.strftime("%d %b %H:%M")
                        lines.append(f"\nRecordatorio: {formatted}")
                        lines.append("Te enviare el link de check-in")
                    except:
                        lines.append(f"\nRecordatorio programado")
                elif ac_status == "FAILED":
                    lines.append("\nNo pude enviarte el recordatorio")
                elif ac_status == "COMPLETED":
                    lines.append("\nYa te envie el link de check-in")

        return "\n".join(lines)

    def format_checkin_buttons(self, status: Dict) -> list:
        """Get interactive buttons for check-in"""
        buttons = []

        status_text = status.get("checkin_status", "NOT_CHECKED_IN")

        if status_text != "CHECKED_IN":
            if not status.get("auto_checkin"):
                buttons.append({"id": "btn_recordatorio", "title": "Avisarme"})
            else:
                ac_status = status.get("auto_checkin", {}).get("status", "")
                if ac_status == "FAILED":
                    buttons.append({"id": "btn_retry_checkin", "title": "Reintentar"})

        buttons.append({"id": "btn_itinerario", "title": "Ver itinerario"})

        if len(buttons) < 3:
            buttons.append({"id": "btn_ayuda", "title": "Ayuda"})

        return buttons
