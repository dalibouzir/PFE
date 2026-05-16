from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import Any, Type

from sqlalchemy.orm import Session

from app.crud.common import require_by_id, require_scoped_by_id
from app.models.cooperative import Cooperative
from app.models.enums import UserRole
from app.models.institution import Institution
from app.models.user import User
from app.utils.exceptions import ForbiddenError, ValidationError

MASS_UNIT_KG = "kg"
MASS_UNIT_TON = "ton"
SUPPORTED_MASS_UNITS = {MASS_UNIT_KG, MASS_UNIT_TON}
COOPERATIVE_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.VIEWER}

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


def is_super_admin(user: User) -> bool:
    return user.role == UserRole.SUPER_ADMIN


def is_institution_admin(user: User) -> bool:
    return user.role == UserRole.INSTITUTION_ADMIN


def ensure_can_read(user: User):
    if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN}:
        return
    if user.role not in COOPERATIVE_ROLES:
        raise ForbiddenError("Read access is not allowed for this role.")


def ensure_can_write(user: User):
    if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN}:
        return
    if user.role not in {UserRole.OWNER, UserRole.MANAGER}:
        raise ForbiddenError("Write access is not allowed for this role.")


def ensure_can_delete(user: User):
    if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN}:
        return
    if user.role != UserRole.OWNER:
        raise ForbiddenError("Delete access is not allowed for this role.")


def resolve_cooperative_scope(user: User, requested_cooperative_id=None):
    if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        if requested_cooperative_id is not None:
            return requested_cooperative_id
        if user.cooperative_id is not None:
            return user.cooperative_id
        raise ForbiddenError("Admin must provide cooperative_id for this operation.")

    ensure_can_read(user)
    if user.cooperative_id is None:
        raise ForbiddenError("User is not linked to a cooperative.")
    if requested_cooperative_id is not None and requested_cooperative_id != user.cooperative_id:
        raise ForbiddenError("Cross-cooperative access is forbidden.")
    return user.cooperative_id


def get_manager_cooperative_id(user: User):
    return resolve_cooperative_scope(user)


def get_user_institution_scope(user: User):
    if user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        return None
    if user.role == UserRole.INSTITUTION_ADMIN:
        if user.institution_id is None:
            raise ForbiddenError("Institution admin is not linked to an institution.")
        return user.institution_id
    return None


def ensure_user_can_access_institution(db: Session, user: User, institution_id):
    institution = require_by_id(db, Institution, institution_id, "Institution")
    if user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        return institution
    if user.role == UserRole.INSTITUTION_ADMIN:
        scope_id = get_user_institution_scope(user)
        if scope_id != institution.id:
            raise ForbiddenError("Cross-institution access is forbidden.")
        return institution
    raise ForbiddenError("Institution access is not allowed for this role.")


def ensure_user_can_access_cooperative_by_institution_or_global(db: Session, user: User, cooperative_id):
    cooperative = require_by_id(db, Cooperative, cooperative_id, "Cooperative")

    if user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        return cooperative

    if user.role == UserRole.INSTITUTION_ADMIN:
        scope_id = get_user_institution_scope(user)
        if cooperative.institution_id != scope_id:
            raise ForbiddenError("Cross-institution cooperative access is forbidden.")
        return cooperative

    ensure_can_read(user)
    if user.cooperative_id != cooperative.id:
        raise ForbiddenError("Cross-cooperative access is forbidden.")
    return cooperative


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
