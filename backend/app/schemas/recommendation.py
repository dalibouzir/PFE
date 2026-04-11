from pydantic import BaseModel


class RecommendRequest(BaseModel):
    loss_pct: float
    duration_hours: float
    product_type: str
    step_name: str


class RecommendResponse(BaseModel):
    recommendations: list[str]
