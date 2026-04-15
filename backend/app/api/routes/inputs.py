from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.input import InputCreate, InputRead
from app.services import inputs as input_service


router = APIRouter(prefix="/inputs", tags=["Inputs"])


@router.post("", response_model=InputRead, summary="Record a member input collection.")
def create_input(payload: InputCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    input_record = input_service.record_input(db, current_manager, payload)
    return InputRead.model_validate(input_record)


@router.get("", response_model=List[InputRead], summary="List input records for the current cooperative.")
def list_inputs(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    inputs = input_service.list_inputs(db, current_manager)
    return [InputRead.model_validate(item) for item in inputs]


@router.get("/{input_id}", response_model=InputRead, summary="Get a single input record.")
def get_input(input_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    input_record = input_service.get_input(db, current_manager, input_id)
    return InputRead.model_validate(input_record)
