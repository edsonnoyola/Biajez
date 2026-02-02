"""
Check-in API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.checkin_service import CheckinService
from pydantic import BaseModel

router = APIRouter(prefix="/v1/checkin", tags=["Check-in"])


class ScheduleCheckinRequest(BaseModel):
    trip_id: str
    airline_code: str
    pnr: str
    passenger_last_name: str
    departure_time: str


@router.post("/schedule")
async def schedule_auto_checkin(
    user_id: str,
    request: ScheduleCheckinRequest,
    db: Session = Depends(get_db)
):
    """
    Schedule automatic check-in for a flight

    Query params:
        user_id: User ID

    Body:
        trip_id: Trip booking reference
        airline_code: Airline IATA code (e.g., AM, AA)
        pnr: PNR/confirmation number
        passenger_last_name: Passenger's last name
        departure_time: ISO format departure time

    Returns:
        Scheduling result with scheduled time
    """
    service = CheckinService(db)
    result = service.schedule_auto_checkin(
        user_id=user_id,
        trip_id=request.trip_id,
        airline_code=request.airline_code,
        pnr=request.pnr,
        passenger_last_name=request.passenger_last_name,
        departure_time=request.departure_time
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/status/{trip_id}")
async def get_checkin_status(
    trip_id: str,
    db: Session = Depends(get_db)
):
    """
    Get check-in status for a trip

    URL params:
        trip_id: Trip booking reference

    Returns:
        Check-in status and auto check-in info if scheduled
    """
    service = CheckinService(db)
    result = service.get_checkin_status(trip_id)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.post("/process")
async def trigger_checkin_processing(db: Session = Depends(get_db)):
    """
    Manually trigger check-in processing (admin/debug endpoint)

    Returns:
        Processing results summary
    """
    service = CheckinService(db)
    return await service.process_pending_checkins()
