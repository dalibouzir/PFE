from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.batch import (
    BatchApproveChargeResponse,
    BatchCompletePreHarvestRequest,
    BatchCreate,
    BatchMaterialBalanceRead,
    BatchPreHarvestStepStatusesUpdate,
    BatchRead,
    BatchStartPostHarvestRequest,
    BatchStatusUpdate,
    BatchUpdate,
)
from app.services import batches as batch_service


router = APIRouter(prefix="/batches", tags=["Batches"])


@router.get("/reference-preview", summary="Preview the next auto-generated lot reference for a product.")
def preview_lot_reference(
    product_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    code = batch_service.preview_next_batch_reference(db, current_manager, product_id)
    return {"code": code}


@router.post("", response_model=BatchRead, summary="Create a new processing batch.")
def create_batch(payload: BatchCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.create_batch(db, current_manager, payload)
    return batch_service.serialize_batch(batch)


@router.get("", response_model=List[BatchRead], summary="List batches in the current cooperative.")
def list_batches(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batches = batch_service.list_batches(db, current_manager)
    return [batch_service.serialize_batch(batch) for batch in batches]


@router.get("/{batch_id}", response_model=BatchRead, summary="Get a single batch.")
def get_batch(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.require_batch(db, current_manager, batch_id, with_steps=True)
    return batch_service.serialize_batch(batch)


@router.patch("/{batch_id}", response_model=BatchRead, summary="Update batch configuration before execution.")
def update_batch(batch_id: UUID, payload: BatchUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.update_batch(db, current_manager, batch_id, payload)
    return batch_service.serialize_batch(batch)


@router.patch("/{batch_id}/status", response_model=BatchRead, summary="Update a batch status.")
def update_batch_status(batch_id: UUID, payload: BatchStatusUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.update_batch_status(db, current_manager, batch_id, payload)
    return batch_service.serialize_batch(batch)


@router.delete("/{batch_id}", status_code=204, summary="Delete a batch.")
def delete_batch(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch_service.delete_batch(db, current_manager, batch_id)


@router.post("/{batch_id}/approve-charge", response_model=BatchApproveChargeResponse, summary="Approve estimated pre-harvest charge and create linked advance + treasury out once.")
def approve_batch_charge(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.approve_estimated_charge(db, current_manager, batch_id)
    return {"batch": batch_service.serialize_batch(batch)}


@router.post("/{batch_id}/activate-preharvest", response_model=BatchRead, summary="Activate pre-harvest lot once (idempotent) without stock side effects.")
def activate_preharvest(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.activate_preharvest(db, current_manager, batch_id)
    return batch_service.serialize_batch(batch)


@router.post("/{batch_id}/stop-preharvest", response_model=BatchRead, summary="Stop active pre-harvest lot and return to preparation only when execution has not started.")
def stop_preharvest(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.stop_preharvest(db, current_manager, batch_id)
    return batch_service.serialize_batch(batch)

@router.patch("/{batch_id}/preharvest-step-statuses", response_model=BatchRead, summary="Persist active pre-harvest execution statuses.")
def update_preharvest_step_statuses(batch_id: UUID, payload: BatchPreHarvestStepStatusesUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.update_preharvest_step_statuses(db, current_manager, batch_id, payload.statuses)
    return batch_service.serialize_batch(batch)


@router.post("/{batch_id}/complete-preharvest", response_model=BatchRead, summary="Complete pre-harvest and mark lot ready for linked collecte.")
def complete_preharvest(batch_id: UUID, payload: BatchCompletePreHarvestRequest, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.complete_preharvest(
        db,
        current_manager,
        batch_id,
        notes=payload.notes,
        collecte_date=payload.collecte_date,
    )
    return batch_service.serialize_batch(batch)


@router.post("/{batch_id}/start-postharvest", response_model=BatchRead, summary="Start post-harvest lifecycle for a ready lot.")
def start_postharvest(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.start_postharvest(
        db,
        current_manager,
        batch_id,
        payload=None,
    )
    return batch_service.serialize_batch(batch)


@router.post("/{batch_id}/start-postharvest-with-stock", response_model=BatchRead, summary="Start post-harvest by selecting product/grade/quantity stock bucket.")
def start_postharvest_with_stock(
    batch_id: UUID,
    payload: BatchStartPostHarvestRequest,
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    batch = batch_service.start_postharvest(db, current_manager, batch_id, payload=payload)
    return batch_service.serialize_batch(batch)


@router.post("/{batch_id}/complete-postharvest", response_model=BatchRead, summary="Complete post-harvest lifecycle once required steps are done.")
def complete_postharvest(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.complete_postharvest(db, current_manager, batch_id)
    return batch_service.serialize_batch(batch)


@router.get("/{batch_id}/material-balance", response_model=BatchMaterialBalanceRead, summary="Return material balance and per-stage performance for a lot.")
def get_material_balance(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return batch_service.get_material_balance(db, current_manager, batch_id)
