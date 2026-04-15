from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.stock import StockAdjustment, StockCreate, StockRead, StockUpdate
from app.services import stocks as stock_service


router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.post("", response_model=StockRead, summary="Create a stock row for a product.")
def create_stock(payload: StockCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    stock = stock_service.create_stock(db, current_manager, payload)
    return StockRead.model_validate(stock)


@router.get("", response_model=List[StockRead], summary="List cooperative stock rows.")
def list_stocks(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    stocks = stock_service.list_stocks(db, current_manager)
    return [StockRead.model_validate(stock) for stock in stocks]


@router.patch("/{stock_id}", response_model=StockRead, summary="Update stock threshold or unit.")
def update_stock(stock_id: UUID, payload: StockUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    stock = stock_service.update_stock(db, current_manager, stock_id, payload)
    return StockRead.model_validate(stock)


@router.post("/{stock_id}/increase", response_model=StockRead, summary="Increase stock quantity.")
def increase_stock(stock_id: UUID, payload: StockAdjustment, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    stock = stock_service.adjust_stock(db, current_manager, stock_id, payload.amount, increase=True)
    return StockRead.model_validate(stock)


@router.post("/{stock_id}/decrease", response_model=StockRead, summary="Decrease stock quantity.")
def decrease_stock(stock_id: UUID, payload: StockAdjustment, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    stock = stock_service.adjust_stock(db, current_manager, stock_id, payload.amount, increase=False)
    return StockRead.model_validate(stock)
