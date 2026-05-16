from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.common import require_by_id
from app.models.cooperative import Cooperative
from app.models.enums import CooperativeStatus
from app.models.institution import Institution
from app.models.user import User
from app.schemas.cooperative import CooperativeCreate, CooperativeUpdate
from app.schemas.institution import InstitutionCreate, InstitutionUpdate
from app.services.helpers import (
    ensure_user_can_access_cooperative_by_institution_or_global,
    ensure_user_can_access_institution,
    get_user_institution_scope,
    parse_enum_value,
)
from app.utils.exceptions import ConflictError, ForbiddenError, ValidationError


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def list_institutions(db: Session):
    return db.scalars(select(Institution).order_by(Institution.created_at.desc())).all()


def get_institution(db: Session, institution_id):
    return require_by_id(db, Institution, institution_id, "Institution")


def create_institution(db: Session, payload: InstitutionCreate) -> Institution:
    existing = db.scalar(select(Institution).where(func.lower(Institution.name) == payload.name.lower()))
    if existing is not None:
        raise ConflictError("An institution with this name already exists.")

    row = Institution(
        name=payload.name.strip(),
        description=_normalize_optional(payload.description),
        region=_normalize_optional(payload.region),
        address=_normalize_optional(payload.address),
        phone=_normalize_optional(payload.phone),
        email=_normalize_optional(payload.email.lower() if payload.email else None),
        status=payload.status.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_institution(db: Session, institution_id, payload: InstitutionUpdate) -> Institution:
    row = get_institution(db, institution_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        normalized_name = data["name"].strip()
        duplicate = db.scalar(
            select(Institution).where(
                Institution.id != row.id,
                func.lower(Institution.name) == normalized_name.lower(),
            )
        )
        if duplicate is not None:
            raise ConflictError("An institution with this name already exists.")
        row.name = normalized_name
    if "description" in data:
        row.description = _normalize_optional(data["description"])
    if "region" in data:
        row.region = _normalize_optional(data["region"])
    if "address" in data:
        row.address = _normalize_optional(data["address"])
    if "phone" in data:
        row.phone = _normalize_optional(data["phone"])
    if "email" in data:
        row.email = _normalize_optional(data["email"].lower() if data["email"] else None)
    if "status" in data and data["status"] is not None:
        row.status = data["status"].strip()

    db.commit()
    db.refresh(row)
    return row


def deactivate_institution(db: Session, institution_id) -> Institution:
    row = get_institution(db, institution_id)
    row.status = "inactive"
    db.commit()
    db.refresh(row)
    return row


def list_all_cooperatives(db: Session):
    return db.scalars(select(Cooperative).order_by(Cooperative.created_at.desc())).all()


def get_cooperative(db: Session, cooperative_id):
    return require_by_id(db, Cooperative, cooperative_id, "Cooperative")


def _validate_cooperative_name_uniqueness(db: Session, name: str, exclude_id=None):
    stmt = select(Cooperative).where(func.lower(Cooperative.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Cooperative.id != exclude_id)
    existing = db.scalar(stmt)
    if existing is not None:
        raise ConflictError("A cooperative with this name already exists.")


def create_cooperative_global(db: Session, payload: CooperativeCreate) -> Cooperative:
    _validate_cooperative_name_uniqueness(db, payload.name.strip())

    institution_id = payload.institution_id
    if institution_id is not None:
        require_by_id(db, Institution, institution_id, "Institution")

    row = Cooperative(
        name=payload.name.strip(),
        region=payload.region.strip(),
        address=payload.address.strip(),
        phone=payload.phone.strip(),
        status=parse_enum_value(CooperativeStatus, payload.status, "cooperative status"),
        institution_id=institution_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_cooperative_global(db: Session, cooperative_id, payload: CooperativeUpdate) -> Cooperative:
    row = get_cooperative(db, cooperative_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        normalized_name = data["name"].strip()
        _validate_cooperative_name_uniqueness(db, normalized_name, exclude_id=row.id)
        row.name = normalized_name
    if "region" in data and data["region"] is not None:
        row.region = data["region"].strip()
    if "address" in data and data["address"] is not None:
        row.address = data["address"].strip()
    if "phone" in data and data["phone"] is not None:
        row.phone = data["phone"].strip()
    if "status" in data and data["status"] is not None:
        row.status = parse_enum_value(CooperativeStatus, data["status"], "cooperative status")
    if "institution_id" in data:
        new_institution_id = data["institution_id"]
        if new_institution_id is not None:
            require_by_id(db, Institution, new_institution_id, "Institution")
        row.institution_id = new_institution_id

    db.commit()
    db.refresh(row)
    return row


def assign_cooperative_to_institution(db: Session, cooperative_id, institution_id) -> Cooperative:
    row = get_cooperative(db, cooperative_id)
    institution = get_institution(db, institution_id)
    row.institution_id = institution.id
    db.commit()
    db.refresh(row)
    return row


def make_cooperative_independent(db: Session, cooperative_id) -> Cooperative:
    row = get_cooperative(db, cooperative_id)
    row.institution_id = None
    db.commit()
    db.refresh(row)
    return row


def deactivate_cooperative(db: Session, cooperative_id) -> Cooperative:
    row = get_cooperative(db, cooperative_id)
    row.status = CooperativeStatus.SUSPENDED
    db.commit()
    db.refresh(row)
    return row


def hierarchy_overview(db: Session):
    institutions = list_institutions(db)
    cooperatives = list_all_cooperatives(db)

    coop_by_institution: dict = {}
    independent = []
    for coop in cooperatives:
        if coop.institution_id is None:
            independent.append(coop)
            continue
        coop_by_institution.setdefault(coop.institution_id, []).append(coop)

    rows = []
    for institution in institutions:
        rows.append((institution, coop_by_institution.get(institution.id, [])))
    return rows, independent


def get_own_institution(db: Session, current_user: User) -> Institution:
    scope_id = get_user_institution_scope(current_user)
    if scope_id is None:
        raise ForbiddenError("No institution scope found for this user.")
    return ensure_user_can_access_institution(db, current_user, scope_id)


def update_own_institution(db: Session, current_user: User, payload: InstitutionUpdate) -> Institution:
    institution = get_own_institution(db, current_user)
    return update_institution(db, institution.id, payload)


def list_cooperatives_for_institution_admin(db: Session, current_user: User):
    scope_id = get_user_institution_scope(current_user)
    if scope_id is None:
        raise ForbiddenError("No institution scope found for this user.")
    return db.scalars(
        select(Cooperative)
        .where(Cooperative.institution_id == scope_id)
        .order_by(Cooperative.created_at.desc())
    ).all()


def get_cooperative_for_institution_admin(db: Session, current_user: User, cooperative_id):
    return ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, cooperative_id)


def create_cooperative_for_institution_admin(db: Session, current_user: User, payload: CooperativeCreate):
    scope_id = get_user_institution_scope(current_user)
    if scope_id is None:
        raise ForbiddenError("No institution scope found for this user.")
    if payload.institution_id is not None and payload.institution_id != scope_id:
        raise ForbiddenError("Cannot create cooperative for another institution.")
    forced_payload = CooperativeCreate(
        name=payload.name,
        region=payload.region,
        address=payload.address,
        phone=payload.phone,
        status=payload.status,
        institution_id=scope_id,
    )
    return create_cooperative_global(db, forced_payload)


def update_cooperative_for_institution_admin(
    db: Session,
    current_user: User,
    cooperative_id,
    payload: CooperativeUpdate,
):
    cooperative = ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, cooperative_id)
    if cooperative.institution_id is None:
        raise ForbiddenError("Institution admin cannot manage independent cooperatives.")

    data = payload.model_dump(exclude_unset=True)
    if "institution_id" in data:
        scope_id = get_user_institution_scope(current_user)
        if data["institution_id"] != scope_id:
            raise ForbiddenError("Cannot assign cooperative to another institution.")

    return update_cooperative_global(db, cooperative_id, payload)
