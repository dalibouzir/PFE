from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import SessionLocal, get_db
from app.models.cooperative import Cooperative
from app.models.institution import Institution
from app.schemas.auth import AuthUserResponse, LoginRequest, TokenResponse
from app.services import auth as auth_service


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse, summary="Authenticate a user and return a JWT access token.")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, payload)


@router.get("/me", response_model=AuthUserResponse, summary="Return the authenticated user's profile.")
def get_me(current_user=Depends(get_current_user)):
    payload = {
        "id": current_user.id,
        "full_name": getattr(current_user, "full_name", None) or getattr(current_user, "name", None),
        "email": current_user.email,
        "phone": getattr(current_user, "phone", None),
        "role": getattr(current_user.role, "value", str(current_user.role)),
        "status": getattr(current_user.status, "value", str(current_user.status)),
        "cooperative_id": current_user.cooperative_id,
        "cooperative_name": None,
        "institution_id": current_user.institution_id,
        "institution_name": None,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
    }

    db = SessionLocal()
    try:
        if current_user.cooperative_id is not None:
            payload["cooperative_name"] = db.scalar(
                select(Cooperative.name).where(Cooperative.id == current_user.cooperative_id)
            )
        if current_user.institution_id is not None:
            payload["institution_name"] = db.scalar(
                select(Institution.name).where(Institution.id == current_user.institution_id)
            )
    finally:
        try:
            db.rollback()
        finally:
            db.close()

    return AuthUserResponse.model_validate(payload)
