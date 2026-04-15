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
    return AuthUserResponse.model_validate(current_user)
