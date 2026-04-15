from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.field import FieldCreate, FieldRead, FieldUpdate
from app.services import fields as field_service


router = APIRouter(prefix="/fields", tags=["Fields"])


@router.post("", response_model=FieldRead, summary="Create a field for a cooperative member.")
def create_field(payload: FieldCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    field = field_service.create_field(db, current_manager, payload)
    return FieldRead.model_validate(field)


@router.get("", response_model=List[FieldRead], summary="List fields in the current cooperative.")
def list_fields(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    fields = field_service.list_fields(db, current_manager)
    return [FieldRead.model_validate(field) for field in fields]


@router.patch("/{field_id}", response_model=FieldRead, summary="Update a field.")
def update_field(field_id: UUID, payload: FieldUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    field = field_service.update_field(db, current_manager, field_id, payload)
    return FieldRead.model_validate(field)
