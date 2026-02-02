"""
Itinerary API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.itinerary_service import ItineraryService

router = APIRouter(prefix="/v1/itinerary", tags=["Itinerary"])


@router.get("/{user_id}")
async def get_user_itineraries(
    user_id: str,
    include_past: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get all itineraries for a user

    URL params:
        user_id: User ID

    Query params:
        include_past: Include past/cancelled trips (default: false)

    Returns:
        List of trip summaries
    """
    service = ItineraryService(db)
    return service.get_user_itineraries(user_id, include_past)


@router.get("/trip/{pnr}")
async def get_trip_itinerary(
    pnr: str,
    user_id: str = None,
    db: Session = Depends(get_db)
):
    """
    Get detailed itinerary for a specific trip

    URL params:
        pnr: Booking reference

    Query params:
        user_id: Optional user ID for verification

    Returns:
        Complete trip details
    """
    service = ItineraryService(db)
    result = service.get_trip_itinerary(pnr, user_id)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.get("/upcoming/{user_id}")
async def get_upcoming_trip(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the next upcoming trip for a user

    URL params:
        user_id: User ID

    Returns:
        Next trip details or null
    """
    service = ItineraryService(db)
    result = service.get_upcoming_trip(user_id)

    if not result:
        return {"message": "No upcoming trips found"}

    return result
