from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.order_management import OrderManager
from pydantic import BaseModel
from typing import List, Dict, Any


class ChangeRequestBody(BaseModel):
    slices_to_remove: List[Dict[str, Any]]
    slices_to_add: List[Dict[str, Any]]

router = APIRouter()

# ===== ORDER MANAGEMENT ENDPOINTS =====

@router.get("/v1/orders/{user_id}")
def get_user_orders(user_id: str, db: Session = Depends(get_db)):
    """Get all orders for a user"""
    order_manager = OrderManager(db)
    return {"orders": order_manager.get_user_orders(user_id)}

@router.get("/v1/orders/detail/{order_id}")
def get_order_detail(order_id: str, db: Session = Depends(get_db)):
    """Get full details of a specific order from Duffel"""
    order_manager = OrderManager(db)
    return order_manager.get_order_details(order_id)

@router.post("/v1/orders/cancel-quote/{order_id}")
def get_cancellation_quote(order_id: str, db: Session = Depends(get_db)):
    """Get refund quote before cancelling"""
    order_manager = OrderManager(db)
    return order_manager.get_cancellation_quote(order_id)

@router.post("/v1/orders/cancel/{order_id}")
def cancel_order(order_id: str, user_id: str, db: Session = Depends(get_db)):
    """Cancel order and process refund (2-step Duffel: quote + confirm + DB update)"""
    order_manager = OrderManager(db)
    return order_manager.cancel_order(order_id, user_id)


# ===== ORDER CHANGE ENDPOINTS =====

@router.post("/v1/orders/change-request")
def create_change_request(
    order_id: str,
    user_id: str,
    body: ChangeRequestBody = Body(...),
    db: Session = Depends(get_db)
):
    """Create an order change request"""
    from app.services.order_change_service import OrderChangeService
    change_service = OrderChangeService(db)
    return change_service.create_change_request(
        order_id, user_id, body.slices_to_remove, body.slices_to_add
    )

@router.get("/v1/orders/change-request/{request_id}")
def get_change_request(request_id: str, db: Session = Depends(get_db)):
    """Get details of an order change request"""
    from app.services.order_change_service import OrderChangeService
    change_service = OrderChangeService(db)
    return change_service.get_change_request(request_id)

@router.get("/v1/orders/change-offers/{request_id}")
def get_change_offers(request_id: str, db: Session = Depends(get_db)):
    """Get available change offers for a change request"""
    from app.services.order_change_service import OrderChangeService
    change_service = OrderChangeService(db)
    return {"offers": change_service.get_change_offers(request_id)}

@router.post("/v1/orders/change-confirm/{offer_id}")
def confirm_change(
    offer_id: str,
    user_id: str,
    payment_amount: float,
    db: Session = Depends(get_db)
):
    """Confirm an order change"""
    from app.services.order_change_service import OrderChangeService
    change_service = OrderChangeService(db)
    return change_service.confirm_change(offer_id, user_id, payment_amount)
