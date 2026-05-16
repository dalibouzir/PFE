from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class CooperativeOversightRow(BaseModel):
    cooperative_id: UUID
    cooperative_name: str
    institution_id: Optional[UUID]
    institution_name: Optional[str]
    status: str
    users_count: int
    managers_count: int
    viewers_count: int
    members_count: int
    parcels_count: int
    lots_count: int
    active_lots_count: int
    ready_post_recolte_lots_count: int
    available_stock_kg: float
    total_stock_kg: float
    loss_rate: float
    efficiency_rate: float
    low_stock_alerts_count: int
    recommendations_count: int


class OversightSummary(BaseModel):
    total_cooperatives: int
    total_users: int
    total_managers: int
    total_members: int
    total_parcels: int
    total_lots: int
    active_lots: int
    ready_post_recolte_lots: int
    total_available_stock_kg: float
    total_stock_kg: float
    avg_loss_rate: float
    avg_efficiency_rate: float
    low_stock_alerts_count: int
    recommendations_count: int


class CooperativeOversightResponse(BaseModel):
    summary: OversightSummary
    cooperatives: List[CooperativeOversightRow]
