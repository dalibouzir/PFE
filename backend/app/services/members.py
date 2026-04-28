import logging
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.product import Product
from app.models.user import User
from app.schemas.member import ContactMemberRequest
from app.services.helpers import get_manager_cooperative_id, parse_enum_value
from app.models.enums import MemberStatus
from app.utils.exceptions import ConflictError


logger = logging.getLogger(__name__)


AUTO_PRODUCT_CATEGORY = "Culture membre"
AUTO_PRODUCT_UNIT = "kg"


def _split_product_labels(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    tokens = [token.strip() for token in re.split(r"[;,/|]+", raw_value) if token.strip()]
    unique: list[str] = []
    seen = set()
    for token in tokens:
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(token)
    return unique


def _merge_member_product_labels(
    main_product: str | None,
    secondary_products: str | None,
    legacy_specialty: str | None = None,
) -> list[str]:
    primary = _split_product_labels(main_product)
    secondary = _split_product_labels(secondary_products)
    legacy = _split_product_labels(legacy_specialty)

    merged: list[str] = []
    seen = set()
    for item in [*primary, *secondary, *legacy]:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        merged.append(item)
    return merged


def _sync_products_for_member(db: Session, cooperative_id, product_labels: list[str]) -> bool:
    created_any = False
    for name in product_labels:
        existing = db.scalar(
            select(Product).where(
                Product.cooperative_id == cooperative_id,
                func.lower(Product.name) == name.lower(),
            )
        )
        if existing is not None:
            continue
        db.add(
            Product(
                cooperative_id=cooperative_id,
                name=name,
                category=AUTO_PRODUCT_CATEGORY,
                unit=AUTO_PRODUCT_UNIT,
                quality_grade=None,
            )
        )
        created_any = True
    return created_any


def ensure_products_from_member_profile(
    db: Session,
    cooperative_id,
    main_product: str | None,
    secondary_products: str | None,
    specialty: str | None = None,
) -> bool:
    product_labels = _merge_member_product_labels(main_product, secondary_products, specialty)
    return _sync_products_for_member(db, cooperative_id, product_labels)


def _normalized_ascii(value: str | None) -> str:
    raw = (value or "").strip()
    return (
        unicodedata.normalize("NFKD", raw)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _first_alnum_char(value: str | None, fallback: str = "X") -> str:
    ascii_value = _normalized_ascii(value)
    for char in ascii_value:
        if char.isalnum():
            return char.upper()
    return fallback


def _member_codes_query(cooperative_id, exclude_member_id=None):
    if exclude_member_id is None:
        return select(Member.code).where(Member.cooperative_id == cooperative_id)
    return select(Member.code).where(Member.cooperative_id == cooperative_id, Member.id != exclude_member_id)


def _build_member_code(
    db: Session,
    cooperative_id,
    full_name: str | None,
    main_product: str | None,
    exclude_member_id=None,
) -> str:
    name_initial = _first_alnum_char(full_name, fallback="X")
    product_initial = _first_alnum_char(main_product, fallback="X")
    prefix = f"{name_initial}{product_initial}"
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")

    max_number = -1
    rows = db.scalars(_member_codes_query(cooperative_id, exclude_member_id)).all()
    for code in rows:
        if not code:
            continue
        matched = pattern.match(code.strip().upper())
        if not matched:
            continue
        max_number = max(max_number, int(matched.group(1)))

    return f"{prefix}-{max_number + 1}"


def _ensure_unique_member_code(
    db: Session,
    cooperative_id,
    desired_code: str | None,
    full_name: str | None,
    main_product: str | None,
    exclude_member_id=None,
) -> str:
    candidate = (desired_code or "").strip()
    if not candidate:
        return _build_member_code(
            db=db,
            cooperative_id=cooperative_id,
            full_name=full_name,
            main_product=main_product,
            exclude_member_id=exclude_member_id,
        )

    duplicate = db.scalar(
        select(Member).where(
            Member.cooperative_id == cooperative_id,
            Member.code == candidate,
            *( [Member.id != exclude_member_id] if exclude_member_id else [] ),
        )
    )
    if duplicate is not None:
        raise ConflictError("A member with this code already exists in this cooperative.")
    return candidate


def create_member(db: Session, manager: User, payload) -> Member:
    cooperative_id = get_manager_cooperative_id(manager)
    product_labels = _merge_member_product_labels(
        payload.main_product,
        payload.secondary_products,
        payload.specialty,
    )
    main_product = product_labels[0] if product_labels else None
    secondary_products = "; ".join(product_labels[1:]) if len(product_labels) > 1 else None

    member = Member(
        cooperative_id=cooperative_id,
        code=_ensure_unique_member_code(
            db=db,
            cooperative_id=cooperative_id,
            desired_code=payload.code,
            full_name=payload.full_name,
            main_product=main_product,
        ),
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        village=payload.village.strip() if payload.village else None,
        main_product=main_product,
        secondary_products=secondary_products,
        parcel_count=int(payload.parcel_count or 0),
        area_hectares=float(payload.area_hectares or 0),
        join_date=payload.join_date,
        specialty=main_product,
        status=parse_enum_value(MemberStatus, payload.status, "member status"),
    )
    db.add(member)
    _sync_products_for_member(db, cooperative_id, product_labels)
    db.commit()
    db.refresh(member)
    return member


def list_members(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Member).where(Member.cooperative_id == cooperative_id).order_by(Member.created_at.desc())
    ).all()


def get_member(db: Session, manager: User, member_id):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalar(
        select(Member).where(Member.id == member_id, Member.cooperative_id == cooperative_id)
    )


def require_member(db: Session, manager: User, member_id):
    member = get_member(db, manager, member_id)
    if member is None:
        from app.utils.exceptions import NotFoundError

        raise NotFoundError("Member not found in the current cooperative.")
    return member


def update_member(db: Session, manager: User, member_id, payload) -> Member:
    member = require_member(db, manager, member_id)
    data = payload.model_dump(exclude_unset=True)
    if "code" in data:
        name_for_code = data["full_name"] if "full_name" in data else member.full_name
        product_labels_for_code = _merge_member_product_labels(
            data.get("main_product", member.main_product),
            data.get("secondary_products", member.secondary_products),
            data.get("specialty", member.specialty),
        )
        main_product_for_code = product_labels_for_code[0] if product_labels_for_code else member.main_product
        member.code = _ensure_unique_member_code(
            db,
            member.cooperative_id,
            data["code"],
            full_name=name_for_code,
            main_product=main_product_for_code,
            exclude_member_id=member.id,
        )
    if "full_name" in data:
        member.full_name = data["full_name"].strip()
    if "phone" in data:
        member.phone = data["phone"].strip()
    if "village" in data:
        member.village = data["village"].strip() if data["village"] else None
    if "parcel_count" in data:
        member.parcel_count = int(data["parcel_count"] or 0)
    if "area_hectares" in data:
        member.area_hectares = float(data["area_hectares"] or 0)
    if "join_date" in data:
        member.join_date = data["join_date"]

    if any(key in data for key in ("main_product", "secondary_products", "specialty")):
        use_legacy = "main_product" not in data and "secondary_products" not in data
        product_labels = _merge_member_product_labels(
            data.get("main_product", member.main_product),
            data.get("secondary_products", member.secondary_products),
            data.get("specialty") if use_legacy else None,
        )
        member.main_product = product_labels[0] if product_labels else None
        member.secondary_products = "; ".join(product_labels[1:]) if len(product_labels) > 1 else None
        member.specialty = member.main_product
    else:
        product_labels = _merge_member_product_labels(
            member.main_product,
            member.secondary_products,
            member.specialty,
        )

    if "status" in data:
        member.status = parse_enum_value(MemberStatus, data["status"], "member status")
    _sync_products_for_member(db, member.cooperative_id, product_labels)
    db.commit()
    db.refresh(member)
    return member


def contact_member(db: Session, manager: User, member_id, payload: ContactMemberRequest):
    member = require_member(db, manager, member_id)
    logger.info(
        "Contact member placeholder: manager_id=%s member_id=%s channel=%s message=%s",
        manager.id,
        member.id,
        payload.channel,
        payload.message,
    )
    return {
        "success": True,
        "member_id": member.id,
        "channel": payload.channel,
        "message": "Contact action logged successfully.",
    }
