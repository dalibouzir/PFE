from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id
from app.utils.exceptions import ConflictError, NotFoundError


def create_product(db: Session, manager: User, payload) -> Product:
    cooperative_id = get_manager_cooperative_id(manager)
    duplicate = db.scalar(
        select(Product).where(
            Product.cooperative_id == cooperative_id,
            func.lower(Product.name) == payload.name.lower(),
        )
    )
    if duplicate is not None:
        raise ConflictError("A product with this name already exists in this cooperative.")
    product = Product(
        cooperative_id=cooperative_id,
        name=payload.name.strip(),
        category=payload.category.strip(),
        unit=payload.unit.strip(),
        quality_grade=payload.quality_grade.strip() if payload.quality_grade else None,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def list_products(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Product).where(Product.cooperative_id == cooperative_id).order_by(Product.created_at.desc())
    ).all()


def require_product(db: Session, manager: User, product_id):
    cooperative_id = get_manager_cooperative_id(manager)
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")
    return product


def update_product(db: Session, manager: User, product_id, payload) -> Product:
    product = require_product(db, manager, product_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        duplicate = db.scalar(
            select(Product).where(
                Product.cooperative_id == product.cooperative_id,
                func.lower(Product.name) == data["name"].lower(),
                Product.id != product.id,
            )
        )
        if duplicate is not None:
            raise ConflictError("A product with this name already exists in this cooperative.")
        product.name = data["name"].strip()
    if "category" in data:
        product.category = data["category"].strip()
    if "unit" in data:
        product.unit = data["unit"].strip()
    if "quality_grade" in data:
        product.quality_grade = data["quality_grade"].strip() if data["quality_grade"] else None
    db.commit()
    db.refresh(product)
    return product
