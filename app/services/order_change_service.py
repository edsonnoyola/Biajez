import os
import requests
from sqlalchemy.orm import Session
from app.models.models import Trip, TripStatusEnum
from fastapi import HTTPException
from typing import List, Dict, Optional

class OrderChangeService:
    """Manages Duffel order change operations: create requests, get offers, confirm changes"""
    
    def __init__(self, db: Session):
        self.db = db
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Duffel-Version": "v2"
        }
    
    def create_change_request(
        self, 
        order_id: str, 
        user_id: str,
        slices_to_remove: List[Dict],
        slices_to_add: List[Dict]
    ):
        """
        Create an order change request
        
        Args:
            order_id: Duffel order ID to change
            user_id: User ID to verify ownership
            slices_to_remove: List of slice IDs to remove [{"slice_id": "sli_xxx"}]
            slices_to_add: List of new search criteria [{
                "origin": "LHR",
                "destination": "JFK", 
                "departure_date": "2026-04-24",
                "cabin_class": "economy"
            }]
            
        Returns:
            dict: Order change request with available offers
        """
        # 1. Verify order belongs to user
        trip = self.db.query(Trip).filter(
            Trip.duffel_order_id == order_id,
            Trip.user_id == user_id
        ).first()
        
        if not trip:
            raise HTTPException(status_code=404, detail="Order not found or unauthorized")
        
        if trip.status == TripStatusEnum.CANCELLED:
            raise HTTPException(status_code=400, detail="Cannot change a cancelled order")
        
        # 2. Create change request with Duffel
        url = f"{self.base_url}/air/order_change_requests"
        payload = {
            "data": {
                "order_id": order_id,
                "slices": {
                    "remove": slices_to_remove,
                    "add": slices_to_add
                }
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            change_request = response.json()["data"]
            
            # 3. Store change request ID in database via raw SQL
            from app.db.database import engine as _engine
            from sqlalchemy import text as _text
            with _engine.connect() as _conn:
                _conn.execute(
                    _text("UPDATE trips SET change_request_id = :crid WHERE duffel_order_id = :oid AND user_id = :uid"),
                    {"crid": change_request["id"], "oid": order_id, "uid": user_id}
                )
                _conn.commit()
            
            return {
                "change_request_id": change_request["id"],
                "order_id": change_request["order_id"],
                "created_at": change_request["created_at"],
                "slices": change_request["slices"],
                "offers_count": len(change_request.get("order_change_offers", [])),
                "order_change_offers": change_request.get("order_change_offers", [])
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Error creating change request for {order_id}: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to create change request: {str(e)}"
            )
    
    def get_change_request(self, request_id: str):
        """
        Get details of an order change request
        
        Args:
            request_id: Order change request ID (ocr_xxx)
            
        Returns:
            dict: Full change request details with offers
        """
        url = f"{self.base_url}/air/order_change_requests/{request_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()["data"]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching change request {request_id}: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch change request: {str(e)}"
            )
    
    def get_change_offers(self, request_id: str):
        """
        Get available change offers for a change request
        
        Args:
            request_id: Order change request ID
            
        Returns:
            list: List of available change offers with pricing
        """
        change_request = self.get_change_request(request_id)
        offers = change_request.get("order_change_offers", [])
        
        # Format offers for easier consumption
        formatted_offers = []
        for offer in offers:
            formatted_offers.append({
                "id": offer["id"],
                "change_total_amount": offer.get("change_total_amount"),
                "change_total_currency": offer.get("change_total_currency"),
                "new_total_amount": offer.get("new_total_amount"),
                "new_total_currency": offer.get("new_total_currency"),
                "penalty_total_amount": offer.get("penalty_total_amount"),
                "penalty_total_currency": offer.get("penalty_total_currency"),
                "expires_at": offer.get("expires_at"),
                "slices": offer.get("slices"),
                "conditions": offer.get("conditions")
            })
        
        return formatted_offers
    
    def get_single_change_offer(self, offer_id: str):
        """
        Get a single order change offer by ID
        
        Args:
            offer_id: Order change offer ID (oco_xxx)
            
        Returns:
            dict: Full offer details
        """
        url = f"{self.base_url}/air/order_change_offers/{offer_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()["data"]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching change offer {offer_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch change offer: {str(e)}"
            )
    
    def confirm_change(self, offer_id: str, user_id: str, payment_amount: float):
        """
        Confirm an order change
        
        Args:
            offer_id: Order change offer ID to confirm
            user_id: User ID to verify ownership
            payment_amount: Amount to pay for the change
            
        Returns:
            dict: Confirmed order change details
        """
        # 1. Get the offer details first
        offer = self.get_single_change_offer(offer_id)
        
        # 2. Verify the order belongs to the user
        order_id = offer.get("order_change_id")  # This links back to the order
        
        # 3. Create the pending order change
        url = f"{self.base_url}/air/order_changes"
        payload = {
            "data": {
                "selected_order_change_offer": offer_id
            }
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            order_change = response.json()["data"]
            change_id = order_change["id"]
            print(f"📋 Order change created: {change_id}")

            # 4. Confirm the order change with payment (2-step like cancellation)
            confirm_url = f"{self.base_url}/air/order_changes/{change_id}/actions/confirm"
            confirm_payload = {
                "data": {
                    "payment": {
                        "amount": str(payment_amount),
                        "currency": "USD",
                        "type": "balance"
                    }
                }
            }
            confirm_response = requests.post(confirm_url, headers=self.headers, json=confirm_payload)
            confirm_response.raise_for_status()
            confirmed_change = confirm_response.json()["data"]
            print(f"✅ Order change confirmed: {confirmed_change.get('confirmed_at')}")

            # 5. Update database with new order information via raw SQL
            from app.db.database import engine as _engine
            from sqlalchemy import text as _text
            try:
                new_order_id = confirmed_change.get("order_id")
                penalty = float(offer.get("penalty_total_amount", 0))
                new_total = float(offer.get("new_total_amount", 0))
                with _engine.connect() as _conn:
                    _conn.execute(
                        _text("""UPDATE trips SET previous_order_id = duffel_order_id,
                                 duffel_order_id = :new_oid,
                                 change_penalty_amount = :penalty,
                                 total_amount = :new_total
                                 WHERE user_id = :uid AND change_request_id IS NOT NULL"""),
                        {"new_oid": new_order_id, "penalty": penalty, "new_total": new_total, "uid": user_id}
                    )
                    _conn.commit()
            except Exception as db_err:
                print(f"⚠️ DB update after change failed: {db_err}")

            return {
                "status": "confirmed",
                "order_change_id": confirmed_change["id"],
                "new_order_id": confirmed_change.get("order_id"),
                "confirmed_at": confirmed_change.get("confirmed_at"),
                "change_amount": offer.get("change_total_amount"),
                "penalty_amount": offer.get("penalty_total_amount"),
                "new_total_amount": offer.get("new_total_amount"),
                "confirmation": confirmed_change
            }

        except requests.exceptions.RequestException as e:
            print(f"Error confirming change for offer {offer_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to confirm order change: {str(e)}"
            )
