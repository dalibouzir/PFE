from enum import Enum
from typing import Any, Type

from sqlalchemy.orm import Session

from app.crud.common import require_by_id, require_scoped_by_id
from app.models.enums import UserRole
from app.models.user import User
from app.utils.exceptions import ForbiddenError, ValidationError


def parse_enum_value(enum_class: Type[Enum], raw_value: str, field_name: str):
    try:
        return enum_class(raw_value)
    except ValueError:
        allowed = ", ".join(item.value for item in enum_class)
        raise ValidationError(f"Invalid {field_name}. Expected one of: {allowed}.")


def get_manager_cooperative_id(user: User):
    if user.role != UserRole.MANAGER:
        raise ForbiddenError("This action is only available to managers.")
    if user.cooperative_id is None:
        raise ForbiddenError("Manager account is not linked to a cooperative.")
    return user.cooperative_id


def require_entity_for_user(db: Session, model: Type[Any], object_id: Any, user: User, label: str):
    if user.role == UserRole.ADMIN:
        return require_by_id(db, model, object_id, label)
    return require_scoped_by_id(db, model, object_id, get_manager_cooperative_id(user), label)


def round_metric(value: float) -> float:
    return round(float(value), 2)
