from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.treasury import (
    TreasuryStatsRead,
    TreasuryTransactionCreate,
    TreasuryTransactionRead,
    TreasuryTransactionUpdate,
)
from app.services import treasury as treasury_service


router = APIRouter(prefix="/treasury", tags=["Treasury"])


@router.get("", response_model=list[TreasuryTransactionRead], summary="List treasury transactions with filters.")
def list_treasury_transactions(
    transaction_type: str | None = Query(default=None, alias="type"),
    source_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return treasury_service.list_treasury_transactions(
        db=db,
        manager=current_manager,
        transaction_type=transaction_type,
        source_type=source_type,
        search=search,
        sort_order=sort,
    )


@router.post("", response_model=TreasuryTransactionRead, summary="Create a manual treasury transaction.")
def create_treasury_transaction(payload: TreasuryTransactionCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return treasury_service.create_treasury_transaction(db, current_manager, payload)


@router.put("/{transaction_id}", response_model=TreasuryTransactionRead, summary="Update a treasury transaction where allowed.")
def update_treasury_transaction(
    transaction_id: UUID,
    payload: TreasuryTransactionUpdate,
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return treasury_service.update_treasury_transaction(db, current_manager, transaction_id, payload)


@router.patch("/{transaction_id}/cancel", response_model=TreasuryTransactionRead, summary="Cancel a treasury transaction.")
def cancel_treasury_transaction(transaction_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return treasury_service.cancel_treasury_transaction(db, current_manager, transaction_id)


@router.get("/stats", response_model=TreasuryStatsRead, summary="Get treasury KPI stats.")
def get_treasury_stats(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return treasury_service.get_treasury_stats(db, current_manager)


@router.post("/{transaction_id}/justificatif", response_model=TreasuryTransactionRead, summary="Upload treasury justificatif.")
def upload_treasury_justificatif(
    transaction_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return treasury_service.upload_treasury_justificatif(db, current_manager, transaction_id, file)
