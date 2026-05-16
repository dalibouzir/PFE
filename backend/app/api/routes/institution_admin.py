from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_institution_admin
from app.db.session import get_db
from app.schemas.cooperative import CooperativeCreate, CooperativeRead, CooperativeUpdate
from app.schemas.institution import InstitutionRead, InstitutionUpdate
from app.schemas.member import MemberRead
from app.schemas.oversight import CooperativeOversightResponse
from app.schemas.user import CooperativeUserCreate, CooperativeUserRead
from app.services import cooperative_users as cooperative_users_service
from app.services import hierarchy_admin as hierarchy_service
from app.services import insights_members as insights_members_service
from app.services import oversight as oversight_service


router = APIRouter(prefix="/institution-admin", tags=["Institution Admin"])


@router.get("/institution", response_model=InstitutionRead, summary="Get own institution profile.")
def get_own_institution(db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    row = hierarchy_service.get_own_institution(db, current_user)
    return InstitutionRead.model_validate(row)


@router.patch("/institution", response_model=InstitutionRead, summary="Update own institution profile.")
def update_own_institution(payload: InstitutionUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    row = hierarchy_service.update_own_institution(db, current_user, payload)
    return InstitutionRead.model_validate(row)


@router.get("/cooperatives", response_model=List[CooperativeRead], summary="List cooperatives under own institution.")
def list_own_cooperatives(db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    rows = hierarchy_service.list_cooperatives_for_institution_admin(db, current_user)
    return [CooperativeRead.model_validate(item) for item in rows]


@router.get("/cooperatives/{cooperative_id}", response_model=CooperativeRead, summary="Get cooperative under own institution.")
def get_own_cooperative(cooperative_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    row = hierarchy_service.get_cooperative_for_institution_admin(db, current_user, cooperative_id)
    return CooperativeRead.model_validate(row)


@router.post("/cooperatives", response_model=CooperativeRead, summary="Create cooperative under own institution.")
def create_cooperative(payload: CooperativeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    row = hierarchy_service.create_cooperative_for_institution_admin(db, current_user, payload)
    return CooperativeRead.model_validate(row)


@router.patch("/cooperatives/{cooperative_id}", response_model=CooperativeRead, summary="Update cooperative under own institution.")
def update_cooperative(
    cooperative_id: UUID,
    payload: CooperativeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_institution_admin),
):
    row = hierarchy_service.update_cooperative_for_institution_admin(db, current_user, cooperative_id, payload)
    return CooperativeRead.model_validate(row)


@router.get("/cooperatives/{cooperative_id}/users", response_model=List[CooperativeUserRead], summary="List cooperative users under own institution.")
def list_cooperative_users(cooperative_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    rows = cooperative_users_service.list_cooperative_users(db, current_user, cooperative_id)
    return [CooperativeUserRead.model_validate(item) for item in rows]


@router.post("/cooperatives/{cooperative_id}/users", response_model=CooperativeUserRead, summary="Create cooperative user under own institution.")
def create_cooperative_user(
    cooperative_id: UUID,
    payload: CooperativeUserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_institution_admin),
):
    row = cooperative_users_service.create_cooperative_user(db, current_user, cooperative_id, payload)
    return CooperativeUserRead.model_validate(row)


@router.patch("/users/{user_id}/enable", response_model=CooperativeUserRead, summary="Enable cooperative user under own institution.")
def enable_cooperative_user(user_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    row = cooperative_users_service.enable_cooperative_user(db, current_user, user_id)
    return CooperativeUserRead.model_validate(row)


@router.patch("/users/{user_id}/disable", response_model=CooperativeUserRead, summary="Disable cooperative user under own institution.")
def disable_cooperative_user(user_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    row = cooperative_users_service.disable_cooperative_user(db, current_user, user_id)
    return CooperativeUserRead.model_validate(row)


@router.get("/oversight/cooperatives", response_model=CooperativeOversightResponse, summary="Read-only oversight KPIs for cooperatives in own institution.")
def get_institution_cooperative_oversight(db: Session = Depends(get_db), current_user=Depends(get_current_institution_admin)):
    cooperatives = hierarchy_service.list_cooperatives_for_institution_admin(db, current_user)
    return oversight_service.build_cooperative_oversight(db, cooperatives)


@router.get(
    "/insights/cooperatives/{cooperative_id}/members",
    response_model=List[MemberRead],
    summary="Read-only members list for selected cooperative insights within own institution.",
)
def list_insights_cooperative_members(
    cooperative_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_institution_admin),
):
    rows = insights_members_service.list_members_for_cooperative_insights(db, current_user, cooperative_id)
    return [MemberRead.model_validate(item) for item in rows]
