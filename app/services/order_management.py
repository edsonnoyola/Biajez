import os
import requests
from sqlalchemy.orm import Session
from app.models.models import Trip, TripStatusEnum
from fastapi import HTTPException

class OrderManager:
    """Manages Duffel order operations: view, cancel, modify"""
    
    def __init__(self, db: Session):
        self.db = db
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Duffel-Version": "v2"
        }
    
    def get_order_details(self, order_id: str):
        """
        Retrieve full order details from Duffel
        
        Args:
            order_id: Duffel order ID (e.g., ord_0000...)
            
        Returns:
            dict: Full order object with segments, passengers, etc.
        """
        url = f"{self.base_url}/air/orders/{order_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()["data"]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching order {order_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch order: {str(e)}")
    
    def get_cancellation_quote(self, order_id: str):
        """
        Get refund quote before cancelling
        
        Args:
            order_id: Duffel order ID
            
        Returns:
            dict: Refund amount and currency
        """
        url = f"{self.base_url}/air/order_cancellations"
        payload = {
            "data": {
                "order_id": order_id
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            cancellation = response.json()["data"]
            
            return {
                "refund_amount": cancellation.get("refund_amount"),
                "refund_currency": cancellation.get("refund_currency"),
                "cancellation_id": cancellation["id"],
                "expires_at": cancellation.get("expires_at")
            }
        except requests.exceptions.RequestException as e:
            print(f"Error getting cancellation quote for {order_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get refund quote: {str(e)}")
    
    def cancel_order(self, order_id: str, user_id: str):
        """
        Cancel order and process refund

        Args:
            order_id: Duffel order ID
            user_id: User ID to verify ownership

        Returns:
            dict: Cancellation confirmation with refund details
        """
        from app.db.database import engine
        from sqlalchemy import text

        # 1. Verify order belongs to user (raw SQL)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT booking_reference, status FROM trips WHERE duffel_order_id = :oid AND user_id = :uid"),
                {"oid": order_id, "uid": user_id}
            ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found or unauthorized")

        if row[1] == "CANCELLED":
            raise HTTPException(status_code=400, detail="Order already cancelled")

        pnr = row[0]

        # 2. Get cancellation quote first
        quote = self.get_cancellation_quote(order_id)

        # 3. Confirm cancellation
        url = f"{self.base_url}/air/order_cancellations/{quote['cancellation_id']}/actions/confirm"

        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            confirmed = response.json()["data"]

            # 4. Update database via raw SQL
            refund_amount = float(confirmed.get("refund_amount", 0))
            with engine.connect() as conn:
                conn.execute(
                    text("UPDATE trips SET status = 'CANCELLED', refund_amount = :refund WHERE booking_reference = :pnr"),
                    {"refund": refund_amount, "pnr": pnr}
                )
                conn.commit()
            print(f"✅ Order {order_id} cancelled, refund: ${refund_amount}")

            # 5. Create airline credit if there's a refund amount
            credit_id = None
            if refund_amount > 0:
                try:
                    from app.services.airline_credits_service import AirlineCreditsService
                    credits_service = AirlineCreditsService(self.db)

                    credit = credits_service.create_credit(
                        user_id=user_id,
                        airline_iata_code="XX",
                        amount=refund_amount,
                        currency=confirmed.get("refund_currency", "USD"),
                        order_id=order_id,
                        expires_days=365
                    )
                    credit_id = credit["id"]
                    print(f"✅ Created airline credit: {credit_id} for ${refund_amount}")
                except Exception as credit_err:
                    print(f"⚠️ Could not create airline credit: {credit_err}")

            # 6. Send cancellation email
            try:
                from app.services.email_service import EmailService
                from app.models.models import Profile
                profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()
                if profile and profile.email and "@whatsapp.temp" not in profile.email:
                    # Get trip details for email
                    with engine.connect() as conn:
                        trip_row = conn.execute(
                            text("SELECT departure_city, arrival_city FROM trips WHERE booking_reference = :pnr"),
                            {"pnr": pnr}
                        ).fetchone()
                    dep_city = trip_row[0] if trip_row else "?"
                    arr_city = trip_row[1] if trip_row else "?"

                    EmailService.send_cancellation_email(profile.email, {
                        "pnr": pnr,
                        "passenger_name": f"{profile.legal_first_name} {profile.legal_last_name}",
                        "route": f"{dep_city} → {arr_city}",
                        "refund_amount": refund_amount,
                        "currency": confirmed.get("refund_currency", "USD"),
                        "credit_amount": refund_amount if credit_id else 0,
                    })
                    print(f"📧 Cancellation email sent to {profile.email}")
            except Exception as email_err:
                print(f"⚠️ Error enviando email cancelacion (no critico): {email_err}")

            # 7. Send WhatsApp cancellation notification
            try:
                from app.services.push_notification_service import PushNotificationService
                from app.models.models import Profile
                import asyncio
                profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()
                if profile and profile.phone_number:
                    push_svc = PushNotificationService()
                    msg = (
                        f"*Vuelo cancelado*\n\n"
                        f"PNR: {pnr}\n"
                        f"Reembolso: ${refund_amount:.2f} {confirmed.get('refund_currency', 'USD')}\n\n"
                    )
                    if credit_id:
                        msg += f"Se genero un credito de aerolinea por ${refund_amount:.2f}.\n"
                        msg += "Escribe 'creditos' para ver tu saldo."
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(push_svc.send_message(profile.phone_number, msg))
                        else:
                            loop.run_until_complete(push_svc.send_message(profile.phone_number, msg))
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(push_svc.send_message(profile.phone_number, msg))
                        finally:
                            loop.close()
                    print(f"📱 WhatsApp cancelacion enviado a {profile.phone_number}")
            except Exception as wa_err:
                print(f"⚠️ Error enviando WhatsApp cancelacion (no critico): {wa_err}")

            return {
                "status": "cancelled",
                "order_id": order_id,
                "refund_amount": confirmed.get("refund_amount"),
                "refund_currency": confirmed.get("refund_currency"),
                "credit_id": credit_id,
                "credit_created": credit_id is not None,
                "confirmation_number": confirmed.get("confirmation_number")
            }

        except requests.exceptions.RequestException as e:
            print(f"Error confirming cancellation for {order_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to cancel order: {str(e)}")
    
    def get_user_orders(self, user_id: str):
        """
        Get all orders for a user from database
        
        Args:
            user_id: User ID
            
        Returns:
            list: List of Trip objects with order details
        """
        trips = self.db.query(Trip).filter(Trip.user_id == user_id).all()
        
        result = []
        for trip in trips:
            trip_data = {
                "trip_id": trip.trip_id,
                "pnr": trip.pnr_code,
                "status": trip.status.value if trip.status else "UNKNOWN",
                "origin": trip.departure_city,
                "destination": trip.arrival_city,
                "departure_date": trip.departure_date.isoformat() if trip.departure_date else None,
                "return_date": trip.return_date.isoformat() if trip.return_date else None,
                "total_amount": float(trip.total_amount) if trip.total_amount else 0,
                "duffel_order_id": trip.duffel_order_id,
                "ticket_url": trip.ticket_url,
                "refund_amount": float(trip.refund_amount) if trip.refund_amount else None
            }
            result.append(trip_data)
        
        return result
