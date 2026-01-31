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
        # 1. Verify order belongs to user
        trip = self.db.query(Trip).filter(
            Trip.duffel_order_id == order_id,
            Trip.user_id == user_id
        ).first()
        
        if not trip:
            raise HTTPException(status_code=404, detail="Order not found or unauthorized")
        
        if trip.status == TripStatusEnum.CANCELLED:
            raise HTTPException(status_code=400, detail="Order already cancelled")
        
        # 2. Get cancellation quote first
        quote = self.get_cancellation_quote(order_id)
        
        # 3. Confirm cancellation
        url = f"{self.base_url}/air/order_cancellations/{quote['cancellation_id']}/actions/confirm"
        
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            confirmed = response.json()["data"]
            
            # 4. Update database
            trip.status = TripStatusEnum.CANCELLED
            trip.refund_amount = float(confirmed.get("refund_amount", 0))
            self.db.commit()
            
            # 5. Create airline credit if there's a refund amount
            credit_id = None
            refund_amount = float(confirmed.get("refund_amount", 0))
            if refund_amount > 0:
                from app.services.airline_credits_service import AirlineCreditsService
                credits_service = AirlineCreditsService(self.db)
                
                # Extract airline code from trip or order
                airline_code = trip.departure_city[:2] if trip.departure_city else "XX"
                
                credit = credits_service.create_credit(
                    user_id=user_id,
                    airline_iata_code=airline_code,
                    amount=refund_amount,
                    currency=confirmed.get("refund_currency", "USD"),
                    order_id=order_id,
                    expires_days=365
                )
                credit_id = credit["id"]
                print(f"✅ Created airline credit: {credit_id} for ${refund_amount}")
            
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
