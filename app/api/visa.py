"""
Visa Requirements API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.visa_service import VisaService

router = APIRouter(prefix="/v1/visa", tags=["Visa"])


@router.get("/requirements")
async def check_visa_requirements(
    passport_country: str,
    destination: str,
    db: Session = Depends(get_db)
):
    """
    Check visa requirements for a destination

    Query params:
        passport_country: 2-letter country code of passport (e.g., MX, US)
        destination: IATA airport code or country code

    Returns:
        Visa requirement details
    """
    service = VisaService(db)
    result = service.check_visa_requirement(
        passport_country=passport_country,
        destination=destination
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/requirements/{user_id}")
async def check_visa_for_user(
    user_id: str,
    destination: str,
    db: Session = Depends(get_db)
):
    """
    Check visa requirements using user's passport country

    URL params:
        user_id: User ID

    Query params:
        destination: IATA airport code or country code

    Returns:
        Visa requirement details based on user's passport
    """
    service = VisaService(db)
    result = service.check_visa_for_user(user_id, destination)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result
