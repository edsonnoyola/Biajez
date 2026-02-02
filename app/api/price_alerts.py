"""
Price Alerts API - Monitor prices and get notified on drops
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.db.database import get_db
from app.services.price_alert_service import PriceAlertService

router = APIRouter(prefix="/api/price-alerts", tags=["price-alerts"])


class CreateAlertRequest(BaseModel):
    user_id: str
    phone_number: str
    search_type: str = "flight"  # flight or hotel
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    current_price: float
    target_price: Optional[float] = None  # Auto-set to 10% below current if not provided


class AlertResponse(BaseModel):
    id: int
    user_id: str
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str]
    target_price: float
    current_price: float
    lowest_price: float
    is_active: bool
    notification_count: int


@router.post("/", response_model=dict)
def create_price_alert(data: CreateAlertRequest, db: Session = Depends(get_db)):
    """Create a new price alert"""
    service = PriceAlertService(db)

    # Set target price to 10% below current if not provided
    target = data.target_price or (data.current_price * 0.9)

    result = service.create_alert(
        user_id=data.user_id,
        phone_number=data.phone_number,
        search_type=data.search_type,
        origin=data.origin,
        destination=data.destination,
        departure_date=data.departure_date,
        return_date=data.return_date,
        current_price=data.current_price,
        target_price=target
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{user_id}")
def get_user_alerts(user_id: str, db: Session = Depends(get_db)):
    """Get all active alerts for a user"""
    service = PriceAlertService(db)
    alerts = service.get_user_alerts(user_id)
    return {"alerts": alerts}


@router.delete("/{alert_id}")
def deactivate_alert(alert_id: int, db: Session = Depends(get_db)):
    """Deactivate a price alert"""
    service = PriceAlertService(db)
    result = service.deactivate_alert(alert_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.post("/check")
async def check_alerts_now(db: Session = Depends(get_db)):
    """Manually trigger price check for all active alerts"""
    service = PriceAlertService(db)
    results = await service.check_all_alerts()
    return {
        "checked": len(results),
        "results": results
    }
