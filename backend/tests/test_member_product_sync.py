from sqlalchemy import func, select

from app.models.enums import MemberStatus
from app.models.member import Member
from app.models.product import Product
from app.models.user import User
from app.schemas.member import MemberCreate, MemberUpdate
from app.services import members as member_service
from app.services import products as product_service


def _manager(db_session):
    manager = db_session.scalar(select(User).where(User.email == "manager@test.local"))
    assert manager is not None
    return manager


def _product_count(db_session, cooperative_id, name: str) -> int:
    return int(
        db_session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.cooperative_id == cooperative_id, func.lower(Product.name) == name.lower())
        )
        or 0
    )


def test_create_member_auto_creates_product_from_specialty(db_session):
    manager = _manager(db_session)
    assert _product_count(db_session, manager.cooperative_id, "mangue") == 0
    assert _product_count(db_session, manager.cooperative_id, "papaye") == 0

    member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            code="MBR-900",
            full_name="Fatou Mangue",
            phone="+221770099001",
            specialty="Mangue; Papaye",
            status="active",
        ),
    )
    assert _product_count(db_session, manager.cooperative_id, "mangue") == 1
    assert _product_count(db_session, manager.cooperative_id, "papaye") == 1

    member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            code="MBR-901",
            full_name="Awa Mangue",
            phone="+221770099002",
            specialty="mangue; PAPAYE",
            status="active",
        ),
    )
    assert _product_count(db_session, manager.cooperative_id, "mangue") == 1
    assert _product_count(db_session, manager.cooperative_id, "papaye") == 1


def test_create_member_auto_creates_products_from_main_and_secondary(db_session):
    manager = _manager(db_session)
    assert _product_count(db_session, manager.cooperative_id, "ananas") == 0
    assert _product_count(db_session, manager.cooperative_id, "orange") == 0

    member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            code="MBR-902",
            full_name="Seynabou Fruits",
            phone="+221770099003",
            main_product="Ananas",
            secondary_products="Orange",
            status="active",
        ),
    )

    assert _product_count(db_session, manager.cooperative_id, "ananas") == 1
    assert _product_count(db_session, manager.cooperative_id, "orange") == 1


def test_update_member_auto_creates_product_when_specialty_changes(db_session):
    manager = _manager(db_session)
    member = member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            code="MBR-910",
            full_name="Moussa Bissap",
            phone="+221770099010",
            specialty=None,
            status="active",
        ),
    )
    assert _product_count(db_session, manager.cooperative_id, "bissap") == 0

    member_service.update_member(
        db_session,
        manager,
        member.id,
        MemberUpdate(specialty="Bissap"),
    )

    assert _product_count(db_session, manager.cooperative_id, "bissap") == 1


def test_auto_member_code_uses_name_and_main_product_with_increment(db_session):
    manager = _manager(db_session)

    first = member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            full_name="Awa Diop",
            phone="+221770099020",
            main_product="Mangue",
            status="active",
        ),
    )
    second = member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            full_name="Amadou Fall",
            phone="+221770099021",
            main_product="Mangue",
            status="active",
        ),
    )
    fallback = member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            full_name="Ndeye",
            phone="+221770099022",
            status="active",
        ),
    )

    assert first.code == "AM-0"
    assert second.code == "AM-1"
    assert fallback.code.startswith("NX-")


def test_list_products_backfills_from_existing_member_profiles(db_session):
    manager = _manager(db_session)

    orphan_member = Member(
        cooperative_id=manager.cooperative_id,
        code="MBR-999",
        full_name="Binta Legacy",
        phone="+221770099099",
        main_product="Mangue",
        secondary_products="Papaye",
        specialty="Mangue",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(orphan_member)
    db_session.commit()

    assert _product_count(db_session, manager.cooperative_id, "mangue") == 0
    assert _product_count(db_session, manager.cooperative_id, "papaye") == 0

    rows = product_service.list_products(db_session, manager)
    names = {row.name.lower() for row in rows}

    assert "mangue" in names
    assert "papaye" in names
