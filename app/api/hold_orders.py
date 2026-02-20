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
    id: Optional[str] = None
    title: Optional[str] = None


class CreateHoldRequest(BaseModel):
    offer_id: str
    passengers: List[PassengerInfo]
    metadata: Optional[Dict] = None


class PayHoldRequest(BaseModel):
    order_id: str


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
    passengers = [p.model_dump(exclude_none=True) for p in data.passengers]
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
    """
    Pay for a held order.
    Re-fetches latest price from Duffel before paying (per docs).
    """
    service = HoldOrderService()
    result = await service.pay_held_order(data.order_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/status/{order_id}")
async def get_hold_status(order_id: str):
    """Get current status of a held order (price, deadline, awaiting_payment)"""
    service = HoldOrderService()
    result = await service.get_order_status(order_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result
