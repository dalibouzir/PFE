from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.crud.common import require_by_id
from app.crud.user import get_user_by_email
from app.models.enums import UserRole, UserStatus
from app.models.institution import Institution
from app.models.user import User
from app.schemas.user import InstitutionAdminCreate
from app.utils.exceptions import ConflictError, ForbiddenError, ValidationError


_BLOCKED_INSTITUTION_STATUSES = {"inactive", "suspended"}


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _ensure_target_role_is_institution_admin(user: User):
    if user.role != UserRole.INSTITUTION_ADMIN:
        raise ForbiddenError("Only institution admin users can be managed by this endpoint.")


def list_institution_admins(db: Session, institution_id):
    require_by_id(db, Institution, institution_id, "Institution")
    return db.scalars(
        select(User)
        .where(
            User.role == UserRole.INSTITUTION_ADMIN,
            User.institution_id == institution_id,
            User.cooperative_id.is_(None),
        )
        .order_by(User.created_at.desc())
    ).all()


def create_institution_admin(db: Session, institution_id, payload: InstitutionAdminCreate) -> User:
    institution = require_by_id(db, Institution, institution_id, "Institution")
    if institution.status.strip().lower() in _BLOCKED_INSTITUTION_STATUSES:
        raise ValidationError("Cannot create institution admin for inactive or suspended institution.")

    email = _normalize_email(payload.email)
    if get_user_by_email(db, email) is not None:
        raise ConflictError("A user with this email already exists.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=get_password_hash(payload.password),
        phone=_normalize_optional(payload.phone),
        role=UserRole.INSTITUTION_ADMIN,
        status=UserStatus.ACTIVE,
        cooperative_id=None,
        institution_id=institution.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def enable_institution_admin(db: Session, user_id) -> User:
    user = require_by_id(db, User, user_id, "User")
    _ensure_target_role_is_institution_admin(user)
    user.status = UserStatus.ACTIVE
    db.commit()
    db.refresh(user)
    return user


def disable_institution_admin(db: Session, user_id) -> User:
    user = require_by_id(db, User, user_id, "User")
    _ensure_target_role_is_institution_admin(user)
    user.status = UserStatus.DISABLED
    db.commit()
    db.refresh(user)
    return user
