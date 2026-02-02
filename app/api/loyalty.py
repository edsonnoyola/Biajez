"""
Loyalty Programs API - Manage frequent flyer numbers
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.db.database import get_db
from app.services.loyalty_service import LoyaltyService

router = APIRouter(prefix="/api/loyalty", tags=["loyalty"])


class LoyaltyCreate(BaseModel):
    user_id: str
    airline_code: str
    member_number: str
    tier: Optional[str] = None


class LoyaltyResponse(BaseModel):
    airline_code: str
    program_name: str
    member_number: str
    tier: Optional[str]
    airline: str


@router.post("/", response_model=dict)
def add_loyalty_program(data: LoyaltyCreate, db: Session = Depends(get_db)):
    """Add or update a loyalty program membership"""
    service = LoyaltyService(db)
    result = service.add_loyalty_number(
        user_id=data.user_id,
        airline_code=data.airline_code,
        member_number=data.member_number,
        tier=data.tier
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{user_id}", response_model=List[LoyaltyResponse])
def get_user_loyalty_programs(user_id: str, db: Session = Depends(get_db)):
    """Get all loyalty programs for a user"""
    service = LoyaltyService(db)
    return service.get_user_programs(user_id)


@router.get("/{user_id}/{airline_code}")
def get_loyalty_for_airline(user_id: str, airline_code: str, db: Session = Depends(get_db)):
    """Get loyalty number for specific airline"""
    service = LoyaltyService(db)
    result = service.get_loyalty_for_airline(user_id, airline_code)
    if not result:
        raise HTTPException(status_code=404, detail="Loyalty program not found")
    return result


@router.delete("/{user_id}/{airline_code}")
def delete_loyalty_program(user_id: str, airline_code: str, db: Session = Depends(get_db)):
    """Remove a loyalty program"""
    service = LoyaltyService(db)
    result = service.delete_loyalty(user_id, airline_code)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.get("/programs/list")
def list_available_programs():
    """List all known loyalty programs"""
    return LoyaltyService.PROGRAMS
