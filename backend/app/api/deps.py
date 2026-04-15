from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import decode_access_token
from app.crud.common import require_by_id
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.utils.exceptions import AuthenticationError, ForbiddenError


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise AuthenticationError("Could not validate access token.") from exc

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Token subject is missing.")

    try:
        user_id = UUID(str(subject))
    except ValueError as exc:
        raise AuthenticationError("Token subject is invalid.") from exc

    user = require_by_id(db, User, user_id, "User")
    if user.status == UserStatus.DISABLED:
        raise ForbiddenError("This account has been disabled.")
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access is required.")
    return current_user


def get_current_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.MANAGER:
        raise ForbiddenError("Manager access is required.")
    return current_user
