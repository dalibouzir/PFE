from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.crud.common import require_by_id
from app.crud.user import get_user_by_email
from app.models.cooperative import Cooperative
from app.models.enums import CooperativeStatus, UserRole, UserStatus
from app.models.user import User
from app.schemas.user import CooperativeUserCreate
from app.services.helpers import COOPERATIVE_ROLES, ensure_user_can_access_cooperative_by_institution_or_global, parse_enum_value
from app.utils.exceptions import ConflictError, ForbiddenError, ValidationError


_ALLOWED_CREATE_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.VIEWER}


def _ensure_cooperative_manageable(cooperative: Cooperative):
    if cooperative.status == CooperativeStatus.SUSPENDED:
        raise ValidationError("Cannot manage users for a suspended cooperative.")


def _ensure_target_is_cooperative_user(user: User):
    if user.role not in COOPERATIVE_ROLES:
        raise ForbiddenError("Only cooperative users can be managed by this endpoint.")


def list_cooperative_users(db: Session, current_user: User, cooperative_id):
    cooperative = ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, cooperative_id)

    if current_user.role == UserRole.INSTITUTION_ADMIN and cooperative.institution_id is None:
        raise ForbiddenError("Institution admin cannot manage users for independent cooperatives.")

    return db.scalars(
        select(User)
        .where(User.cooperative_id == cooperative.id, User.role.in_(tuple(role.value for role in COOPERATIVE_ROLES)))
        .order_by(User.created_at.desc())
    ).all()


def create_cooperative_user(db: Session, current_user: User, cooperative_id, payload: CooperativeUserCreate) -> User:
    cooperative = ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, cooperative_id)

    if current_user.role == UserRole.INSTITUTION_ADMIN and cooperative.institution_id is None:
        raise ForbiddenError("Institution admin cannot manage users for independent cooperatives.")

    _ensure_cooperative_manageable(cooperative)

    if get_user_by_email(db, payload.email) is not None:
        raise ConflictError("A user with this email already exists.")

    role = parse_enum_value(UserRole, payload.role, "user role")
    if role not in _ALLOWED_CREATE_ROLES:
        allowed = ", ".join(sorted(item.value for item in _ALLOWED_CREATE_ROLES))
        raise ValidationError(f"Invalid cooperative user role. Expected one of: {allowed}.")

    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.password),
        phone=payload.phone.strip() if payload.phone else None,
        role=role,
        status=UserStatus.ACTIVE,
        cooperative_id=cooperative.id,
        institution_id=cooperative.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def enable_cooperative_user(db: Session, current_user: User, user_id) -> User:
    target = require_by_id(db, User, user_id, "User")
    _ensure_target_is_cooperative_user(target)

    if target.cooperative_id is None:
        raise ForbiddenError("Target user is not linked to a cooperative.")

    cooperative = ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, target.cooperative_id)
    if current_user.role == UserRole.INSTITUTION_ADMIN and cooperative.institution_id is None:
        raise ForbiddenError("Institution admin cannot manage users for independent cooperatives.")

    target.status = UserStatus.ACTIVE
    db.commit()
    db.refresh(target)
    return target


def disable_cooperative_user(db: Session, current_user: User, user_id) -> User:
    target = require_by_id(db, User, user_id, "User")
    _ensure_target_is_cooperative_user(target)

    if target.cooperative_id is None:
        raise ForbiddenError("Target user is not linked to a cooperative.")

    cooperative = ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, target.cooperative_id)
    if current_user.role == UserRole.INSTITUTION_ADMIN and cooperative.institution_id is None:
        raise ForbiddenError("Institution admin cannot manage users for independent cooperatives.")

    target.status = UserStatus.DISABLED
    db.commit()
    db.refresh(target)
    return target
