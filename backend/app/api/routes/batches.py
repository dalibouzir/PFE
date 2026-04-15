from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.batch import BatchCreate, BatchRead, BatchStatusUpdate
from app.services import batches as batch_service


router = APIRouter(prefix="/batches", tags=["Batches"])


@router.post("", response_model=BatchRead, summary="Create a new processing batch.")
def create_batch(payload: BatchCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.create_batch(db, current_manager, payload)
    return BatchRead.model_validate(batch)


@router.get("", response_model=List[BatchRead], summary="List batches in the current cooperative.")
def list_batches(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batches = batch_service.list_batches(db, current_manager)
    return [BatchRead.model_validate(batch) for batch in batches]


@router.get("/{batch_id}", response_model=BatchRead, summary="Get a single batch.")
def get_batch(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.require_batch(db, current_manager, batch_id, with_steps=True)
    return BatchRead.model_validate(batch)


@router.patch("/{batch_id}/status", response_model=BatchRead, summary="Update a batch status.")
def update_batch_status(batch_id: UUID, payload: BatchStatusUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    batch = batch_service.update_batch_status(db, current_manager, batch_id, payload)
    return BatchRead.model_validate(batch)
