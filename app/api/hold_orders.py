"""
Hold Orders API - Reserve flights without immediate payment
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.db.database import get_db
from app.services.hold_order_service import HoldOrderService

router = APIRouter(prefix="/api/hold-orders", tags=["hold-orders"])


class PassengerInfo(BaseModel):
    type: str = "adult"
    given_name: str
    family_name: str
    gender: str
    born_on: str
    email: str
    phone_number: str


class CreateHoldRequest(BaseModel):
    offer_id: str
    passengers: List[PassengerInfo]
    metadata: Optional[Dict] = None


class PayHoldRequest(BaseModel):
    order_id: str
    currency: str = "USD"
    amount: str


@router.get("/check/{offer_id}")
async def check_hold_availability(offer_id: str):
    """Check if an offer supports hold/pay later"""
    service = HoldOrderService()
    result = await service.check_hold_availability(offer_id)
    return result


@router.post("/create")
async def create_hold_order(data: CreateHoldRequest):
    """Create a held order (reserve without paying)"""
    service = HoldOrderService()
    passengers = [p.model_dump() for p in data.passengers]
    result = await service.create_hold_order(
        offer_id=data.offer_id,
        passengers=passengers,
        metadata=data.metadata
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/pay")
async def pay_held_order(data: PayHoldRequest):
    """Complete payment for a held order"""
    service = HoldOrderService()
    payment_info = {
        "currency": data.currency,
        "amount": data.amount
    }
    result = await service.pay_held_order(data.order_id, payment_info)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/user/{user_id}")
def get_user_held_orders(user_id: str, db: Session = Depends(get_db)):
    """Get user's held orders that need payment"""
    import asyncio
    service = HoldOrderService()
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(service.get_held_orders(user_id, db))
        return {"held_orders": result}
    finally:
        loop.close()
