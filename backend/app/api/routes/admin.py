from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.schemas.cooperative import CooperativeCreate, CooperativeRead
from app.schemas.user import ManagerCreate, UserRead
from app.services import admin as admin_service


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/cooperatives", response_model=CooperativeRead, summary="Create a cooperative.")
def create_cooperative(payload: CooperativeCreate, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    cooperative = admin_service.create_cooperative(db, payload)
    return CooperativeRead.model_validate(cooperative)


@router.post("/managers", response_model=UserRead, summary="Create a manager account linked to a cooperative.")
def create_manager(payload: ManagerCreate, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    manager = admin_service.create_manager(db, payload)
    return UserRead.model_validate(manager)


@router.patch("/users/{user_id}/disable", response_model=UserRead, summary="Disable a user account.")
def disable_user(user_id: UUID, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    user = admin_service.disable_user(db, user_id)
    return UserRead.model_validate(user)


@router.get("/users", response_model=List[UserRead], summary="List all users.")
def list_users(db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    users = admin_service.list_users(db)
    return [UserRead.model_validate(user) for user in users]


@router.get("/cooperatives", response_model=List[CooperativeRead], summary="List all cooperatives.")
def list_cooperatives(db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    cooperatives = admin_service.list_cooperatives(db)
    return [CooperativeRead.model_validate(item) for item in cooperatives]
