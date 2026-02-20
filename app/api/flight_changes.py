"""
Flight Changes API - Endpoints for handling airline-initiated changes.

FIXED:
- Uses extra_data instead of metadata (matches Notification model)
- Uses duffel_order_id for trip lookup (not booking_reference)
- Calls Duffel API to actually accept/reject changes
- Sends WhatsApp notification on accept/reject
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Notification, Trip
import json
import os
import requests

router = APIRouter()


@router.get("/v1/flight-changes/{notification_id}/details")
async def get_change_details(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed comparison of old vs new flight.

    Returns:
        Notification with parsed extra_data containing flight change details
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.type != "flight_change":
        raise HTTPException(status_code=400, detail="Not a flight change notification")

    # Parse extra_data (the correct column name, not metadata)
    extra_data = json.loads(notification.extra_data) if notification.extra_data else {}

    return {
        "notification_id": notification_id,
        "order_id": notification.related_order_id,
        "pnr": extra_data.get("pnr"),
        "change_type": extra_data.get("change_type", "unknown"),
        "previous": extra_data.get("previous", {}),
        "updated_segments": extra_data.get("updated_segments", []),
        "action_required": bool(notification.action_required),
        "created_at": notification.created_at
    }


@router.post("/v1/flight-changes/{notification_id}/accept")
async def accept_flight_change(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """
    Accept airline-initiated change.

    For airline-initiated changes, "accepting" means acknowledging the new schedule.
    The order is already updated on Duffel's side - we just need to update our DB.

    Steps:
    1. Get notification and order details
    2. Fetch latest order data from Duffel to sync
    3. Update trip in database with new details
    4. Mark notification as resolved
    5. Send WhatsApp confirmation
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.type != "flight_change":
        raise HTTPException(status_code=400, detail="Not a flight change notification")

    order_id = notification.related_order_id

    if not order_id:
        raise HTTPException(status_code=400, detail="No order ID associated with notification")

    # Find trip by duffel_order_id
    trip = db.query(Trip).filter(Trip.duffel_order_id == order_id).first()
    if not trip:
        # Fallback to booking_reference
        trip = db.query(Trip).filter(Trip.booking_reference == order_id).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Fetch latest order from Duffel to get current state
    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    updated_details = {}

    if duffel_token:
        try:
            duffel_order_id = trip.duffel_order_id or order_id
            response = requests.get(
                f"https://api.duffel.com/air/orders/{duffel_order_id}",
                headers={
                    "Authorization": f"Bearer {duffel_token}",
                    "Duffel-Version": "v2",
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                },
                timeout=15
            )

            if response.status_code == 200:
                order_data = response.json().get("data", {})
                slices = order_data.get("slices", [])

                if slices:
                    first_slice = slices[0]
                    segments = first_slice.get("segments", [])

                    if segments:
                        first_seg = segments[0]
                        last_seg = segments[-1]

                        new_origin = first_seg.get("origin", {}).get("iata_code")
                        new_dest = last_seg.get("destination", {}).get("iata_code")
                        new_dep = first_seg.get("departing_at", "")

                        if new_origin:
                            trip.departure_city = new_origin
                            updated_details["departure_city"] = new_origin
                        if new_dest:
                            trip.arrival_city = new_dest
                            updated_details["arrival_city"] = new_dest
                        if new_dep and len(new_dep) >= 10:
                            from datetime import date
                            trip.departure_date = date.fromisoformat(new_dep[:10])
                            updated_details["departure_date"] = new_dep[:10]

                # Update total if changed
                new_total = order_data.get("total_amount")
                if new_total:
                    trip.total_amount = float(new_total)
                    updated_details["total_amount"] = new_total

        except Exception as e:
            print(f"Error fetching order from Duffel: {e}")

    # Mark notification as read and resolved
    notification.read = 1
    notification.action_required = 0

    db.commit()

    print(f"✅ Accepted flight change for order {order_id}")

    # Send WhatsApp confirmation
    try:
        from app.services.webhook_service import WebhookService
        ws = WebhookService(db)
        ws._send_whatsapp_notification(
            user_id=trip.user_id,
            message=(
                f"*Cambio aceptado*\n\n"
                f"Tu vuelo {trip.booking_reference} ha sido actualizado.\n"
                f"{trip.departure_city or '?'} → {trip.arrival_city or '?'}\n"
                f"Escribe 'itinerario' para ver los nuevos detalles."
            )
        )
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")

    return {
        "success": True,
        "message": "Flight change accepted",
        "order_id": order_id,
        "pnr": trip.booking_reference,
        "notification_id": notification_id,
        "updated_details": updated_details
    }


