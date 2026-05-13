from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import apply_date_filter, canonical_product_name, enum_value, source, tool_response, warnings_for_empty
from app.ai.tools.material_balance_tools import compute_material_balance
from app.models.batch import Batch
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.user import User


class PostharvestTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def get_batches_summary(self, status: str | None = None, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        rows = self._batch_rows(status=status, product=product, date_range=date_range)
        data = [_batch_payload(*row) for row in rows]
        return tool_response(ok=True, data=data, sources=[source(table="batches,products", label="Lots enregistrés", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_active_batches(self, product: str | None = None) -> dict[str, Any]:
        return self.get_batches_summary(status="in_progress", product=product)

    def get_batch_summary(self, batch_ref: str | None = None) -> dict[str, Any]:
        rows = self._batch_rows(batch_ref=batch_ref)
        data = _batch_payload(*rows[0]) if rows else None
        warnings = warnings_for_empty(data)
        if batch_ref and data is None:
            warnings = [f"Aucun lot correspondant à la référence {batch_ref} n’a été trouvé."]
        return tool_response(ok=True, data=data, sources=[source(table="batches", label="Résumé du lot", record_count=1 if data else 0, related_batch=batch_ref)], warnings=warnings)

    def find_batch_by_reference(self, batch_ref: str) -> dict[str, Any]:
        return self.get_batch_summary(batch_ref=batch_ref)

    def get_recent_batches(self, limit: int = 10) -> dict[str, Any]:
        rows = self._batch_rows(limit=max(1, min(int(limit or 10), 50)))
        data = [_batch_payload(*row) for row in rows]
        return tool_response(ok=True, data=data, sources=[source(table="batches", label="Lots récents", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_process_steps(self, batch_ref: str | None = None, product: str | None = None, stage: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        rows = self._process_step_rows(batch_ref=batch_ref, product=product, stage=stage, date_range=date_range)
        data = [_step_payload(*row) for row in rows]
        return tool_response(ok=True, data=data, sources=[source(table="process_steps", label="Étapes de transformation", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_process_step_losses(self, batch_ref: str | None = None, stage: str | None = None, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        return self.get_process_steps(batch_ref=batch_ref, product=product, stage=stage, date_range=date_range)

    def get_stage_efficiency_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(
                ProcessStep.type,
                func.avg(func.coalesce(((ProcessStep.qty_in - ProcessStep.qty_out) * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)),
                func.avg(func.coalesce((ProcessStep.qty_out * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)),
                func.count(ProcessStep.id),
            )
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.current_user.cooperative_id)
            .group_by(ProcessStep.type)
            .order_by(func.avg(func.coalesce(((ProcessStep.qty_in - ProcessStep.qty_out) * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)).desc())
        )
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        stmt = apply_date_filter(stmt, ProcessStep.date, date_range)
        rows = self.db.execute(stmt).all()
        data = [
            {"stage": str(stage), "avg_loss_pct": float(loss or 0.0), "avg_efficiency_pct": float(eff or 0.0), "record_count": int(count or 0)}
            for stage, loss, eff, count in rows
        ]
        return tool_response(ok=True, data=data, sources=[source(table="process_steps", label="Efficacité moyenne par étape", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_high_loss_stages(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        result = self.get_stage_efficiency_summary(product=product, date_range=date_range)
        data = [item for item in result["data"] if float(item.get("avg_loss_pct", 0.0)) >= 10.0]
        return tool_response(ok=True, data=data, sources=[source(table="process_steps", label="Étapes à fortes pertes", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_high_loss_batches(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        rows = self._batch_rows(product=product, date_range=date_range)
        data = sorted([_batch_payload(*row) for row in rows], key=lambda item: float(item["loss_pct"]), reverse=True)[:10]
        data = [item for item in data if float(item["loss_pct"]) >= 10.0]
        return tool_response(ok=True, data=data, sources=[source(table="batches", label="Lots à fortes pertes", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_material_balance(self, batch_ref: str | None = None, product: str | None = None) -> dict[str, Any]:
        rows = self._batch_rows(batch_ref=batch_ref, product=product)
        data = []
        warnings: list[str] = []
        for row in rows:
            payload = _batch_payload(*row)
            stage_rows = self._process_step_rows(batch_ref=payload["batch_ref"], product=product)
            breakdown = [_step_payload(*step_row) for step_row in stage_rows]
            balance = compute_material_balance(input_quantity=payload["initial_qty"], output_quantity=payload["current_qty"], stage_breakdown=breakdown)
            warnings.extend(balance.get("warnings", []))
            data.append({"batch_ref": payload["batch_ref"], "product": payload["product"], **balance})
        if batch_ref and not data:
            warnings.append(f"Aucun lot correspondant à la référence {batch_ref} n’a été trouvé.")
        warnings.extend(warnings_for_empty(data))
        return tool_response(ok=True, data=data, sources=[source(table="batches,process_steps", label="Bilan matière", record_count=len(data))], warnings=sorted(set(warnings)))

    def get_material_balance_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        rows = self._batch_rows(product=product, date_range=date_range)
        data = [_batch_payload(*row) for row in rows]
        return tool_response(ok=True, data=data, sources=[source(table="batches", label="Résumé du bilan matière", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_batch_stage_breakdown(self, batch_ref: str) -> dict[str, Any]:
        return self.get_process_steps(batch_ref=batch_ref)

    def _batch_rows(self, *, batch_ref: str | None = None, status: str | None = None, product: str | None = None, date_range: list[str] | None = None, limit: int | None = None):
        stmt = (
            select(Batch.id, Batch.code, Product.name, Batch.initial_qty, Batch.current_qty, Batch.unit, Batch.status, Batch.creation_date)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.current_user.cooperative_id)
            .order_by(Batch.creation_date.desc())
        )
        if batch_ref:
            stmt = stmt.where(func.upper(Batch.code) == str(batch_ref).upper())
        if status:
            stmt = stmt.where(func.lower(Batch.status) == str(status).lower())
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        stmt = apply_date_filter(stmt, Batch.creation_date, date_range)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).all()

    def _process_step_rows(self, *, batch_ref: str | None = None, product: str | None = None, stage: str | None = None, date_range: list[str] | None = None):
        stmt = (
            select(ProcessStep.id, Batch.code, Product.name, ProcessStep.type, ProcessStep.qty_in, ProcessStep.qty_out, ProcessStep.date)
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.current_user.cooperative_id)
            .order_by(ProcessStep.date.desc())
        )
        if batch_ref:
            stmt = stmt.where(func.upper(Batch.code) == str(batch_ref).upper())
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        if stage:
            stmt = stmt.where(func.lower(ProcessStep.type) == str(stage).lower())
        stmt = apply_date_filter(stmt, ProcessStep.date, date_range)
        return self.db.execute(stmt).all()


def _batch_payload(batch_id, code, product_name, initial_qty, current_qty, unit, status, creation_date) -> dict[str, Any]:
    initial = float(initial_qty or 0.0)
    current = float(current_qty or 0.0)
    loss_pct = ((initial - current) / initial * 100.0) if initial > 0 else 0.0
    return {
        "batch_id": str(batch_id),
        "batch_ref": str(code),
        "product": str(product_name),
        "initial_qty": initial,
        "current_qty": current,
        "loss_pct": loss_pct,
        "efficiency_pct": (current / initial * 100.0) if initial > 0 else 0.0,
        "unit": str(unit or "kg"),
        "status": enum_value(status),
        "creation_date": str(creation_date),
    }


def _step_payload(step_id, batch_code, product_name, stage, qty_in, qty_out, step_date) -> dict[str, Any]:
    q_in = float(qty_in or 0.0)
    q_out = float(qty_out or 0.0)
    loss_pct = ((q_in - q_out) / q_in * 100.0) if q_in > 0 else 0.0
    return {
        "step_id": str(step_id),
        "batch_ref": str(batch_code),
        "product": str(product_name),
        "stage": str(stage),
        "qty_in": q_in,
        "qty_out": q_out,
        "loss_pct": loss_pct,
        "efficiency_pct": (q_out / q_in * 100.0) if q_in > 0 else 0.0,
        "date": str(step_date),
    }


def _product_aliases(value: str | None) -> list[str]:
    canonical = canonical_product_name(value)
    if canonical == "mango":
        return ["mango", "mangue"]
    if canonical == "peanut":
        return ["peanut", "arachide"]
    if canonical == "millet":
        return ["millet", "mil"]
    return [canonical]
