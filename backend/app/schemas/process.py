from datetime import datetime
from pydantic import BaseModel


class ProcessCreate(BaseModel):
    member_id: str
    input_id: str | None = None
    step_name: str
    input_kg: float
    output_kg: float
    duration_hours: float | None = None
    performed_at: datetime


class ProcessResponse(BaseModel):
    status: str
    data: dict
