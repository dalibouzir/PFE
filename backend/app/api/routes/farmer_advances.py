from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.farmer_advance import (
    FarmerAdvanceCreate,
    FarmerAdvanceFarmerDetailResponse,
    FarmerAdvanceRead,
    FarmerAdvanceSummaryResponse,
    FarmerAdvanceUpdate,
)
from app.services import farmer_advances as farmer_advance_service


router = APIRouter(prefix="/farmer-advances", tags=["Farmer Advances"])


@router.get("/summary", response_model=FarmerAdvanceSummaryResponse, summary="List farmer advances aggregated by farmer.")
def list_farmer_advances_summary(
    search: str | None = Query(default=None),
    sort_by: str = Query(default="last_modified"),
    order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return farmer_advance_service.list_farmer_advances_summary(
        db=db,
        manager=current_manager,
        search=search,
        sort_by=sort_by,
        order=order,
    )


@router.get("/farmer/{farmer_id}", response_model=FarmerAdvanceFarmerDetailResponse, summary="Get all advances details for one farmer.")
def get_farmer_advances_detail(farmer_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return farmer_advance_service.get_farmer_advances_detail(db, current_manager, farmer_id)


@router.post("", response_model=FarmerAdvanceRead, summary="Create a new farmer advance and linked treasury transaction.")
def create_farmer_advance(payload: FarmerAdvanceCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return farmer_advance_service.create_farmer_advance(db, current_manager, payload)


@router.put("/{advance_id}", response_model=FarmerAdvanceRead, summary="Update a farmer advance and sync linked treasury transaction.")
def update_farmer_advance(
    advance_id: UUID,
    payload: FarmerAdvanceUpdate,
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return farmer_advance_service.update_farmer_advance(db, current_manager, advance_id, payload)


@router.patch("/{advance_id}/cancel", response_model=FarmerAdvanceRead, summary="Cancel a farmer advance and linked treasury transaction.")
def cancel_farmer_advance(advance_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return farmer_advance_service.cancel_farmer_advance(db, current_manager, advance_id)
