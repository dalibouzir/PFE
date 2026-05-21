from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import AuthUserResponse, LoginRequest, TokenResponse
from app.services import auth as auth_service


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse, summary="Authenticate a user and return a JWT access token.")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, payload)


@router.get("/me", response_model=AuthUserResponse, summary="Return the authenticated user's profile.")
def get_me(current_user=Depends(get_current_user)):
    return AuthUserResponse.model_validate(
        {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "role": getattr(current_user.role, "value", str(current_user.role)),
            "status": getattr(current_user.status, "value", str(current_user.status)),
            "cooperative_id": current_user.cooperative_id,
            "cooperative_name": current_user.cooperative.name if getattr(current_user, "cooperative", None) else None,
            "institution_id": current_user.institution_id,
            "institution_name": current_user.institution.name if getattr(current_user, "institution", None) else None,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at,
        }
    )
