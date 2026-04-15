from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.member import ContactMemberRequest, ContactMemberResponse, MemberCreate, MemberRead, MemberUpdate
from app.services import members as member_service


router = APIRouter(prefix="/members", tags=["Members"])


@router.post("", response_model=MemberRead, summary="Register a new cooperative member.")
def create_member(payload: MemberCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    member = member_service.create_member(db, current_manager, payload)
    return MemberRead.model_validate(member)


@router.get("", response_model=List[MemberRead], summary="List members in the current cooperative.")
def list_members(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    members = member_service.list_members(db, current_manager)
    return [MemberRead.model_validate(member) for member in members]


@router.get("/{member_id}", response_model=MemberRead, summary="Get a member inside the current cooperative.")
def get_member(member_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    member = member_service.require_member(db, current_manager, member_id)
    return MemberRead.model_validate(member)


@router.patch("/{member_id}", response_model=MemberRead, summary="Update a cooperative member.")
def update_member(member_id: UUID, payload: MemberUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    member = member_service.update_member(db, current_manager, member_id, payload)
    return MemberRead.model_validate(member)


@router.post("/{member_id}/contact", response_model=ContactMemberResponse, summary="Log a placeholder member contact action.")
def contact_member(member_id: UUID, payload: ContactMemberRequest, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return member_service.contact_member(db, current_manager, member_id, payload)
