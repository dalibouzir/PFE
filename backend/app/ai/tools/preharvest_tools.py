from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import canonical_product_name, enum_value, source, tool_response, warnings_for_empty
from app.models.enums import PreHarvestStepStatus
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.user import User


class PreharvestTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def get_parcels_summary(self, product: str | None = None) -> dict[str, Any]:
        rows = self.db.execute(
            select(Parcel.main_culture, func.count(Parcel.id), func.coalesce(func.sum(Parcel.surface_ha), 0.0))
            .where(Parcel.cooperative_id == self.current_user.cooperative_id)
            .group_by(Parcel.main_culture)
            .order_by(Parcel.main_culture.asc())
        ).all()
        data = []
        for culture, count, surface in rows:
            if product and canonical_product_name(culture) != canonical_product_name(product):
                continue
            data.append({"product": str(culture), "parcel_count": int(count or 0), "surface_ha": float(surface or 0.0)})
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="parcels", label="Parcelles enregistrées", record_count=len(data), related_product=product)],
            warnings=warnings_for_empty(data),
        )

    def get_parcel_detail(self, parcel_id: str) -> dict[str, Any]:
        parcel = self._get_parcel(parcel_id)
        data = _parcel_payload(parcel) if parcel else None
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="parcels", label="Détail de la parcelle", record_count=1 if parcel else 0)],
            warnings=warnings_for_empty(data),
        )

    def get_parcels_missing_data(self) -> dict[str, Any]:
        rows = self.db.scalars(select(Parcel).where(Parcel.cooperative_id == self.current_user.cooperative_id)).all()
        data = []
        for parcel in rows:
            missing = []
            if not parcel.variety:
                missing.append("variété")
            if parcel.tree_count is None:
                missing.append("nombre d’arbres")
            if not parcel.surface_ha or parcel.surface_ha <= 0:
                missing.append("surface")
            if missing:
                data.append({**_parcel_payload(parcel), "missing_fields": missing})
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="parcels", label="Parcelles avec données manquantes", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def get_parcels_by_crop(self, product: str | None = None) -> dict[str, Any]:
        stmt = select(Parcel).where(Parcel.cooperative_id == self.current_user.cooperative_id).order_by(Parcel.name.asc())
        rows = self.db.scalars(stmt).all()
        data = [
            _parcel_payload(parcel)
            for parcel in rows
            if not product or canonical_product_name(parcel.main_culture) == canonical_product_name(product)
        ]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="parcels", label="Parcelles par culture", record_count=len(data), related_product=product)],
            warnings=warnings_for_empty(data),
        )

    def get_parcel_preharvest_status(self, parcel_id: str | None = None, product: str | None = None) -> dict[str, Any]:
        rows = self._preharvest_rows(parcel_id=parcel_id, product=product)
        grouped: dict[str, dict[str, Any]] = {}
        for parcel, step in rows:
            item = grouped.setdefault(str(parcel.id), {"parcel_id": str(parcel.id), "parcel_name": parcel.name, "product": parcel.main_culture, "completed": 0, "pending": 0})
            if step and step.status == PreHarvestStepStatus.COMPLETED:
                item["completed"] += 1
            elif step:
                item["pending"] += 1
        data = list(grouped.values())
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="parcels,pre_harvest_steps", label="Statut pré-récolte des parcelles", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def get_preharvest_steps(self, parcel_id: str | None = None, product: str | None = None) -> dict[str, Any]:
        rows = self._preharvest_rows(parcel_id=parcel_id, product=product)
        data = [_step_payload(parcel, step) for parcel, step in rows if step is not None]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="pre_harvest_steps", label="Étapes pré-récolte", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def get_incomplete_preharvest_steps(self, parcel_id: str | None = None, product: str | None = None) -> dict[str, Any]:
        rows = [(parcel, step) for parcel, step in self._preharvest_rows(parcel_id=parcel_id, product=product) if step and step.status != PreHarvestStepStatus.COMPLETED]
        data = [_step_payload(parcel, step) for parcel, step in rows]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="pre_harvest_steps", label="Étapes pré-récolte incomplètes", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def get_preharvest_alerts(self, product: str | None = None) -> dict[str, Any]:
        return self.get_incomplete_preharvest_steps(product=product)

    def get_preharvest_readiness(self, parcel_id: str | None = None, product: str | None = None) -> dict[str, Any]:
        statuses = self.get_parcel_preharvest_status(parcel_id=parcel_id, product=product)
        data = []
        for item in statuses["data"]:
            total = int(item["completed"]) + int(item["pending"])
            readiness = 100.0 if total == 0 else (float(item["completed"]) / total) * 100.0
            data.append({**item, "readiness_pct": readiness})
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="parcels,pre_harvest_steps", label="Préparation pré-récolte", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def _get_parcel(self, parcel_id: str) -> Parcel | None:
        try:
            return self.db.scalar(select(Parcel).where(Parcel.cooperative_id == self.current_user.cooperative_id, Parcel.id == UUID(str(parcel_id))))
        except ValueError:
            return None

    def _preharvest_rows(self, *, parcel_id: str | None = None, product: str | None = None) -> list[tuple[Parcel, PreHarvestStep | None]]:
        stmt = (
            select(Parcel, PreHarvestStep)
            .join(PreHarvestStep, PreHarvestStep.parcel_id == Parcel.id, isouter=True)
            .where(Parcel.cooperative_id == self.current_user.cooperative_id)
            .order_by(Parcel.name.asc(), PreHarvestStep.step_order.asc())
        )
        if parcel_id:
            try:
                stmt = stmt.where(Parcel.id == UUID(str(parcel_id)))
            except ValueError:
                return []
        rows = self.db.execute(stmt).all()
        return [
            (parcel, step)
            for parcel, step in rows
            if not product or canonical_product_name(parcel.main_culture) == canonical_product_name(product)
        ]


def _parcel_payload(parcel: Parcel | None) -> dict[str, Any] | None:
    if parcel is None:
        return None
    return {
        "parcel_id": str(parcel.id),
        "name": parcel.name,
        "product": parcel.main_culture,
        "surface_ha": float(parcel.surface_ha or 0.0),
        "variety": parcel.variety,
        "tree_count": parcel.tree_count,
        "member_id": str(parcel.member_id),
    }


def _step_payload(parcel: Parcel, step: PreHarvestStep) -> dict[str, Any]:
    return {
        "parcel_id": str(parcel.id),
        "parcel_name": parcel.name,
        "product": parcel.main_culture,
        "step_id": str(step.id),
        "step_key": step.step_key,
        "label": step.label,
        "category": step.category,
        "status": enum_value(step.status),
        "realization_date": str(step.realization_date) if step.realization_date else None,
        "operation_cost_fcfa": float(step.operation_cost_fcfa or 0.0),
    }
