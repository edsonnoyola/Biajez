"""
Webhook Service - Handles processing of Duffel webhook events

FIXED:
- Signature verification uses Duffel's t=timestamp,v1=signature format
- Event data parsing uses data.object (Duffel's actual structure)
- Trip lookup uses duffel_order_id (not booking_reference)
- Idempotency check prevents duplicate event processing
- Added order.creation_failed handler
- WhatsApp notifications in Spanish
"""
import json
import hmac
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.models import WebhookEvent, Notification, Trip, AirlineCredit
from app.services.airline_credits_service import AirlineCreditsService
import uuid
import os
import requests as http_requests


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.credits_service = AirlineCreditsService(db)

    def verify_signature(self, payload: bytes, signature_header: str, secret: str) -> bool:
        """
        Verify that webhook came from Duffel using HMAC-SHA256.

        Duffel sends X-Duffel-Signature header in format:
            t=1616202842,v1=8aebaa7ecaf36950721e...

        The signed content is: timestamp + "." + raw_payload

        Args:
            payload: Raw request body bytes
            signature_header: Full X-Duffel-Signature header value
            secret: Webhook secret from DUFFEL_WEBHOOK_SECRET env var

        Returns:
            True if signature is valid, False otherwise
        """
        if not secret:
            print("⚠️  Warning: No webhook secret configured - skipping verification")
            return True  # Allow in development

        if not signature_header:
            print("⚠️  Warning: No signature header received")
            return False

        try:
            # Parse the signature header: "t=timestamp,v1=signature"
            parts = {}
            for part in signature_header.split(","):
                key, value = part.split("=", 1)
                parts[key.strip()] = value.strip()

            timestamp = parts.get("t")
            received_signature = parts.get("v1")

            if not timestamp or not received_signature:
                print("❌ Invalid signature header format")
                return False

            # Compute expected signature: HMAC-SHA256(secret, timestamp + "." + payload)
            signed_content = timestamp.encode() + b"." + payload
            expected_signature = hmac.new(
                secret.encode(),
                signed_content,
                hashlib.sha256
            ).hexdigest()

            # Secure comparison to prevent timing attacks
            is_valid = hmac.compare_digest(expected_signature, received_signature)

            if not is_valid:
                print(f"❌ Signature mismatch: expected={expected_signature[:20]}... got={received_signature[:20]}...")

            return is_valid

        except Exception as e:
            print(f"❌ Signature verification error: {e}")
            return False

    def is_duplicate_event(self, event_data: dict) -> bool:
        """
        Check if this event was already processed (idempotency).
        Duffel sends idempotency_key to detect duplicates.
        """
        idempotency_key = event_data.get("idempotency_key")
        event_id = event_data.get("id")

        if idempotency_key:
            existing = self.db.query(WebhookEvent).filter(
                WebhookEvent.event_data.contains(idempotency_key),
                WebhookEvent.processed == 1
            ).first()
            if existing:
                print(f"⚠️  Duplicate event detected (idempotency_key: {idempotency_key})")
                return True

        if event_id:
            existing = self.db.query(WebhookEvent).filter(
                WebhookEvent.id == event_id,
                WebhookEvent.processed == 1
            ).first()
            if existing:
                print(f"⚠️  Duplicate event detected (event_id: {event_id})")
                return True

        return False

    def store_event(self, event_type: str, event_data: dict) -> WebhookEvent:
        """
        Store webhook event in database for audit trail.
        Uses the Duffel event ID if available.
        """
        event_id = event_data.get("id", f"whe_{str(uuid.uuid4())[:20]}")

        webhook_event = WebhookEvent(
            id=event_id,
            event_type=event_type,
            event_data=json.dumps(event_data),
            processed=0,
            created_at=datetime.utcnow().isoformat()
        )

        self.db.add(webhook_event)
        self.db.commit()

        print(f"✅ Stored webhook event: {event_type} (ID: {event_id})")
        return webhook_event

    def process_event(self, event_type: str, event_data: dict) -> dict:
        """
        Route event to appropriate handler.

        Duffel event types (actual names from API):
        - order.created: Order successfully created
        - order.creation_failed: Order creation failed (202 accepted but failed later)
        - order.airline_initiated_change_detected: Airline changed the schedule
        - air.order.changed: Order was updated/changed
        - order_cancellation.created: Cancellation quote created
        - order_cancellation.confirmed: Cancellation confirmed
        - payment.created: Payment created for hold order
        - ping.triggered: Test ping from Duffel
        """
        print(f"🔄 Processing webhook event: {event_type}")

        handlers = {
            "order.airline_initiated_change_detected": self.handle_airline_change,
            "air.order.changed": self.handle_order_updated,
            "order.updated": self.handle_order_updated,  # Alias for compatibility
            "order.created": self.handle_order_created,
            "order.creation_failed": self.handle_order_creation_failed,
            "order_cancellation.created": self.handle_cancellation_created,
            "order_cancellation.confirmed": self.handle_cancellation_confirmed,
            "payment.created": self.handle_payment_created,
            "ping.triggered": self.handle_ping,
        }

        handler = handlers.get(event_type)

        if handler:
            try:
                result = handler(event_data)
                return {"success": True, "result": result}
            except Exception as e:
                print(f"❌ Error processing {event_type}: {e}")
                import traceback
                traceback.print_exc()
                return {"success": False, "error": str(e)}
        else:
            print(f"⚠️  No handler for event type: {event_type}")
            return {"success": True, "result": f"Acknowledged unknown event: {event_type}"}

    def _find_trip_by_duffel_order(self, duffel_order_id: str) -> Trip:
        """
        Find a trip by its Duffel order ID.
        Looks in duffel_order_id column first, then booking_reference as fallback.
        """
        # Primary lookup: duffel_order_id column
        trip = self.db.query(Trip).filter(Trip.duffel_order_id == duffel_order_id).first()
        if trip:
            return trip

        # Fallback: booking_reference (some old records may use this)
        trip = self.db.query(Trip).filter(Trip.booking_reference == duffel_order_id).first()
        if trip:
            return trip

        # Fallback for PostgreSQL with raw SQL (production)
        try:
            result = self.db.execute(
                text("SELECT booking_reference FROM trips WHERE duffel_order_id = :oid LIMIT 1"),
                {"oid": duffel_order_id}
            ).fetchone()
            if result:
                return self.db.query(Trip).filter(Trip.booking_reference == result[0]).first()
        except:
            pass

        return None

    def _extract_order_id(self, event_data: dict) -> str:
        """
        Extract order ID from Duffel webhook event data.

        Duffel webhook payload structure:
        {
            "id": "wev_...",
            "type": "order.airline_initiated_change_detected",
            "data": {
                "object": { ... the full order object ... }
            },
            "idempotency_key": "...",
            ...
        }

        The order ID is in data.object.id
        """
        data = event_data.get("data", {})

        # Duffel v2 format: data.object.id
        obj = data.get("object", {})
        if isinstance(obj, dict) and obj.get("id"):
            return obj["id"]

        # Fallback: data.id (some events may use this)
        if data.get("id"):
            return data["id"]

        # Fallback: data.order_id
        if data.get("order_id"):
            return data["order_id"]

        return None

    def handle_airline_change(self, event_data: dict) -> dict:
        """
        Handle airline-initiated changes (schedule changes, cancellations).

        When an airline changes a flight, Duffel sends this event with the
        updated order object. We need to:
        1. Find the trip in our DB
        2. Extract what changed (new times, new route, etc.)
        3. Create a notification for the user
        4. Send WhatsApp alert
        """
        print("✈️  Handling airline-initiated change")

        order_id = self._extract_order_id(event_data)
        if not order_id:
            print("❌ No order_id in event data")
            return {"error": "No order_id"}

        # Find trip in database
        trip = self._find_trip_by_duffel_order(order_id)

        if not trip:
            print(f"⚠️  Trip not found for order: {order_id}")
            return {"error": f"Trip not found for order {order_id}"}

        # Extract the updated order object from the event
        order_obj = event_data.get("data", {}).get("object", {})

        # Extract new flight details from slices
        new_slices = order_obj.get("slices", [])
        change_details = []

        for slice_data in new_slices:
            segments = slice_data.get("segments", [])
            for seg in segments:
                change_details.append({
                    "origin": seg.get("origin", {}).get("iata_code", ""),
                    "destination": seg.get("destination", {}).get("iata_code", ""),
                    "departing_at": seg.get("departing_at", ""),
                    "arriving_at": seg.get("arriving_at", ""),
                    "carrier": seg.get("operating_carrier", {}).get("name", ""),
                    "flight_number": seg.get("operating_carrier_flight_number", ""),
                })

        # Build metadata for the notification
        metadata = {
            "duffel_order_id": order_id,
            "pnr": trip.booking_reference,
            "change_type": "airline_initiated_schedule_change",
            "previous": {
                "departure_city": trip.departure_city,
                "arrival_city": trip.arrival_city,
                "departure_date": str(trip.departure_date) if trip.departure_date else None,
            },
            "updated_segments": change_details,
            "raw_slices_count": len(new_slices),
        }

        # Create notification with change details
        notification = self.create_notification(
            user_id=trip.user_id,
            type="flight_change",
            title="Cambio en tu vuelo",
            message=f"La aerolinea modifico tu vuelo {trip.booking_reference}. Revisa los cambios.",
            action_required=True,
            related_order_id=order_id,
            metadata=metadata
        )

        print(f"Created notification {notification.id} for user {trip.user_id}")

        # Send WhatsApp push notification
        self._send_whatsapp_notification(
            user_id=trip.user_id,
            message=self._format_airline_change_message(trip, change_details)
        )

        return {
            "order_id": order_id,
            "pnr": trip.booking_reference,
            "notification_id": notification.id,
            "user_id": trip.user_id,
            "changes_detected": len(change_details)
        }

    def handle_order_updated(self, event_data: dict) -> dict:
        """
        Handle order updated event.
        This fires when an order is modified (change confirmed, documents issued, etc.)

        We update the trip record with the latest data from Duffel.
        """
        print("🔄 Handling order updated")

        order_id = self._extract_order_id(event_data)
        if not order_id:
            return {"error": "No order_id"}

        trip = self._find_trip_by_duffel_order(order_id)
        if not trip:
            print(f"⚠️  Trip not found for order update: {order_id}")
            return {"error": "Trip not found"}

        # Extract updated order data
        order_obj = event_data.get("data", {}).get("object", {})

        # Update trip with latest data from the order
        try:
            # Update departure/arrival from slices
            slices = order_obj.get("slices", [])
            if slices:
                first_slice = slices[0]
                segments = first_slice.get("segments", [])

                if segments:
                    first_seg = segments[0]
                    last_seg = segments[-1]

                    origin = first_seg.get("origin", {}).get("iata_code")
                    destination = last_seg.get("destination", {}).get("iata_code")
                    departing_at = first_seg.get("departing_at", "")

                    if origin:
                        trip.departure_city = origin
                    if destination:
                        trip.arrival_city = destination
                    if departing_at and len(departing_at) >= 10:
                        from datetime import date
                        trip.departure_date = date.fromisoformat(departing_at[:10])

            # Update total amount if changed
            new_total = order_obj.get("total_amount")
            if new_total:
                trip.total_amount = float(new_total)

            # Update e-ticket numbers from documents
            documents = order_obj.get("documents", [])
            etickets = [d.get("unique_identifier", "") for d in documents if d.get("type") == "electronic_ticket"]
            if etickets:
                trip.eticket_number = ",".join(etickets)

            # Update booking reference (PNR) if Duffel has it
            booking_ref = order_obj.get("booking_reference")
            if booking_ref and booking_ref != trip.booking_reference:
                # PNR might change after airline-initiated change
                print(f"PNR updated: {trip.booking_reference} → {booking_ref}")

            self.db.commit()
            print(f"✅ Trip {trip.booking_reference} updated from webhook")

        except Exception as e:
            print(f"Error updating trip from webhook: {e}")
            import traceback
            traceback.print_exc()

        # Create notification
        notification = self.create_notification(
            user_id=trip.user_id,
            type="order_updated",
            title="Reserva actualizada",
            message=f"Tu reserva {trip.booking_reference} ha sido actualizada.",
            action_required=False,
            related_order_id=order_id
        )

        return {
            "order_id": order_id,
            "pnr": trip.booking_reference,
            "notification_id": notification.id
        }

    def handle_order_created(self, event_data: dict) -> dict:
        """
        Handle order creation confirmation from Duffel.
        This confirms the booking was successfully created on the airline's side.
        """
        print("✅ Handling order creation")

        order_id = self._extract_order_id(event_data)
        order_obj = event_data.get("data", {}).get("object", {})

        if not order_id:
            return {"error": "No order_id", "status": "acknowledged"}

        trip = self._find_trip_by_duffel_order(order_id)

        if trip:
            # Confirm the trip status
            if trip.status != "CANCELLED":
                trip.status = "TICKETED"

            # Extract PNR/booking reference from Duffel
            booking_ref = order_obj.get("booking_reference")
            if booking_ref:
                trip.pnr_code = booking_ref

            # Extract e-ticket numbers
            documents = order_obj.get("documents", [])
            etickets = [d.get("unique_identifier", "") for d in documents if d.get("type") == "electronic_ticket"]
            if etickets:
                trip.eticket_number = ",".join(etickets)

            self.db.commit()
            print(f"✅ Trip {trip.booking_reference} confirmed as TICKETED")

            # Send WhatsApp confirmation
            self._send_whatsapp_notification(
                user_id=trip.user_id,
                message=(
                    f"*Reserva confirmada*\n\n"
                    f"PNR: {trip.booking_reference}\n"
                    f"{trip.departure_city or ''} → {trip.arrival_city or ''}\n"
                    f"Total: ${trip.total_amount}\n\n"
                    f"Tu boleto esta listo. Escribe 'itinerario' para ver detalles."
                )
            )

        return {"order_id": order_id, "status": "confirmed"}

    def handle_order_creation_failed(self, event_data: dict) -> dict:
        """
        Handle order creation failure.
        This fires when a 202-accepted order fails to actually book with the airline.
        Critical: notify the user immediately that their booking didn't go through.
        """
        print("❌ Handling order creation failure")

        order_id = self._extract_order_id(event_data)
        if not order_id:
            return {"error": "No order_id"}

        trip = self._find_trip_by_duffel_order(order_id)

        if trip:
            # Mark as failed
            trip.status = "CANCELLED"
            self.db.commit()

            # Create urgent notification
            notification = self.create_notification(
                user_id=trip.user_id,
                type="booking_failed",
                title="Error en reserva",
                message=f"Tu reserva {trip.booking_reference} no pudo completarse. Intenta de nuevo o contacta soporte.",
                action_required=True,
                related_order_id=order_id
            )

            # Send WhatsApp alert
            self._send_whatsapp_notification(
                user_id=trip.user_id,
                message=(
                    f"*Error en tu reserva*\n\n"
                    f"Tu reserva {trip.booking_reference} no pudo completarse con la aerolinea.\n\n"
                    f"Esto puede ocurrir cuando la tarifa ya no esta disponible.\n"
                    f"Intenta buscar de nuevo o escribe 'ayuda' para soporte."
                )
            )

            return {
                "order_id": order_id,
                "notification_id": notification.id,
                "status": "booking_failed"
            }

        return {"order_id": order_id, "status": "acknowledged_no_trip"}

    def handle_cancellation_created(self, event_data: dict) -> dict:
        """
        Handle order_cancellation.created - cancellation quote was created.
        This means someone initiated a cancellation but it's not confirmed yet.
        """
        print("🚫 Handling cancellation created (quote)")

        order_id = self._extract_order_id(event_data)
        if not order_id:
            return {"error": "No order_id"}

        trip = self._find_trip_by_duffel_order(order_id)
        if trip:
            self.create_notification(
                user_id=trip.user_id,
                type="cancellation_pending",
                title="Cancelacion en proceso",
                message=f"Se inicio la cancelacion de tu vuelo {trip.booking_reference}.",
                action_required=False,
                related_order_id=order_id
            )

        return {"order_id": order_id, "status": "cancellation_quote_created"}

    def handle_cancellation_confirmed(self, event_data: dict) -> dict:
        """
        Handle order_cancellation.confirmed - cancellation was finalized.
        Update trip status and notify user via WhatsApp.
        """
        print("🚫 Handling cancellation confirmed")

        order_id = self._extract_order_id(event_data)
        if not order_id:
            return {"error": "No order_id"}

        # Extract refund info from the cancellation object
        cancel_obj = event_data.get("data", {}).get("object", {})
        refund_amount = cancel_obj.get("refund_amount", "0")
        refund_currency = cancel_obj.get("refund_currency", "USD")

        trip = self._find_trip_by_duffel_order(order_id)
        if trip:
            trip.status = "CANCELLED"
            if refund_amount:
                trip.refund_amount = float(refund_amount)
            self.db.commit()

            # Create notification
            self.create_notification(
                user_id=trip.user_id,
                type="cancellation_confirmed",
                title="Vuelo cancelado",
                message=f"Tu vuelo {trip.booking_reference} fue cancelado." +
                       (f" Reembolso: ${refund_amount} {refund_currency}" if float(refund_amount or 0) > 0 else ""),
                action_required=False,
                related_order_id=order_id
            )

            # Send WhatsApp
            msg = f"*Vuelo cancelado*\n\nTu vuelo {trip.booking_reference} fue cancelado."
            if float(refund_amount or 0) > 0:
                msg += f"\nReembolso: ${refund_amount} {refund_currency}"
            msg += "\n\nEscribe 'ayuda' si necesitas algo."

            self._send_whatsapp_notification(user_id=trip.user_id, message=msg)

            print(f"✅ Trip {trip.booking_reference} cancelled via webhook")

        return {"order_id": order_id, "status": "cancellation_confirmed", "refund": refund_amount}

    def handle_payment_created(self, event_data: dict) -> dict:
        """
        Handle payment created event (for hold orders).
        """
        print("💳 Handling payment created")

        order_id = self._extract_order_id(event_data)

        return {"order_id": order_id, "status": "payment_acknowledged"}

    def handle_ping(self, event_data: dict) -> dict:
        """
        Handle ping event (webhook test from Duffel dashboard).
        """
        print("🏓 Ping received from Duffel")
        return {"status": "pong"}

    def _format_airline_change_message(self, trip: Trip, change_details: list) -> str:
        """Format a WhatsApp message for airline-initiated changes in Spanish."""
        msg = f"*Cambio en tu vuelo*\n\n"
        msg += f"PNR: {trip.booking_reference}\n"
        msg += f"Ruta: {trip.departure_city or '?'} → {trip.arrival_city or '?'}\n\n"

        if change_details:
            msg += "Nuevos detalles:\n"
            for seg in change_details:
                origin = seg.get("origin", "?")
                dest = seg.get("destination", "?")
                dep_time = seg.get("departing_at", "")
                carrier = seg.get("carrier", "")

                # Format time nicely
                if dep_time and "T" in dep_time:
                    try:
                        dt = datetime.fromisoformat(dep_time.replace("Z", "+00:00"))
                        time_str = dt.strftime("%d/%m %H:%M")
                    except:
                        time_str = dep_time[:16]
                else:
                    time_str = dep_time or "?"

                msg += f"  {origin} → {dest} | {time_str}"
                if carrier:
                    msg += f" ({carrier})"
                msg += "\n"
        else:
            msg += "La aerolinea modifico el horario de tu vuelo.\n"

        msg += "\nRevisa tu itinerario actualizado.\n"
        msg += "Escribe 'itinerario' para ver detalles."

        return msg

    def _send_whatsapp_notification(self, user_id: str, message: str) -> None:
        """
        Send WhatsApp notification to user.
        Uses PushNotificationService (async) in a sync context.
        """
        try:
            from app.models.models import Profile
            from app.services.push_notification_service import PushNotificationService
            import asyncio

            # Get user's phone number
            profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()

            if not profile or not profile.phone_number:
                print(f"⚠️  No phone number found for user {user_id}")
                return

            push_service = PushNotificationService()

            # Run async function in sync context safely
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside an async context (FastAPI), use create_task
                    asyncio.ensure_future(push_service.send_message(profile.phone_number, message))
                    print(f"📱 WhatsApp notification queued for {profile.phone_number}")
                else:
                    loop.run_until_complete(push_service.send_message(profile.phone_number, message))
                    print(f"📱 WhatsApp notification sent to {profile.phone_number}")
            except RuntimeError:
                # No event loop, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(push_service.send_message(profile.phone_number, message))
                    print(f"📱 WhatsApp notification sent to {profile.phone_number}")
                finally:
                    loop.close()

        except Exception as e:
            print(f"❌ Error sending WhatsApp notification: {e}")
            import traceback
            traceback.print_exc()

    def create_notification(
        self,
        user_id: str,
        type: str,
        title: str,
        message: str,
        action_required: bool = False,
        related_order_id: str = None,
        metadata: dict = None
    ) -> Notification:
        """
        Create a notification for a user.
        Stores metadata in extra_data column as JSON.
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
            extra_data=json.dumps(metadata) if metadata else None,
            created_at=datetime.utcnow().isoformat()
        )

        self.db.add(notification)
        self.db.commit()

        print(f"✅ Created notification: {notification.id} for user {user_id}")

        return notification

    def mark_event_processed(self, event_id: str, success: bool = True, error: str = None):
        """
        Mark webhook event as processed.
        """
        event = self.db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()

        if event:
            event.processed = 1
            event.processed_at = datetime.utcnow().isoformat()
            if error:
                event.error_message = error
            self.db.commit()
            print(f"✅ Marked event {event_id} as processed")
