from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel
from app.schemas.process_step import ProcessStepRead


class BatchCreate(BaseModel):
    product_id: UUID
    member_id: Optional[UUID] = None
    parcel_id: Optional[UUID] = None
    creation_date: date
    initial_qty: float = Field(gt=0)
    unit: str = Field(default="kg", min_length=1, max_length=16)
    process_steps: List[str] = Field(min_length=1)
    surface_ha: Optional[float] = Field(default=None, ge=0)
    expected_yield_kg_per_ha: Optional[float] = Field(default=None, ge=0)
    expected_losses_kg: Optional[float] = Field(default=None, ge=0)
    estimated_qty_override_reason: Optional[str] = Field(default=None, max_length=1000)
    estimated_charge_fcfa: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


class BatchStatusUpdate(BaseModel):
    status: str


class BatchUpdate(BaseModel):
    process_steps: Optional[List[str]] = Field(default=None, min_length=1)
    estimated_charge_fcfa: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)

class PreHarvestStepStatusItem(BaseModel):
    index: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=500)
    status: str
    updated_at: Optional[datetime] = None
    execution_date: Optional[date] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    summary: Optional[str] = Field(default=None, max_length=2000)

class BatchPreHarvestStepStatusesUpdate(BaseModel):
    statuses: List[PreHarvestStepStatusItem]


class BatchRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    product_id: UUID
    member_id: Optional[UUID]
    parcel_id: Optional[UUID]
    code: str
    creation_date: date
    unit: str
    ordered_process_steps: List[str]
    initial_qty: float
    current_qty: float
    surface_ha: Optional[float]
    expected_yield_kg_per_ha: Optional[float]
    expected_losses_kg: Optional[float]
    estimated_qty_kg: Optional[float]
    estimated_qty_override_reason: Optional[str]
    estimated_charge_fcfa: Optional[float]
    charge_approved_at: Optional[datetime]
    charge_approved_by_user_id: Optional[UUID]
    preharvest_activated_at: Optional[datetime]
    preharvest_step_statuses: Optional[List[PreHarvestStepStatusItem]]
    preharvest_completed_at: Optional[datetime]
    confirmed_weight_kg: Optional[float]
    collecte_input_id: Optional[UUID] = None
    collecte_created: bool = False
    stock_in_created: bool = False
    postharvest_started_at: Optional[datetime]
    postharvest_status: Optional[str] = None
    status_note: Optional[str]
    initial_qty_display: float
    current_qty_display: float
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class BatchMetricsSummary(BaseModel):
    batch_id: UUID
    total_input: float
    final_output: float
    total_loss_pct: float
    total_efficiency_pct: float
    completed_steps: int
    latest_step_id: Optional[UUID] = None


class BatchApproveChargeResponse(BaseModel):
    batch: BatchRead


class BatchCompletePreHarvestRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)
    collecte_date: Optional[date] = None


class BatchMaterialBalanceStageRead(BaseModel):
    stage: str
    step_count: int
    qty_in: float
    qty_out: float
    loss_qty: float
    loss_pct: float
    efficiency_pct: float


class BatchMaterialBalanceRead(BaseModel):
    batch_id: UUID
    cooperative_id: UUID
    postharvest_status: str
    initial_confirmed_qty: float
    current_qty: float
    final_output_qty: Optional[float]
    total_loss_qty: float
    total_loss_pct: float
    total_efficiency_pct: float
    steps_completed: int
    steps_required: int
    per_stage: List[BatchMaterialBalanceStageRead]
    process_steps: List["ProcessStepRead"]
