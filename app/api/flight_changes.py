"""
Flight Changes API - Endpoints for handling airline-initiated changes
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
    Get detailed comparison of old vs new flight
    
    Returns:
        Notification with parsed metadata containing flight change details
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.type != "flight_change":
        raise HTTPException(status_code=400, detail="Not a flight change notification")
    
    # Parse metadata
    metadata = json.loads(notification.metadata) if notification.metadata else {}
    
    return {
        "notification_id": notification_id,
        "order_id": notification.related_order_id,
        "original_flight": metadata.get("original_flight", {}),
        "new_flight": metadata.get("new_flight", {}),
        "changes": metadata.get("changes", {}),
        "change_type": metadata.get("change_type", "unknown")
    }

@router.post("/v1/flight-changes/{notification_id}/accept")
async def accept_flight_change(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """
    Accept airline-initiated change
    
    Steps:
    1. Get notification and order details
    2. Call Duffel API to confirm change (if needed)
    3. Update order in database
    4. Mark notification as resolved (read)
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.type != "flight_change":
        raise HTTPException(status_code=400, detail="Not a flight change notification")
    
    order_id = notification.related_order_id
    
    if not order_id:
        raise HTTPException(status_code=400, detail="No order ID associated with notification")
    
    # Find trip
    trip = db.query(Trip).filter(Trip.booking_reference == order_id).first()
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Parse metadata to get new flight details
    metadata = json.loads(notification.metadata) if notification.metadata else {}
    new_flight = metadata.get("new_flight", {})
    
    # Update trip with new details
    if new_flight.get("departure_time"):
        trip.departure_time = new_flight["departure_time"]
    if new_flight.get("arrival_time"):
        trip.arrival_time = new_flight["arrival_time"]
    if new_flight.get("carrier_code"):
        trip.carrier_code = new_flight["carrier_code"]
    if new_flight.get("flight_number"):
        trip.flight_number = new_flight["flight_number"]
    
    # Mark notification as read
    notification.read = 1
    notification.action_required = 0
    
    db.commit()
    
    print(f"✅ Accepted flight change for order {order_id}")
    
    # TODO: Call Duffel API to confirm change if needed
    # duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    # response = requests.post(
    #     f"https://api.duffel.com/air/order_changes/{change_id}/actions/confirm",
    #     headers={"Authorization": f"Bearer {duffel_token}"}
    # )
    
    return {
        "success": True,
        "message": "Flight change accepted",
        "order_id": order_id,
        "notification_id": notification_id,
        "updated_flight": {
            "departure_time": trip.departure_time,
            "arrival_time": trip.arrival_time,
            "carrier_code": trip.carrier_code,
            "flight_number": trip.flight_number
        }
    }

@router.post("/v1/flight-changes/{notification_id}/reject")
async def reject_flight_change(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """
    Reject airline-initiated change
    
    Steps:
    1. Get notification and order details
    2. Call Duffel API to request refund/cancellation
    3. Generate airline credit
    4. Mark notification as resolved
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.type != "flight_change":
        raise HTTPException(status_code=400, detail="Not a flight change notification")
    
    order_id = notification.related_order_id
    
    if not order_id:
        raise HTTPException(status_code=400, detail="No order ID associated with notification")
    
    # Find trip
    trip = db.query(Trip).filter(Trip.booking_reference == order_id).first()
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Update trip status to cancelled
    trip.status = "CANCELLED"
    
    # Generate airline credit
    from app.services.airline_credits_service import AirlineCreditsService
    credits_service = AirlineCreditsService(db)
    
    # Use trip amount as credit amount
    credit_amount = float(trip.total_amount) if hasattr(trip, 'total_amount') else 100.0
    
    credit = credits_service.create_credit(
        user_id=trip.user_id,
        airline_iata_code=trip.carrier_code or "XX",
        amount=credit_amount,
        currency=trip.currency if hasattr(trip, 'currency') else "USD",
        order_id=order_id
    )
    
    # Mark notification as read
    notification.read = 1
    notification.action_required = 0
    
    db.commit()
    
    print(f"✅ Rejected flight change for order {order_id}, generated credit {credit.id}")
    
    # TODO: Call Duffel API to cancel order
    # duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    # response = requests.post(
    #     f"https://api.duffel.com/air/order_cancellations",
    #     json={"order_id": order_id},
    #     headers={"Authorization": f"Bearer {duffel_token}"}
    # )
    
    return {
        "success": True,
        "message": "Flight change rejected, credit issued",
        "order_id": order_id,
        "notification_id": notification_id,
        "credit": {
            "id": credit.id,
            "amount": credit.credit_amount,
            "currency": credit.credit_currency,
            "airline": credit.airline_iata_code
        }
    }
