from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.commercial import (
    CatalogProductCreate,
    CatalogProductRead,
    CatalogProductUpdate,
    CommercialInvoiceRead,
    CommercialInvoiceStats,
    CommercialOrderIntake,
    CommercialOrderRead,
    CommercialOrderStats,
    CommercialOrderStatusUpdate,
)
from app.services import commercial as commercial_service


router = APIRouter(prefix="/commercial", tags=["Commercialisation"])


@router.get("/catalog", response_model=List[CatalogProductRead], summary="List commercial catalog products.")
def list_catalog(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.list_catalog_products(db, current_manager)


@router.post("/catalog", response_model=CatalogProductRead, summary="Create a commercial catalog product and allocate stock.")
def create_catalog(payload: CatalogProductCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.create_catalog_product(db, current_manager, payload)


@router.patch("/catalog/{catalog_product_id}", response_model=CatalogProductRead, summary="Update a commercial catalog product.")
def update_catalog(catalog_product_id: UUID, payload: CatalogProductUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.update_catalog_product(db, current_manager, catalog_product_id, payload)


@router.patch("/catalog/{catalog_product_id}/status", response_model=CatalogProductRead, summary="Set catalog product status.")
def update_catalog_status(catalog_product_id: UUID, status: str = Query(..., min_length=1), db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.set_catalog_status(db, current_manager, catalog_product_id, status)


@router.get("/orders", response_model=List[CommercialOrderRead], summary="List commercial orders.")
def list_orders(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return commercial_service.list_orders(db, current_manager, status=status, search=search)


@router.get("/orders/stats", response_model=CommercialOrderStats, summary="Get commercial order stats.")
def orders_stats(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.order_stats(db, current_manager)


@router.post("/orders", response_model=CommercialOrderRead, summary="Intake a new order from consumer channel.")
def intake_order(payload: CommercialOrderIntake, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.intake_order(db, current_manager, payload)


@router.patch("/orders/{order_id}/status", response_model=CommercialOrderRead, summary="Update order lifecycle status.")
def update_order_status(order_id: UUID, payload: CommercialOrderStatusUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.update_order_status(db, current_manager, order_id, payload)


@router.get("/invoices", response_model=List[CommercialInvoiceRead], summary="List invoices.")
def list_invoices(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_manager=Depends(get_current_manager),
):
    return commercial_service.list_invoices(db, current_manager, status=status, search=search)


@router.get("/invoices/stats", response_model=CommercialInvoiceStats, summary="Get invoice stats.")
def invoices_stats(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.invoice_stats(db, current_manager)


@router.get("/invoices/{invoice_id}", response_model=CommercialInvoiceRead, summary="Get one invoice.")
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return commercial_service.get_invoice(db, current_manager, invoice_id)
