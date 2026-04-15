from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.process_step import ProcessStepCompleteRequest, ProcessStepCreate, ProcessStepRead, ProcessStepUpdate
from app.services import analytics as analytics_service
from app.services import process_steps as process_step_service


router = APIRouter(prefix="/process-steps", tags=["Process Steps"])


@router.post("", response_model=ProcessStepRead, summary="Create a process step for a batch.")
def create_process_step(payload: ProcessStepCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    step = process_step_service.create_process_step(db, current_manager, payload)
    return analytics_service.serialize_process_step(step)


@router.get("", response_model=List[ProcessStepRead], summary="List process steps, optionally filtered by batch.")
def list_process_steps(batch_id: Optional[UUID] = Query(default=None), db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    steps = process_step_service.list_process_steps(db, current_manager, batch_id=batch_id)
    return [analytics_service.serialize_process_step(step) for step in steps]


@router.get("/{step_id}", response_model=ProcessStepRead, summary="Get a single process step.")
def get_process_step(step_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    step = process_step_service.get_process_step(db, current_manager, step_id)
    return analytics_service.serialize_process_step(step)


@router.patch("/{step_id}", response_model=ProcessStepRead, summary="Update a process step.")
def update_process_step(step_id: UUID, payload: ProcessStepUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    step = process_step_service.update_process_step(db, current_manager, step_id, payload)
    return analytics_service.serialize_process_step(step)


@router.post("/{step_id}/complete", response_model=ProcessStepRead, summary="Complete a process step and optionally complete its batch.")
def complete_process_step(step_id: UUID, payload: ProcessStepCompleteRequest, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    step = process_step_service.complete_process_step(db, current_manager, step_id, payload.mark_batch_completed)
    return analytics_service.serialize_process_step(step)