@router.post("/v1/flight-changes/{notification_id}/reject")
async def reject_flight_change(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """
    Reject airline-initiated change.

    This cancels the order and issues a refund/credit.

    Steps:
    1. Get notification and order details
    2. Cancel the order via Duffel API (2-step: quote + confirm)
    3. Generate airline credit from refund
    4. Mark notification as resolved
    5. Send WhatsApp notification
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.type != "flight_change":
        raise HTTPException(status_code=400, detail="Not a flight change notification")

    order_id = notification.related_order_id

    if not order_id:
        raise HTTPException(status_code=400, detail="No order ID associated with notification")

    # Find trip by duffel_order_id
    trip = db.query(Trip).filter(Trip.duffel_order_id == order_id).first()
    if not trip:
        trip = db.query(Trip).filter(Trip.booking_reference == order_id).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Cancel via Duffel API (2-step cancellation)
    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    refund_amount = 0
    refund_currency = "USD"

    if duffel_token and trip.duffel_order_id:
        try:
            # Step 1: Create cancellation quote
            quote_response = requests.post(
                "https://api.duffel.com/air/order_cancellations",
                headers={
                    "Authorization": f"Bearer {duffel_token}",
                    "Duffel-Version": "v2",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                },
                json={"data": {"order_id": trip.duffel_order_id}},
                timeout=30
            )

            if quote_response.status_code in (200, 201):
                quote_data = quote_response.json().get("data", {})
                cancellation_id = quote_data.get("id")
                refund_amount = float(quote_data.get("refund_amount", 0))
                refund_currency = quote_data.get("refund_currency", "USD")

                # Step 2: Confirm cancellation
                if cancellation_id:
                    confirm_response = requests.post(
                        f"https://api.duffel.com/air/order_cancellations/{cancellation_id}/actions/confirm",
                        headers={
                            "Authorization": f"Bearer {duffel_token}",
                            "Duffel-Version": "v2",
                            "Accept": "application/json",
                            "Accept-Encoding": "gzip",
                        },
                        timeout=30
                    )

                    if confirm_response.status_code in (200, 201):
                        print(f"✅ Order {trip.duffel_order_id} cancelled via Duffel")
                    else:
                        print(f"⚠️  Cancellation confirm failed: {confirm_response.status_code}")
            else:
                print(f"⚠️  Cancellation quote failed: {quote_response.status_code}: {quote_response.text[:200]}")

        except Exception as e:
            print(f"Error cancelling on Duffel: {e}")

    # Update trip status
    trip.status = "CANCELLED"
    if refund_amount:
        trip.refund_amount = refund_amount

    # Generate airline credit
    credit_id = None
    credit_amount = refund_amount if refund_amount > 0 else float(trip.total_amount or 0)

    if credit_amount > 0:
        try:
            from app.services.airline_credits_service import AirlineCreditsService
            credits_service = AirlineCreditsService(db)

            credit = credits_service.create_credit(
                user_id=trip.user_id,
                airline_iata_code="XX",  # Generic - airline code not always available
                amount=credit_amount,
                currency=refund_currency,
                order_id=order_id
            )
            credit_id = credit.id
            print(f"✅ Generated credit: {credit_id} for ${credit_amount}")
        except Exception as e:
            print(f"Error creating credit: {e}")

    # Mark notification as read
    notification.read = 1
    notification.action_required = 0

    db.commit()

    print(f"✅ Rejected flight change for order {order_id}")

    # Send WhatsApp notification
    try:
        from app.services.webhook_service import WebhookService
        ws = WebhookService(db)

        msg = (
            f"*Cambio rechazado - Vuelo cancelado*\n\n"
            f"Tu vuelo {trip.booking_reference} ha sido cancelado.\n"
        )
        if credit_amount > 0:
            msg += f"\nSe te acredito ${credit_amount:.2f} {refund_currency} para futuros viajes.\n"
        msg += "\nEscribe 'creditos' para ver tu saldo."

        ws._send_whatsapp_notification(user_id=trip.user_id, message=msg)
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")

    return {
        "success": True,
        "message": "Flight change rejected, order cancelled",
        "order_id": order_id,
        "pnr": trip.booking_reference,
        "notification_id": notification_id,
        "refund_amount": refund_amount,
        "credit_id": credit_id,
        "credit_amount": credit_amount,
        "currency": refund_currency
    }
