from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.crud.common import require_by_id
from app.crud.user import get_user_by_email
from app.models.cooperative import Cooperative
from app.models.enums import CooperativeStatus, UserRole, UserStatus
from app.models.user import User
from app.schemas.cooperative import CooperativeCreate
from app.schemas.user import ManagerCreate
from app.services.helpers import parse_enum_value
from app.utils.exceptions import ConflictError, ValidationError


def create_cooperative(db: Session, payload: CooperativeCreate) -> Cooperative:
    existing = db.scalar(select(Cooperative).where(func.lower(Cooperative.name) == payload.name.lower()))
    if existing is not None:
        raise ConflictError("A cooperative with this name already exists.")

    cooperative = Cooperative(
        name=payload.name.strip(),
        region=payload.region.strip(),
        address=payload.address.strip(),
        phone=payload.phone.strip(),
        status=parse_enum_value(CooperativeStatus, payload.status, "cooperative status"),
    )
    db.add(cooperative)
    db.commit()
    db.refresh(cooperative)
    return cooperative


def create_manager(db: Session, payload: ManagerCreate) -> User:
    if get_user_by_email(db, payload.email) is not None:
        raise ConflictError("A user with this email already exists.")

    cooperative = require_by_id(db, Cooperative, payload.cooperative_id, "Cooperative")
    if cooperative.status == CooperativeStatus.SUSPENDED:
        raise ValidationError("Cannot attach a manager to a suspended cooperative.")

    manager = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower(),
        password_hash=get_password_hash(payload.password),
        phone=payload.phone.strip() if payload.phone else None,
        role=UserRole.MANAGER,
        status=UserStatus.ACTIVE,
        cooperative_id=cooperative.id,
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    return manager


def disable_user(db: Session, user_id):
    user = require_by_id(db, User, user_id, "User")
    if user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE:
        active_admins = db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE)
        )
        if active_admins <= 1:
            raise ValidationError("The last active admin account cannot be disabled.")
    user.status = UserStatus.DISABLED
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session):
    return db.scalars(select(User).order_by(User.created_at.desc())).all()


def list_cooperatives(db: Session):
    return db.scalars(select(Cooperative).order_by(Cooperative.created_at.desc())).all()
