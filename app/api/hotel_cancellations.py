"""
Hotel Cancellations API - Endpoints for cancelling hotel bookings
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Trip, Notification
import os
import requests
from datetime import datetime

router = APIRouter()

@router.post("/v1/hotels/{booking_id}/cancel")
async def cancel_hotel_booking(
    booking_id: str,
    db: Session = Depends(get_db)
):
    """
    Cancel a hotel booking
    
    Steps:
    1. Find booking in database
    2. Call Duffel Stays API to cancel (if available)
    3. Update booking status to CANCELLED
    4. Create notification for user
    
    Returns:
        Cancellation confirmation with refund details
    """
    # Find booking
    booking = db.query(Trip).filter(Trip.id == booking_id).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Booking already cancelled")
    
    # Check if it's a hotel booking
    booking_type = getattr(booking, 'booking_type', 'flight')
    if booking_type != 'hotel':
        raise HTTPException(status_code=400, detail="Not a hotel booking")
    
    # Get Duffel token
    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    
    refund_amount = 0
    refund_currency = "USD"
    
    # Try to cancel with Duffel Stays API
    if duffel_token and booking.booking_reference:
        try:
            print(f"🏨 Attempting to cancel hotel booking with Duffel: {booking.booking_reference}")
            
            # Call Duffel Stays API
            response = requests.post(
                f"https://api.duffel.com/stays/accommodations/{booking.booking_reference}/actions/cancel",
                headers={
                    "Authorization": f"Bearer {duffel_token}",
                    "Content-Type": "application/json",
                    "Duffel-Version": "v1"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                refund_data = result.get("data", {}).get("refund", {})
                refund_amount = float(refund_data.get("amount", 0))
                refund_currency = refund_data.get("currency", "USD")
                print(f"✅ Duffel cancellation successful. Refund: {refund_amount} {refund_currency}")
            else:
                print(f"⚠️  Duffel API returned {response.status_code}: {response.text}")
                # Continue with local cancellation
                
        except requests.exceptions.Timeout:
            print("⚠️  Duffel API timeout, proceeding with local cancellation")
        except Exception as e:
            print(f"⚠️  Duffel API error: {e}, proceeding with local cancellation")
    
    # Update booking status in database
    booking.status = "CANCELLED"
    
    # If no refund from Duffel, estimate from booking amount
    if refund_amount == 0 and hasattr(booking, 'total_amount'):
        refund_amount = float(booking.total_amount)
        refund_currency = getattr(booking, 'currency', 'USD')
    
    db.commit()
    
    # Create notification for user
    from app.services.webhook_service import WebhookService
    webhook_service = WebhookService(db)
    
    hotel_name = getattr(booking, 'hotel_name', 'Hotel')
    
    webhook_service.create_notification(
        user_id=booking.user_id,
        type="hotel_cancelled",
        title="🏨 Hotel Booking Cancelled",
        message=f"Your hotel booking for {hotel_name} has been cancelled. Refund: ${refund_amount:.2f} {refund_currency}",
        action_required=False,
        related_order_id=booking.booking_reference
    )
    
    print(f"✅ Hotel booking {booking_id} cancelled successfully")
    
    return {
        "success": True,
        "message": "Hotel booking cancelled",
        "booking_id": booking_id,
        "booking_reference": booking.booking_reference,
        "status": "CANCELLED",
        "refund": {
            "amount": refund_amount,
            "currency": refund_currency
        },
        "hotel_name": hotel_name
    }

@router.get("/v1/hotels/{booking_id}/details")
async def get_hotel_booking_details(
    booking_id: str,
    db: Session = Depends(get_db)
):
    """
    Get hotel booking details
    """
    booking = db.query(Trip).filter(Trip.id == booking_id).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "booking_id": booking.id,
        "booking_reference": booking.booking_reference,
        "status": booking.status,
        "hotel_name": getattr(booking, 'hotel_name', 'Unknown Hotel'),
        "check_in": getattr(booking, 'check_in_date', None),
        "check_out": getattr(booking, 'check_out_date', None),
        "total_amount": getattr(booking, 'total_amount', 0),
        "currency": getattr(booking, 'currency', 'USD')
    }
