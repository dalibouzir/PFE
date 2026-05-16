from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import decode_access_token
from app.crud.common import require_by_id
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus
from app.services.helpers import (
    ensure_user_can_access_cooperative_by_institution_or_global as ensure_user_can_access_cooperative_by_institution_or_global_helper,
    ensure_user_can_access_institution as ensure_user_can_access_institution_helper,
    get_user_institution_scope as get_user_institution_scope_helper,
    is_institution_admin as is_institution_admin_helper,
    is_super_admin as is_super_admin_helper,
)
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


def is_super_admin(current_user: User) -> bool:
    return is_super_admin_helper(current_user)


def is_institution_admin(current_user: User) -> bool:
    return is_institution_admin_helper(current_user)


def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_super_admin(current_user):
        raise ForbiddenError("Super admin access is required.")
    return current_user


def get_current_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        raise ForbiddenError("Platform admin access is required.")
    return current_user


def get_current_institution_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_institution_admin(current_user):
        raise ForbiddenError("Institution admin access is required.")
    return current_user


def get_user_institution_scope(current_user: User = Depends(get_current_user)):
    return get_user_institution_scope_helper(current_user)


def ensure_user_can_access_institution(db: Session, current_user: User, institution_id):
    return ensure_user_can_access_institution_helper(db, current_user, institution_id)


def ensure_user_can_access_cooperative_by_institution_or_global(db: Session, current_user: User, cooperative_id):
    return ensure_user_can_access_cooperative_by_institution_or_global_helper(db, current_user, cooperative_id)


def get_current_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.MANAGER:
        raise ForbiddenError("Manager access is required.")
    return current_user


def get_current_cooperative_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER, UserRole.VIEWER}:
        raise ForbiddenError("Cooperative access is required.")
    return current_user


def get_current_cooperative_writer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}:
        raise ForbiddenError("Write access is required.")
    return current_user


def get_current_cooperative_deleter(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        raise ForbiddenError("Delete access is required.")
    return current_user
