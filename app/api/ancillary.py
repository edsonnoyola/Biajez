"""
Ancillary Services API - Meals, WiFi, extras
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.ancillary_service import AncillaryService

router = APIRouter(prefix="/api/ancillary", tags=["ancillary"])


class AddServicesRequest(BaseModel):
    order_id: str
    service_ids: List[str]


@router.get("/available/{offer_id}")
async def get_available_services(offer_id: str):
    """Get available ancillary services for a flight offer"""
    service = AncillaryService()
    result = await service.get_available_services(offer_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/add")
async def add_services_to_order(data: AddServicesRequest):
    """Add ancillary services to an existing order"""
    service = AncillaryService()
    result = await service.add_service_to_order(data.order_id, data.service_ids)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/order/{order_id}")
async def get_order_services(order_id: str):
    """Get services already added to an order"""
    service = AncillaryService()
    result = await service.get_order_services(order_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/types")
def get_service_types():
    """List available service types"""
    return {
        "service_types": AncillaryService.SERVICE_TYPES,
        "meal_options": AncillaryService.MEAL_OPTIONS
    }
