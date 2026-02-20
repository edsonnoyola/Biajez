import os
import requests
from sqlalchemy.orm import Session
from app.models.models import AirlineCredit, CreditTypeEnum
from fastapi import HTTPException
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

class AirlineCreditsService:
    """Manages airline credits: creation, retrieval, validation, and redemption"""
    
    def __init__(self, db: Session):
        self.db = db
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")
        self.base_url = "https://api.duffel.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Duffel-Version": "v2"
        }
    
    def create_credit(
        self,
        user_id: str,
        airline_iata_code: str,
        amount: float,
        currency: str,
        order_id: Optional[str] = None,
        credit_code: Optional[str] = None,
        expires_days: int = 365
    ) -> Dict:
        """
        Create an airline credit (local and optionally sync with Duffel)
        
        Args:
            user_id: User ID who owns the credit
            airline_iata_code: 2-letter airline code (e.g., "AM", "AA")
            amount: Credit amount
            currency: Currency code (e.g., "USD", "MXN")
            order_id: Optional order ID that generated this credit
            credit_code: Optional airline-provided credit code
            expires_days: Days until expiration (default 365)
            
        Returns:
            dict: Created credit details
        """
        # Calculate expiration date
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        issued_on = date.today()
        
        # Create credit in local database
        credit = AirlineCredit(
            user_id=user_id,
            airline_iata_code=airline_iata_code.upper(),
            credit_amount=amount,
            credit_currency=currency.upper(),
            credit_code=credit_code,
            credit_name=f"{airline_iata_code} Flight Credit",
            expires_at=expires_at,
            order_id=order_id,
            issued_on=issued_on,
            type=CreditTypeEnum.ETICKET,
            created_at=datetime.now().isoformat()
        )
        
        self.db.add(credit)
        self.db.commit()
        self.db.refresh(credit)
        
        return {
            "id": credit.id,
            "user_id": credit.user_id,
            "airline_iata_code": credit.airline_iata_code,
            "credit_amount": float(credit.credit_amount),
            "credit_currency": credit.credit_currency,
            "credit_code": credit.credit_code,
            "expires_at": credit.expires_at,
            "created_at": credit.created_at
        }
    
    def get_user_credits(self, user_id: str, include_spent: bool = False) -> List[Dict]:
        """
        Get all credits for a user
        
        Args:
            user_id: User ID
            include_spent: Whether to include already-spent credits
            
        Returns:
            list: List of credit dictionaries
        """
        query = self.db.query(AirlineCredit).filter(
            AirlineCredit.user_id == user_id
        )
        
        if not include_spent:
            query = query.filter(AirlineCredit.spent_at.is_(None))
        
        credits = query.all()
        
        result = []
        for credit in credits:
            # Check if expired
            is_expired = False
            if credit.expires_at:
                try:
                    exp_date = datetime.fromisoformat(credit.expires_at)
                    is_expired = exp_date < datetime.now()
                except:
                    pass
            
            # Check if valid (not spent, not invalidated, not expired)
            is_valid = (
                credit.spent_at is None and 
                credit.invalidated_at is None and 
                not is_expired
            )
            
            result.append({
                "id": credit.id,
                "airline_iata_code": credit.airline_iata_code,
                "credit_amount": float(credit.credit_amount),
                "credit_currency": credit.credit_currency,
                "credit_name": credit.credit_name,
                "credit_code": credit.credit_code,
                "expires_at": credit.expires_at,
                "spent_at": credit.spent_at,
                "invalidated_at": credit.invalidated_at,
                "order_id": credit.order_id,
                "issued_on": credit.issued_on.isoformat() if credit.issued_on else None,
                "is_valid": is_valid,
                "is_expired": is_expired,
                "created_at": credit.created_at
            })
        
        return result
    
    def get_available_credits_for_airline(
        self, 
        user_id: str, 
        airline_iata_code: str
    ) -> List[Dict]:
        """
        Get available (valid, not spent) credits for a specific airline
        
        Args:
            user_id: User ID
            airline_iata_code: Airline code (e.g., "AM")
            
        Returns:
            list: List of available credits for that airline
        """
        all_credits = self.get_user_credits(user_id, include_spent=False)
        
        # Filter by airline and validity
        available = [
            c for c in all_credits 
            if c["airline_iata_code"] == airline_iata_code.upper() 
            and c["is_valid"]
        ]
        
        return available
    
    def get_credit_details(self, credit_id: str) -> Dict:
        """
        Get details of a specific credit
        
        Args:
            credit_id: Credit ID
            
        Returns:
            dict: Credit details
        """
        credit = self.db.query(AirlineCredit).filter(
            AirlineCredit.id == credit_id
        ).first()
        
        if not credit:
            raise HTTPException(status_code=404, detail="Credit not found")
        
        # Check if expired
        is_expired = False
        if credit.expires_at:
            try:
                exp_date = datetime.fromisoformat(credit.expires_at)
                is_expired = exp_date < datetime.now()
            except:
                pass
        
        return {
            "id": credit.id,
            "user_id": credit.user_id,
            "airline_iata_code": credit.airline_iata_code,
            "credit_amount": float(credit.credit_amount),
            "credit_currency": credit.credit_currency,
            "credit_name": credit.credit_name,
            "credit_code": credit.credit_code,
            "expires_at": credit.expires_at,
            "spent_at": credit.spent_at,
            "invalidated_at": credit.invalidated_at,
            "order_id": credit.order_id,
            "passenger_id": credit.passenger_id,
            "issued_on": credit.issued_on.isoformat() if credit.issued_on else None,
            "type": credit.type.value if credit.type else None,
            "is_expired": is_expired,
            "created_at": credit.created_at
        }
    
    def validate_credit(self, credit_id: str, airline_iata_code: str) -> bool:
        """
        Validate if a credit can be used
        
        Args:
            credit_id: Credit ID
            airline_iata_code: Airline code for the booking
            
        Returns:
            bool: True if credit is valid and can be used
        """
        credit = self.db.query(AirlineCredit).filter(
            AirlineCredit.id == credit_id
        ).first()
        
        if not credit:
            return False
        
        # Check if already spent
        if credit.spent_at:
            return False
        
        # Check if invalidated
        if credit.invalidated_at:
            return False
        
        # Check if expired
        if credit.expires_at:
            try:
                exp_date = datetime.fromisoformat(credit.expires_at)
                if exp_date < datetime.now():
                    return False
            except:
                return False
        
        # Check if airline matches
        if credit.airline_iata_code != airline_iata_code.upper():
            return False
        
        return True
    
    def mark_credit_as_spent(self, credit_id: str, order_id: str) -> Dict:
        """
        Mark a credit as spent/used
        
        Args:
            credit_id: Credit ID
            order_id: Order ID where credit was used
            
        Returns:
            dict: Updated credit details
        """
        credit = self.db.query(AirlineCredit).filter(
            AirlineCredit.id == credit_id
        ).first()
        
        if not credit:
            raise HTTPException(status_code=404, detail="Credit not found")
        
        if credit.spent_at:
            raise HTTPException(status_code=400, detail="Credit already spent")
        
        credit.spent_at = datetime.now().isoformat()
        credit.order_id = order_id
        
        self.db.commit()
        self.db.refresh(credit)
        
        return {
            "id": credit.id,
            "spent_at": credit.spent_at,
            "order_id": credit.order_id,
            "status": "spent"
        }
    
    def get_total_available_balance(self, user_id: str) -> Dict[str, float]:
        """
        Get total available credit balance by currency
        
        Args:
            user_id: User ID
            
        Returns:
            dict: Balance by currency (e.g., {"USD": 150.00, "MXN": 3000.00})
        """
        credits = self.get_user_credits(user_id, include_spent=False)
        
        balances = {}
        for credit in credits:
            if credit["is_valid"]:
                currency = credit["credit_currency"]
                amount = credit["credit_amount"]
                balances[currency] = balances.get(currency, 0) + amount
        
        return balances
