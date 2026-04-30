from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_cooperative_user
from app.db.session import get_db
from app.schemas.member import MemberRead
from app.schemas.parcel import ParcelRead
from app.services import members as member_service
from app.services import parcels as parcel_service


router = APIRouter(prefix="/farmers", tags=["Farmers"])


@router.get("", response_model=List[MemberRead], summary="List farmers (members) with derived parcel stats.")
def list_farmers(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    items = member_service.list_members(db, current_user)
    return [MemberRead.model_validate(item) for item in items]


@router.get("/{farmer_id}", response_model=MemberRead, summary="Get farmer profile.")
def get_farmer(farmer_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    item = member_service.require_member(db, current_user, farmer_id)
    return MemberRead.model_validate(item)


@router.get("/{farmer_id}/parcels", response_model=List[ParcelRead], summary="List parcels linked to a farmer.")
def list_farmer_parcels(farmer_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = parcel_service.list_parcels(db, current_user, member_id=farmer_id)
    return [ParcelRead.model_validate(item) for item in rows]
