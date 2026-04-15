from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.user import get_user_by_email
from app.models.enums import UserStatus
from app.schemas.auth import LoginRequest, TokenResponse
from app.utils.exceptions import AuthenticationError, ForbiddenError


def authenticate_user(db: Session, login_data: LoginRequest):
    user = get_user_by_email(db, login_data.email)
    if user is None or not verify_password(login_data.password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")
    if user.status == UserStatus.DISABLED:
        raise ForbiddenError("This account has been disabled.")
    return user


def login(db: Session, login_data: LoginRequest) -> TokenResponse:
    user = authenticate_user(db, login_data)
    token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims={"role": user.role.value},
    )
    return TokenResponse(access_token=token)
