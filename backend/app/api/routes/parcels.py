from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_cooperative_deleter, get_current_cooperative_user, get_current_cooperative_writer
from app.db.session import get_db
from app.schemas.parcel import ParcelCreate, ParcelRead, ParcelUpdate
from app.schemas.pre_harvest import PreHarvestInitResponse, PreHarvestStepRead, PreHarvestStepUpdate
from app.services import parcels as parcel_service


router = APIRouter(tags=["Parcels & Culture"])


@router.get("/parcels", response_model=List[ParcelRead], summary="List parcels, optionally filtered by farmer/member.")
def list_parcels(
    member_id: Optional[UUID] = Query(default=None),
    farmer_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_cooperative_user),
):
    target_member = farmer_id or member_id
    rows = parcel_service.list_parcels(db, current_user, member_id=target_member)
    return [ParcelRead.model_validate(row) for row in rows]


@router.post("/parcels", response_model=ParcelRead, summary="Create parcel and initialize default pre-harvest steps.")
def create_parcel(payload: ParcelCreate, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_writer)):
    row = parcel_service.create_parcel(db, current_user, payload)
    return ParcelRead.model_validate(row)


@router.put("/parcels/{parcel_id}", response_model=ParcelRead, summary="Update parcel.")
def update_parcel(parcel_id: UUID, payload: ParcelUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_writer)):
    row = parcel_service.update_parcel(db, current_user, parcel_id, payload)
    return ParcelRead.model_validate(row)


@router.delete("/parcels/{parcel_id}", status_code=204, summary="Delete parcel (owner/admin only).")
def delete_parcel(parcel_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_deleter)):
    parcel_service.delete_parcel(db, current_user, parcel_id)
    return None


@router.get("/parcels/{parcel_id}/pre-harvest", response_model=List[PreHarvestStepRead], summary="List pre-harvest lifecycle steps for a parcel.")
def list_pre_harvest_steps(parcel_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = parcel_service.list_pre_harvest_steps(db, current_user, parcel_id)
    return [PreHarvestStepRead.model_validate(item) for item in rows]


@router.get("/parcels/{parcel_id}/pre-harvest-steps", response_model=List[PreHarvestStepRead], summary="List pre-harvest lifecycle steps for a parcel.")
def list_pre_harvest_steps_alias(parcel_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = parcel_service.list_pre_harvest_steps(db, current_user, parcel_id)
    return [PreHarvestStepRead.model_validate(item) for item in rows]


@router.post("/parcels/{parcel_id}/pre-harvest/init", response_model=PreHarvestInitResponse, summary="Initialize default pre-harvest steps for parcel.")
def init_pre_harvest_steps(parcel_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_writer)):
    created = parcel_service.init_pre_harvest_steps(db, current_user, parcel_id)
    return PreHarvestInitResponse(parcel_id=parcel_id, created_steps=created)


@router.put("/pre-harvest-events/{step_id}", response_model=PreHarvestStepRead, summary="Update a pre-harvest step and mark it completed.")
def update_pre_harvest_step(
    step_id: UUID,
    parcel_id: UUID = Query(...),
    payload: PreHarvestStepUpdate = ...,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_cooperative_writer),
):
    item = parcel_service.update_pre_harvest_step(db, current_user, parcel_id, step_id, payload)
    return PreHarvestStepRead.model_validate(item)


@router.put("/parcels/{parcel_id}/pre-harvest-steps/{step_id}", response_model=PreHarvestStepRead, summary="Update pre-harvest step by parcel.")
def update_pre_harvest_step_alias(
    parcel_id: UUID,
    step_id: UUID,
    payload: PreHarvestStepUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_cooperative_writer),
):
    item = parcel_service.update_pre_harvest_step(db, current_user, parcel_id, step_id, payload)
    return PreHarvestStepRead.model_validate(item)


@router.post("/pre-harvest-events/{step_id}/complete", response_model=PreHarvestStepRead, summary="Mark pre-harvest step as completed.")
def complete_pre_harvest_step(
    step_id: UUID,
    parcel_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_cooperative_writer),
):
    item = parcel_service.complete_pre_harvest_step(db, current_user, parcel_id, step_id)
    return PreHarvestStepRead.model_validate(item)


@router.post("/parcels/{parcel_id}/pre-harvest-steps/{step_id}/complete", response_model=PreHarvestStepRead, summary="Mark pre-harvest step as completed.")
def complete_pre_harvest_step_alias(
    parcel_id: UUID,
    step_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_cooperative_writer),
):
    item = parcel_service.complete_pre_harvest_step(db, current_user, parcel_id, step_id)
    return PreHarvestStepRead.model_validate(item)
