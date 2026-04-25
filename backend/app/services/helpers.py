import re
import unicodedata
from enum import Enum
from typing import Any, Type

from sqlalchemy.orm import Session

from app.crud.common import require_by_id, require_scoped_by_id
from app.models.enums import UserRole
from app.models.user import User
from app.utils.exceptions import ForbiddenError, ValidationError

MASS_UNIT_KG = "kg"
MASS_UNIT_TON = "ton"
SUPPORTED_MASS_UNITS = {MASS_UNIT_KG, MASS_UNIT_TON}

PRODUCT_CODE_OVERRIDES = {
    "mango": "MANG",
    "peanut": "PEAN",
    "millet": "MILL",
}


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


def normalize_mass_unit(raw_unit: str | None) -> str:
    unit = (raw_unit or "").strip().lower()
    if unit in {"kg", "kgs", "kilogram", "kilograms"}:
        return MASS_UNIT_KG
    if unit in {"ton", "tons", "tonne", "tonnes", "t"}:
        return MASS_UNIT_TON
    allowed = ", ".join(sorted(SUPPORTED_MASS_UNITS))
    raise ValidationError(f"Invalid unit. Expected one of: {allowed}.")


def to_kg(quantity: float, unit: str) -> float:
    normalized = normalize_mass_unit(unit)
    value = float(quantity)
    if normalized == MASS_UNIT_KG:
        return round_metric(value)
    return round_metric(value * 1000.0)


def from_kg(quantity_kg: float, unit: str) -> float:
    normalized = normalize_mass_unit(unit)
    value = float(quantity_kg)
    if normalized == MASS_UNIT_KG:
        return round_metric(value)
    return round_metric(value / 1000.0)


def normalize_product_code(name: str) -> str:
    normalized_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )
    if normalized_name in PRODUCT_CODE_OVERRIDES:
        return PRODUCT_CODE_OVERRIDES[normalized_name]
    token = re.sub(r"[^a-z0-9]", "", normalized_name).upper()
    if not token:
        token = "PROD"
    return (token[:4]).ljust(4, "X")
