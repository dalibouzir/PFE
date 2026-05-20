from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.stock_movement import ManualStockMovementCreate, StockMovementDetailRead, StockMovementRead
from app.services import stock_movements as stock_movement_service


router = APIRouter(prefix="/stock-movements", tags=["Stock Movements"])


@router.get("", response_model=list[StockMovementRead], summary="List persisted stock movements.")
def list_stock_movements(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    product_id: Optional[UUID] = Query(default=None),
    grade: Optional[str] = Query(default=None),
    movement_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    batch_reference: Optional[str] = Query(default=None),
    input_reference: Optional[str] = Query(default=None),
    member_id: Optional[UUID] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return stock_movement_service.list_stock_movements(
        db=db,
        manager=current_manager,
        date_from=date_from,
        date_to=date_to,
        product_id=product_id,
        grade=grade,
        movement_type=movement_type,
        source=source,
        batch_reference=batch_reference,
        input_reference=input_reference,
        member_id=member_id,
        search=search,
        sort=sort,
    )


@router.get("/{movement_id}", response_model=StockMovementDetailRead, summary="Get one stock movement detail.")
def get_stock_movement_detail(
    movement_id: UUID,
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return stock_movement_service.get_stock_movement_detail(db, current_manager, movement_id)


@router.post("/manual-adjustment", response_model=StockMovementDetailRead, summary="Create manual stock movement.")
def create_manual_stock_movement(
    payload: ManualStockMovementCreate,
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return stock_movement_service.create_manual_stock_movement(db, current_manager, payload)
