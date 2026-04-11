from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    product_type: str
    step_name: str
    input_kg: float
    output_kg: float
    duration_hours: float


class AnalyzeResponse(BaseModel):
    loss_kg: float
    loss_pct: float
    efficiency_score: float
    anomaly_flag: bool
