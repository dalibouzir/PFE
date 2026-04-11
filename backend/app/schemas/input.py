from datetime import datetime
from pydantic import BaseModel


class InputCreate(BaseModel):
    member_id: str
    product_type: str
    quantity_kg: float
    quality_grade: str | None = None
    collected_at: datetime


class InputResponse(BaseModel):
    status: str
    data: dict
