from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_admin
from app.db.session import get_db
from app.schemas.cooperative import CooperativeCreate, CooperativeRead, CooperativeUpdate
from app.schemas.hierarchy import HierarchyOverviewRead, InstitutionWithCooperativesRead
from app.schemas.institution import InstitutionCreate, InstitutionRead, InstitutionUpdate
from app.schemas.member import MemberRead
from app.schemas.oversight import CooperativeOversightResponse
from app.schemas.user import CooperativeUserCreate, CooperativeUserRead, InstitutionAdminCreate, InstitutionAdminRead
from app.services import cooperative_users as cooperative_users_service
from app.services import hierarchy_admin as hierarchy_service
from app.services import insights_members as insights_members_service
from app.services import institution_admin_users as institution_admin_users_service
from app.services import oversight as oversight_service


router = APIRouter(prefix="/super-admin", tags=["Super Admin"])


class AssignInstitutionRequest(BaseModel):
    institution_id: UUID


@router.get("/institutions", response_model=List[InstitutionRead], summary="List institutions.")
def list_institutions(db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    rows = hierarchy_service.list_institutions(db)
    return [InstitutionRead.model_validate(item) for item in rows]


@router.get("/institutions/{institution_id}", response_model=InstitutionRead, summary="Get institution by id.")
def get_institution(institution_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.get_institution(db, institution_id)
    return InstitutionRead.model_validate(row)


@router.post("/institutions", response_model=InstitutionRead, summary="Create institution.")
def create_institution(payload: InstitutionCreate, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.create_institution(db, payload)
    return InstitutionRead.model_validate(row)


@router.patch("/institutions/{institution_id}", response_model=InstitutionRead, summary="Update institution.")
def update_institution(institution_id: UUID, payload: InstitutionUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.update_institution(db, institution_id, payload)
    return InstitutionRead.model_validate(row)


@router.patch("/institutions/{institution_id}/deactivate", response_model=InstitutionRead, summary="Deactivate institution.")
def deactivate_institution(institution_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.deactivate_institution(db, institution_id)
    return InstitutionRead.model_validate(row)


@router.get("/cooperatives", response_model=List[CooperativeRead], summary="List all cooperatives.")
def list_cooperatives(db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    rows = hierarchy_service.list_all_cooperatives(db)
    return [CooperativeRead.model_validate(item) for item in rows]


@router.get("/cooperatives/{cooperative_id}", response_model=CooperativeRead, summary="Get cooperative by id.")
def get_cooperative(cooperative_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.get_cooperative(db, cooperative_id)
    return CooperativeRead.model_validate(row)


@router.post("/cooperatives", response_model=CooperativeRead, summary="Create cooperative (institution-linked or independent).")
def create_cooperative(payload: CooperativeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.create_cooperative_global(db, payload)
    return CooperativeRead.model_validate(row)


@router.patch("/cooperatives/{cooperative_id}", response_model=CooperativeRead, summary="Update cooperative.")
def update_cooperative(cooperative_id: UUID, payload: CooperativeUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.update_cooperative_global(db, cooperative_id, payload)
    return CooperativeRead.model_validate(row)


@router.patch("/cooperatives/{cooperative_id}/assign-institution", response_model=CooperativeRead, summary="Assign cooperative to institution.")
def assign_cooperative_to_institution(
    cooperative_id: UUID,
    payload: AssignInstitutionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_platform_admin),
):
    row = hierarchy_service.assign_cooperative_to_institution(db, cooperative_id, payload.institution_id)
    return CooperativeRead.model_validate(row)


@router.patch("/cooperatives/{cooperative_id}/make-independent", response_model=CooperativeRead, summary="Remove institution assignment.")
def make_cooperative_independent(cooperative_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.make_cooperative_independent(db, cooperative_id)
    return CooperativeRead.model_validate(row)


@router.patch("/cooperatives/{cooperative_id}/deactivate", response_model=CooperativeRead, summary="Deactivate cooperative.")
def deactivate_cooperative(cooperative_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = hierarchy_service.deactivate_cooperative(db, cooperative_id)
    return CooperativeRead.model_validate(row)


@router.get("/cooperatives/{cooperative_id}/users", response_model=List[CooperativeUserRead], summary="List cooperative users.")
def list_cooperative_users(cooperative_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    rows = cooperative_users_service.list_cooperative_users(db, current_user, cooperative_id)
    return [CooperativeUserRead.model_validate(item) for item in rows]


@router.post("/cooperatives/{cooperative_id}/users", response_model=CooperativeUserRead, summary="Create cooperative user.")
def create_cooperative_user(
    cooperative_id: UUID,
    payload: CooperativeUserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_platform_admin),
):
    row = cooperative_users_service.create_cooperative_user(db, current_user, cooperative_id, payload)
    return CooperativeUserRead.model_validate(row)


@router.patch("/users/{user_id}/enable", response_model=CooperativeUserRead, summary="Enable cooperative user.")
def enable_cooperative_user(user_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = cooperative_users_service.enable_cooperative_user(db, current_user, user_id)
    return CooperativeUserRead.model_validate(row)


@router.patch("/users/{user_id}/disable", response_model=CooperativeUserRead, summary="Disable cooperative user.")
def disable_cooperative_user(user_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = cooperative_users_service.disable_cooperative_user(db, current_user, user_id)
    return CooperativeUserRead.model_validate(row)


@router.get("/institutions/{institution_id}/admins", response_model=List[InstitutionAdminRead], summary="List institution admins.")
def list_institution_admin_users(institution_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    rows = institution_admin_users_service.list_institution_admins(db, institution_id)
    return [InstitutionAdminRead.model_validate(item) for item in rows]


@router.post("/institutions/{institution_id}/admins", response_model=InstitutionAdminRead, summary="Create institution admin.")
def create_institution_admin_user(
    institution_id: UUID,
    payload: InstitutionAdminCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_platform_admin),
):
    row = institution_admin_users_service.create_institution_admin(db, institution_id, payload)
    return InstitutionAdminRead.model_validate(row)


@router.patch("/institution-admins/{user_id}/enable", response_model=InstitutionAdminRead, summary="Enable institution admin.")
def enable_institution_admin_user(user_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = institution_admin_users_service.enable_institution_admin(db, user_id)
    return InstitutionAdminRead.model_validate(row)


@router.patch("/institution-admins/{user_id}/disable", response_model=InstitutionAdminRead, summary="Disable institution admin.")
def disable_institution_admin_user(user_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    row = institution_admin_users_service.disable_institution_admin(db, user_id)
    return InstitutionAdminRead.model_validate(row)


@router.get("/hierarchy", response_model=HierarchyOverviewRead, summary="Hierarchy overview with institutions and independent cooperatives.")
def get_hierarchy(db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    institution_rows, independent = hierarchy_service.hierarchy_overview(db)
    institutions = [
        InstitutionWithCooperativesRead.model_validate(
            {
                **InstitutionRead.model_validate(institution).model_dump(),
                "cooperatives": [CooperativeRead.model_validate(item).model_dump() for item in cooperatives],
            }
        )
        for institution, cooperatives in institution_rows
    ]
    return HierarchyOverviewRead(
        institutions=institutions,
        independent_cooperatives=[CooperativeRead.model_validate(item) for item in independent],
    )


@router.get("/oversight/cooperatives", response_model=CooperativeOversightResponse, summary="Read-only cooperative oversight KPIs.")
def get_cooperative_oversight(db: Session = Depends(get_db), current_user=Depends(get_current_platform_admin)):
    cooperatives = hierarchy_service.list_all_cooperatives(db)
    return oversight_service.build_cooperative_oversight(db, cooperatives)


@router.get(
    "/insights/cooperatives/{cooperative_id}/members",
    response_model=List[MemberRead],
    summary="Read-only members list for selected cooperative insights.",
)
def list_insights_cooperative_members(
    cooperative_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_platform_admin),
):
    rows = insights_members_service.list_members_for_cooperative_insights(db, current_user, cooperative_id)
    return [MemberRead.model_validate(item) for item in rows]
