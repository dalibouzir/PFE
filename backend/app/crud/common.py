from typing import Any, Type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.utils.exceptions import NotFoundError


def get_by_id(db: Session, model: Type[Any], object_id: Any):
    return db.get(model, object_id)


def require_by_id(db: Session, model: Type[Any], object_id: Any, label: str):
    instance = get_by_id(db, model, object_id)
    if instance is None:
        raise NotFoundError(f"{label} not found.")
    return instance


def require_scoped_by_id(db: Session, model: Type[Any], object_id: Any, cooperative_id: Any, label: str):
    instance = db.scalar(
        select(model).where(model.id == object_id, model.cooperative_id == cooperative_id)
    )
    if instance is None:
        raise NotFoundError(f"{label} not found in the current cooperative.")
    return instance
