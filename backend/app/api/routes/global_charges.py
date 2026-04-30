from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_cooperative_deleter, get_current_cooperative_user, get_current_cooperative_writer
from app.db.session import get_db
from app.schemas.global_charge import FarmerChargesResponse, GlobalChargeCreate, GlobalChargeRead, GlobalChargeUpdate
from app.services import global_charges as charge_service


router = APIRouter(tags=["Global Charges"])


@router.get("/charges", response_model=List[GlobalChargeRead], summary="List global charges in current cooperative.")
def list_charges(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = charge_service.list_charges(db, current_user)
    return [GlobalChargeRead.model_validate(row) for row in rows]


@router.post("/charges", response_model=GlobalChargeRead, summary="Create a global charge and mirror it to treasury.")
def create_charge(payload: GlobalChargeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_writer)):
    row = charge_service.create_charge(db, current_user, payload)
    return GlobalChargeRead.model_validate(row)


@router.put("/charges/{charge_id}", response_model=GlobalChargeRead, summary="Update global charge and mirrored treasury record.")
def update_charge(charge_id: UUID, payload: GlobalChargeUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_writer)):
    row = charge_service.update_charge(db, current_user, charge_id, payload)
    return GlobalChargeRead.model_validate(row)


@router.delete("/charges/{charge_id}", status_code=204, summary="Delete global charge (owner/admin only).")
def delete_charge(charge_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_deleter)):
    charge_service.delete_charge(db, current_user, charge_id)
    return None


@router.get("/farmers/{farmer_id}/global-charges", response_model=FarmerChargesResponse, summary="List a farmer's global charges and total.")
def list_farmer_charges(farmer_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    result = charge_service.list_farmer_charges(db, current_user, farmer_id)
    return FarmerChargesResponse.model_validate(result)


@router.post("/global-charges", response_model=GlobalChargeRead, summary="Alias: create a global charge and mirror it to treasury.")
def create_global_charge_alias(payload: GlobalChargeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_writer)):
    row = charge_service.create_charge(db, current_user, payload)
    return GlobalChargeRead.model_validate(row)
