"""
Baggage API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.baggage_service import BaggageService
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/v1/baggage", tags=["Baggage"])


class AddBaggageRequest(BaseModel):
    service_ids: List[str]


@router.get("/options/{order_id}")
async def get_baggage_options(
    order_id: str,
    db: Session = Depends(get_db)
):
    """
    Get available baggage options for a Duffel order

    URL params:
        order_id: Duffel order ID (ord_xxx)

    Returns:
        Current baggage info and available add-on options
    """
    service = BaggageService(db)
    result = service.get_baggage_options(order_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/trip/{pnr}")
async def get_trip_baggage(
    pnr: str,
    db: Session = Depends(get_db)
):
    """
    Get baggage info for a trip by PNR

    URL params:
        pnr: Booking reference (PNR)

    Returns:
        Baggage information
    """
    service = BaggageService(db)
    result = service.get_trip_baggage(pnr)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.post("/add/{order_id}")
async def add_baggage(
    order_id: str,
    request: AddBaggageRequest,
    db: Session = Depends(get_db)
):
    """
    Add baggage services to an existing order

    URL params:
        order_id: Duffel order ID

    Body:
        service_ids: List of baggage service IDs to add

    Returns:
        Updated order information
    """
    service = BaggageService(db)
    result = service.add_baggage(order_id, request.service_ids)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result
