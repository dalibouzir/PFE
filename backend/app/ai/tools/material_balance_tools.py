from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User


def compute_material_balance(
    *,
    input_quantity: float,
    output_quantity: float,
    stage_breakdown: list[dict] | None = None,
) -> dict:
    warnings: list[str] = []
    qty_in = float(input_quantity or 0.0)
    qty_out = float(output_quantity or 0.0)

    if stage_breakdown is None:
        warnings.append("Le détail par étape est incomplet.")

    if qty_in <= 0:
        warnings.append("La quantité d’entrée doit être supérieure à 0.")
        return {
            "input_quantity": qty_in,
            "output_quantity": qty_out,
            "total_loss_quantity": 0.0,
            "loss_percentage": 0.0,
            "efficiency_percentage": 0.0,
            "stage_level_loss_breakdown": stage_breakdown or [],
            "warnings": warnings,
        }

    if qty_out < 0:
        warnings.append("La quantité de sortie ne peut pas être négative.")
        qty_out = 0.0

    if qty_out > qty_in:
        warnings.append("La quantité de sortie est supérieure à la quantité d’entrée.")

    total_loss = qty_in - qty_out
    loss_pct = (total_loss / qty_in) * 100.0
    efficiency_pct = (qty_out / qty_in) * 100.0

    return {
        "input_quantity": qty_in,
        "output_quantity": qty_out,
        "total_loss_quantity": total_loss,
        "loss_percentage": loss_pct,
        "efficiency_percentage": efficiency_pct,
        "stage_level_loss_breakdown": stage_breakdown or [],
        "warnings": warnings,
    }


class MaterialBalanceTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def get_material_balance(self, batch_ref: str | None = None, product: str | None = None) -> dict[str, Any]:
        return self._postharvest_tools().get_material_balance(batch_ref=batch_ref, product=product)

    def get_material_balance_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        return self._postharvest_tools().get_material_balance_summary(product=product, date_range=date_range)

    def get_batch_stage_breakdown(self, batch_ref: str) -> dict[str, Any]:
        return self._postharvest_tools().get_batch_stage_breakdown(batch_ref=batch_ref)

    def _postharvest_tools(self):
        from app.ai.tools.postharvest_tools import PostharvestTools

        return PostharvestTools(self.db, self.current_user)
