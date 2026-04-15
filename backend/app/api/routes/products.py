from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services import products as product_service


router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductRead, summary="Create a product for the current cooperative.")
def create_product(payload: ProductCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    product = product_service.create_product(db, current_manager, payload)
    return ProductRead.model_validate(product)


@router.get("", response_model=List[ProductRead], summary="List products in the current cooperative.")
def list_products(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    products = product_service.list_products(db, current_manager)
    return [ProductRead.model_validate(product) for product in products]


@router.patch("/{product_id}", response_model=ProductRead, summary="Update a product.")
def update_product(product_id: UUID, payload: ProductUpdate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    product = product_service.update_product(db, current_manager, product_id, payload)
    return ProductRead.model_validate(product)
