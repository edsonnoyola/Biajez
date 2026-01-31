"""
Webhook Service - Handles processing of Duffel webhook events
"""
import json
import hmac
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import WebhookEvent, Notification, Trip, AirlineCredit
from app.services.airline_credits_service import AirlineCreditsService
import uuid

class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.credits_service = AirlineCreditsService(db)
    
    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify that webhook came from Duffel
        
        Args:
            payload: Raw request body
            signature: Signature from X-Duffel-Signature header
            secret: Webhook secret from environment
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not secret:
            print("⚠️  Warning: No webhook secret configured")
            return True  # Allow in development
        
        expected_signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def store_event(self, event_type: str, event_data: dict) -> WebhookEvent:
        """
        Store webhook event in database for audit trail
        """
        webhook_event = WebhookEvent(
            id=f"whe_{str(uuid.uuid4())[:20]}",
            event_type=event_type,
            event_data=json.dumps(event_data),
            processed=0,
            created_at=datetime.utcnow().isoformat()
        )
        
        self.db.add(webhook_event)
        self.db.commit()
        
        print(f"✅ Stored webhook event: {event_type} (ID: {webhook_event.id})")
        return webhook_event
    
    def process_event(self, event_type: str, event_data: dict) -> dict:
        """
        Route event to appropriate handler
        
        Returns:
            dict with processing result
        """
        print(f"🔄 Processing webhook event: {event_type}")
        
        handlers = {
            "order.airline_initiated_change_detected": self.handle_airline_change,
            "order.cancelled": self.handle_order_cancelled,
            "order.changed": self.handle_order_changed,
            "order.created": self.handle_order_created,
            "payment.failed": self.handle_payment_failed,
        }
        
        handler = handlers.get(event_type)
        
        if handler:
            try:
                result = handler(event_data)
                return {"success": True, "result": result}
            except Exception as e:
                print(f"❌ Error processing {event_type}: {e}")
                return {"success": False, "error": str(e)}
        else:
            print(f"⚠️  No handler for event type: {event_type}")
            return {"success": False, "error": f"No handler for {event_type}"}
    
    def handle_airline_change(self, event_data: dict) -> dict:
        """
        Handle airline-initiated changes
        
        This is when the airline changes/cancels a flight
        Stores change details in notification metadata
        """
        print("✈️  Handling airline-initiated change")
        
        # Extract order ID and change details from event
        data = event_data.get("data", {})
        order_id = data.get("order_id") or data.get("id")
        changes = data.get("changes", {})
        
        if not order_id:
            print("❌ No order_id in event data")
            return {"error": "No order_id"}
        
        # Find trip in database
        trip = self.db.query(Trip).filter(Trip.booking_reference == order_id).first()
        
        if not trip:
            print(f"⚠️  Trip not found for order: {order_id}")
            return {"error": "Trip not found"}
        
        # Extract change details for metadata
        metadata = {
            "order_id": order_id,
            "changes": changes,
            "change_type": data.get("change_type", "schedule_change"),
            "original_flight": {
                "departure_time": trip.departure_time,
                "arrival_time": trip.arrival_time,
                "carrier_code": trip.carrier_code,
                "flight_number": trip.flight_number,
                "origin": trip.origin_iata,
                "destination": trip.destination_iata
            },
            "new_flight": {
                "departure_time": changes.get("departure_time"),
                "arrival_time": changes.get("arrival_time"),
                "carrier_code": changes.get("carrier_code"),
                "flight_number": changes.get("flight_number")
            }
        }
        
        # Create notification with change details
        notification = self.create_notification(
            user_id=trip.user_id,
            type="flight_change",
            title="✈️ Flight Change Detected",
            message=f"Your flight {trip.booking_reference} has been changed by the airline. Please review the changes.",
            action_required=True,
            related_order_id=order_id,
            metadata=metadata  # NEW: Store change details
        )
        
        print(f"✅ Created notification with change details for user {trip.user_id}")
        
        return {
            "order_id": order_id,
            "notification_id": notification.id,
            "user_id": trip.user_id,
            "changes": changes
        }
    
    def handle_order_cancelled(self, event_data: dict) -> dict:
        """
        Handle order cancellation
        
        Generate airline credit if refund amount exists
        """
        print("🚫 Handling order cancellation")
        
        order_id = event_data.get("data", {}).get("id")
        refund_amount = event_data.get("data", {}).get("refund_amount")
        refund_currency = event_data.get("data", {}).get("refund_currency", "USD")
        
        if not order_id:
            return {"error": "No order_id"}
        
        # Find trip
        trip = self.db.query(Trip).filter(Trip.booking_reference == order_id).first()
        
        if not trip:
            return {"error": "Trip not found"}
        
        # Update trip status
        trip.status = "CANCELLED"
        self.db.commit()
        
        # Generate credit if refund exists
        credit_id = None
        if refund_amount and float(refund_amount) > 0:
            # Get airline code from trip
            airline_code = trip.carrier_code or "XX"
            
            credit = self.credits_service.create_credit(
                user_id=trip.user_id,
                airline_iata_code=airline_code,
                amount=float(refund_amount),
                currency=refund_currency,
                order_id=order_id
            )
            credit_id = credit.id
            print(f"✅ Generated credit: {credit_id} for ${refund_amount}")
        
        # Create notification
        notification = self.create_notification(
            user_id=trip.user_id,
            type="cancellation",
            title="🚫 Flight Cancelled",
            message=f"Your flight {trip.booking_reference} has been cancelled. " + 
                   (f"A credit of ${refund_amount} has been added to your account." if credit_id else ""),
            action_required=False,
            related_order_id=order_id
        )
        
        return {
            "order_id": order_id,
            "credit_id": credit_id,
            "notification_id": notification.id
        }
    
    def handle_order_changed(self, event_data: dict) -> dict:
        """
        Handle order change confirmation
        """
        print("🔄 Handling order change")
        
        order_id = event_data.get("data", {}).get("id")
        
        if not order_id:
            return {"error": "No order_id"}
        
        trip = self.db.query(Trip).filter(Trip.booking_reference == order_id).first()
        
        if not trip:
            return {"error": "Trip not found"}
        
        # Create notification
        notification = self.create_notification(
            user_id=trip.user_id,
            type="order_changed",
            title="✅ Flight Change Confirmed",
            message=f"Your flight change for {trip.booking_reference} has been confirmed.",
            action_required=False,
            related_order_id=order_id
        )
        
        return {
            "order_id": order_id,
            "notification_id": notification.id
        }
    
    def handle_order_created(self, event_data: dict) -> dict:
        """
        Handle order creation (confirmation)
        """
        print("✅ Handling order creation")
        
        order_id = event_data.get("data", {}).get("id")
        
        return {"order_id": order_id, "status": "acknowledged"}
    
    def handle_payment_failed(self, event_data: dict) -> dict:
        """
        Handle payment failure
        """
        print("❌ Handling payment failure")
        
        payment_id = event_data.get("data", {}).get("id")
        
        # You would need to find the user associated with this payment
        # For now, just acknowledge
        
        return {"payment_id": payment_id, "status": "acknowledged"}
    
    def create_notification(
        self,
        user_id: str,
        type: str,
        title: str,
        message: str,
        action_required: bool = False,
        related_order_id: str = None,
        metadata: dict = None  # NEW: Accept metadata
    ) -> Notification:
        """
        Create a notification for a user
        """
        notification = Notification(
            id=f"not_{str(uuid.uuid4())[:20]}",
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            read=0,
            action_required=1 if action_required else 0,
            related_order_id=related_order_id,
            metadata=json.dumps(metadata) if metadata else None,  # NEW: Store metadata as JSON
            created_at=datetime.utcnow().isoformat()
        )
        
        self.db.add(notification)
        self.db.commit()
        
        print(f"✅ Created notification: {notification.id} for user {user_id}")
        
        return notification
    
    def mark_event_processed(self, event_id: str, success: bool = True, error: str = None):
        """
        Mark webhook event as processed
        """
        event = self.db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        
        if event:
            event.processed = 1
            event.processed_at = datetime.utcnow().isoformat()
            if error:
                event.error_message = error
            self.db.commit()
            print(f"✅ Marked event {event_id} as processed")
