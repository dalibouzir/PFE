from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.ai.tools.material_balance_tools import compute_material_balance
from app.ai.tools.preharvest_tools import PreharvestTools
from app.models.batch import Batch
from app.models.commercial_invoice import CommercialInvoice
from app.models.commercial_order import CommercialOrder
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User


class SQLTools:
    """Controlled SQL tool execution for grounded response generation."""

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.cooperative_id = current_user.cooperative_id
        self.preharvest = PreharvestTools(db, current_user)

    def module_available(self, table_name: str) -> bool:
        try:
            return bool(inspect(self.db.get_bind()).has_table(table_name))
        except Exception:
            return False

    def get_current_stock(self, product: str | None = None) -> dict[str, Any]:
        stmt = (
            select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold, Stock.unit)
            .join(Product, Product.id == Stock.product_id)
            .where(Stock.cooperative_id == self.cooperative_id)
            .order_by(Product.name.asc())
        )
        rows = self.db.execute(stmt).all()
        items = []
        for name, total, reserved, threshold, unit in rows:
            if product and _canonical_product_name(name) != _canonical_product_name(product):
                continue
            available = float(total or 0.0) - float(reserved or 0.0)
            items.append(
                {
                    "product": str(name),
                    "total_stock_kg": float(total or 0.0),
                    "reserved_in_lots_kg": float(reserved or 0.0),
                    "available_stock_kg": available,
                    "threshold_kg": float(threshold or 0.0),
                    "unit": str(unit or "kg"),
                    "is_low": available < float(threshold or 0.0),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "stocks",
                    "label": "Stocks courants par produit",
                    "record_count": len(items),
                    "related_product": product,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_collections_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt: Select = (
            select(Product.name, func.coalesce(func.sum(Input.quantity), 0.0), func.count(Input.id))
            .join(Product, Product.id == Input.product_id)
            .where(Input.cooperative_id == self.cooperative_id)
            .group_by(Product.name)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
        )
        stmt = _apply_input_date_range(stmt, date_range)
        rows = self.db.execute(stmt).all()
        items = []
        for prod_name, qty, count in rows:
            if product and _canonical_product_name(prod_name) != _canonical_product_name(product):
                continue
            items.append(
                {
                    "product": str(prod_name),
                    "total_quantity_kg": float(qty or 0.0),
                    "records": int(count or 0),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "inputs",
                    "label": "Résumé des collectes",
                    "record_count": len(items),
                    "related_product": product,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_members_list(self, member_name: str | None = None) -> dict[str, Any]:
        stmt = (
            select(Member.id, Member.code, Member.full_name, Member.phone, Member.village, Member.main_product, Member.status)
            .where(Member.cooperative_id == self.cooperative_id)
            .order_by(Member.full_name.asc())
        )
        rows = self.db.execute(stmt).all()
        items = []
        needle = str(member_name or "").strip().lower()
        for member_id, code, full_name, phone, village, main_product, status in rows:
            if needle and needle not in str(full_name or "").lower():
                continue
            items.append(
                {
                    "member_id": str(member_id),
                    "member_code": str(code),
                    "member_name": str(full_name),
                    "phone": str(phone or ""),
                    "village": str(village or ""),
                    "main_product": str(main_product or ""),
                    "status": str(status.value if hasattr(status, "value") else status),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "members",
                    "label": "Liste des membres",
                    "record_count": len(items),
                    "related_member_name": member_name,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_parcels_list(self, product: str | None = None) -> dict[str, Any]:
        stmt = (
            select(Parcel.id, Parcel.name, Parcel.surface_ha, Parcel.main_culture, Parcel.variety, Member.full_name)
            .join(Member, Member.id == Parcel.member_id)
            .where(Parcel.cooperative_id == self.cooperative_id)
            .order_by(Parcel.name.asc())
        )
        rows = self.db.execute(stmt).all()
        items = []
        for parcel_id, name, surface_ha, main_culture, variety, member_name in rows:
            if product and _canonical_product_name(main_culture) != _canonical_product_name(product):
                continue
            items.append(
                {
                    "parcel_id": str(parcel_id),
                    "parcel_name": str(name),
                    "surface_ha": float(surface_ha or 0.0),
                    "main_culture": str(main_culture or ""),
                    "variety": str(variety or ""),
                    "member_name": str(member_name or ""),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "parcels,members",
                    "label": "Liste des parcelles",
                    "record_count": len(items),
                    "related_product": product,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_cooperative_overview(self) -> dict[str, Any]:
        member_count = int(
            self.db.scalar(select(func.count(Member.id)).where(Member.cooperative_id == self.cooperative_id)) or 0
        )
        parcel_count = int(
            self.db.scalar(select(func.count(Parcel.id)).where(Parcel.cooperative_id == self.cooperative_id)) or 0
        )
        batch_count = int(
            self.db.scalar(select(func.count(Batch.id)).where(Batch.cooperative_id == self.cooperative_id)) or 0
        )
        batch_rows = self.get_batch_summary(batch_ref=None).get("items", [])
        open_batch_count = sum(
            1 for row in batch_rows if str(row.get("status") or "").strip().lower() not in {"completed", "cancelled"}
        )
        stock_rows = self.get_current_stock().get("items", [])
        stock_total_kg = float(sum(float(row.get("available_stock_kg", 0.0) or 0.0) for row in stock_rows))
        process_rows = self.get_process_step_losses().get("items", [])
        avg_loss_pct = 0.0
        if process_rows:
            avg_loss_pct = float(sum(float(row.get("loss_pct", 0.0) or 0.0) for row in process_rows) / len(process_rows))

        items = [
            {
                "member_count": member_count,
                "parcel_count": parcel_count,
                "batch_count": batch_count,
                "open_batch_count": open_batch_count,
                "stock_total_kg": stock_total_kg,
                "process_step_count": len(process_rows),
                "avg_loss_pct": avg_loss_pct,
            }
        ]
        warnings: list[str] = []
        if member_count == 0 and parcel_count == 0 and batch_count == 0 and stock_total_kg <= 0:
            warnings.append("NO_SQL_DATA")
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "members,parcels,stocks,batches,process_steps",
                    "label": "Synthèse coopérative",
                    "record_count": 1,
                }
            ],
            "warnings": warnings,
        }

    def get_high_risk_lots(self, *, loss_threshold: float = 12.0, efficiency_threshold: float = 85.0) -> dict[str, Any]:
        batches = self.get_batch_summary(batch_ref=None).get("items", [])
        items = []
        for row in batches:
            loss = float(row.get("loss_pct", 0.0) or 0.0)
            efficiency = float(row.get("efficiency_pct", 0.0) or 0.0)
            if loss >= float(loss_threshold) or efficiency <= float(efficiency_threshold):
                items.append(
                    {
                        **row,
                        "risk_reason": (
                            f"loss_pct={loss:.1f}% >= {loss_threshold:.1f}%"
                            if loss >= float(loss_threshold)
                            else f"efficiency_pct={efficiency:.1f}% <= {efficiency_threshold:.1f}%"
                        ),
                    }
                )
        items.sort(key=lambda row: float(row.get("loss_pct", 0.0) or 0.0), reverse=True)
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "batches",
                    "label": "Lots à risque élevé (mesures SQL)",
                    "record_count": len(items),
                    "loss_threshold_pct": float(loss_threshold),
                    "efficiency_threshold_pct": float(efficiency_threshold),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_batch_summary(self, batch_ref: str | None = None) -> dict[str, Any]:
        stmt = (
            select(Batch.id, Batch.code, Product.name, Batch.initial_qty, Batch.current_qty, Batch.unit, Batch.status)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .order_by(Batch.creation_date.desc())
        )
        rows = self.db.execute(stmt).all()
        items = []
        for batch_id, code, product_name, initial_qty, current_qty, unit, status in rows:
            if batch_ref and str(code).upper() != str(batch_ref).upper():
                continue
            initial = float(initial_qty or 0.0)
            current = float(current_qty or 0.0)
            loss_pct = ((initial - current) / initial * 100.0) if initial > 0 else 0.0
            items.append(
                {
                    "batch_id": str(batch_id),
                    "batch_ref": str(code),
                    "product": str(product_name),
                    "initial_qty": initial,
                    "current_qty": current,
                    "loss_pct": loss_pct,
                    "efficiency_pct": (current / initial * 100.0) if initial > 0 else 0.0,
                    "status": str(status.value if hasattr(status, "value") else status),
                    "unit": str(unit or "kg"),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "batches",
                    "label": "Résumé des lots",
                    "record_count": len(items),
                    "related_batch": batch_ref,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_process_step_losses(
        self,
        batch_ref: str | None = None,
        stage: str | None = None,
        product: str | None = None,
        date_range: list[str] | None = None,
    ) -> dict[str, Any]:
        stmt = (
            select(
                ProcessStep.id,
                Batch.code,
                Product.name,
                ProcessStep.type,
                ProcessStep.qty_in,
                ProcessStep.qty_out,
                ProcessStep.date,
            )
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .order_by(ProcessStep.date.desc())
        )
        stmt = _apply_step_date_range(stmt, date_range)
        rows = self.db.execute(stmt).all()

        items = []
        for step_id, code, product_name, step_type, qty_in, qty_out, step_date in rows:
            if batch_ref and str(code).upper() != str(batch_ref).upper():
                continue
            if stage and _canonical_stage_name(step_type) != _canonical_stage_name(stage):
                continue
            if product and _canonical_product_name(product_name) != _canonical_product_name(product):
                continue
            q_in = float(qty_in or 0.0)
            q_out = float(qty_out or 0.0)
            loss_pct = ((q_in - q_out) / q_in * 100.0) if q_in > 0 else 0.0
            items.append(
                {
                    "step_id": str(step_id),
                    "batch_ref": str(code),
                    "product": str(product_name),
                    "stage": str(step_type),
                    "qty_in": q_in,
                    "qty_out": q_out,
                    "loss_pct": loss_pct,
                    "efficiency_pct": (q_out / q_in * 100.0) if q_in > 0 else 0.0,
                    "date": str(step_date),
                }
            )

        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "process_steps",
                    "label": "Pertes par étape",
                    "record_count": len(items),
                    "related_batch": batch_ref,
                    "related_stage": stage,
                    "related_product": product,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_material_balance(self, batch_ref: str | None = None, product: str | None = None) -> dict[str, Any]:
        batch_summary = self.get_batch_summary(batch_ref=batch_ref)
        rows = batch_summary.get("items", [])
        if product:
            rows = [row for row in rows if _canonical_product_name(row.get("product", "")) == _canonical_product_name(product)]

        balances = []
        warnings: list[str] = []
        for row in rows:
            step_rows = self.get_process_step_losses(batch_ref=row.get("batch_ref"), stage=None, product=product).get("items", [])
            breakdown = [
                {
                    "stage": step.get("stage"),
                    "qty_in": step.get("qty_in"),
                    "qty_out": step.get("qty_out"),
                    "loss_pct": step.get("loss_pct"),
                }
                for step in step_rows
            ]
            balance = compute_material_balance(
                input_quantity=float(row.get("initial_qty", 0.0) or 0.0),
                output_quantity=float(row.get("current_qty", 0.0) or 0.0),
                stage_breakdown=breakdown,
            )
            warnings.extend(balance.get("warnings", []))
            balances.append({"batch_ref": row.get("batch_ref"), "product": row.get("product"), **balance})

        if not balances:
            warnings.append("NO_SQL_DATA")

        return {
            "items": balances,
            "sources": [
                {
                    "type": "sql",
                    "table": "batches,process_steps",
                    "label": "Bilan matière",
                    "record_count": len(balances),
                    "related_batch": batch_ref,
                    "related_product": product,
                }
            ],
            "warnings": sorted(set(warnings)),
        }

    def get_low_stock_alerts(self) -> dict[str, Any]:
        stock = self.get_current_stock()
        items = [item for item in stock.get("items", []) if item.get("is_low")]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "stocks",
                    "label": "Alertes de stock bas",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_top_farmers(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Member.id, Member.full_name, Member.code, func.coalesce(func.sum(Input.quantity), 0.0).label("qty"))
            .join(Input, Input.member_id == Member.id)
            .join(Product, Product.id == Input.product_id)
            .where(Member.cooperative_id == self.cooperative_id)
            .group_by(Member.id, Member.full_name, Member.code)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
            .limit(10)
        )
        if product:
            aliases = _product_aliases(product)
            stmt = stmt.where(func.lower(Product.name).in_(aliases))
        stmt = _apply_input_date_range(stmt, date_range)
        rows = self.db.execute(stmt).all()
        items = [
            {
                "member_id": str(member_id),
                "member_name": str(full_name),
                "member_code": str(code),
                "total_quantity_kg": float(qty or 0.0),
            }
            for member_id, full_name, code, qty in rows
        ]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "inputs,members",
                    "label": "Top producteurs",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_top_members_by_cost(self, date_range: list[str] | None = None) -> dict[str, Any]:
        if not self.module_available("global_charges"):
            return {
                "items": [],
                "sources": [],
                "warnings": ["MODULE_NOT_AVAILABLE"],
            }
        stmt: Select = (
            select(
                Member.id,
                Member.full_name,
                Member.code,
                func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).label("cost"),
            )
            .join(GlobalCharge, GlobalCharge.member_id == Member.id)
            .where(Member.cooperative_id == self.cooperative_id)
            .group_by(Member.id, Member.full_name, Member.code)
            .order_by(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).desc())
            .limit(10)
        )
        stmt = _apply_charge_date_range(stmt, date_range)
        rows = self.db.execute(stmt).all()
        items = [
            {
                "member_id": str(member_id),
                "member_name": str(full_name),
                "member_code": str(code),
                "total_cost_fcfa": float(cost or 0.0),
            }
            for member_id, full_name, code, cost in rows
        ]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "global_charges,members",
                    "label": "Classement membres par coût",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_invoices_summary(self) -> dict[str, Any]:
        if not self.module_available("commercial_invoices"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        rows = self.db.execute(
            select(
                CommercialInvoice.invoice_number,
                CommercialInvoice.status,
                CommercialInvoice.total_amount_fcfa,
                CommercialInvoice.issue_date,
            )
            .where(CommercialInvoice.cooperative_id == self.cooperative_id)
            .order_by(CommercialInvoice.issue_date.desc())
            .limit(30)
        ).all()
        items = [
            {
                "invoice_number": str(number),
                "status": str(status.value if hasattr(status, "value") else status),
                "total_amount_fcfa": float(total or 0.0),
                "issue_date": str(issue_date),
            }
            for number, status, total, issue_date in rows
        ]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "commercial_invoices",
                    "label": "Factures commerciales",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_commercial_orders_summary(self) -> dict[str, Any]:
        if not self.module_available("commercial_orders"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        rows = self.db.execute(
            select(
                CommercialOrder.order_number,
                CommercialOrder.status,
                CommercialOrder.total_amount_fcfa,
                CommercialOrder.received_at,
            )
            .where(CommercialOrder.cooperative_id == self.cooperative_id)
            .order_by(CommercialOrder.received_at.desc())
            .limit(30)
        ).all()
        items = [
            {
                "order_number": str(number),
                "status": str(status.value if hasattr(status, "value") else status),
                "total_amount_fcfa": float(total or 0.0),
                "received_at": str(received_at),
            }
            for number, status, total, received_at in rows
        ]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "commercial_orders",
                    "label": "Commandes commerciales",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_commercial_totals(self) -> dict[str, Any]:
        if not self.module_available("commercial_orders"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        total_orders = self.db.scalar(
            select(func.count(CommercialOrder.id)).where(CommercialOrder.cooperative_id == self.cooperative_id)
        )
        total_value = self.db.scalar(
            select(func.coalesce(func.sum(CommercialOrder.total_amount_fcfa), 0.0)).where(
                CommercialOrder.cooperative_id == self.cooperative_id
            )
        )
        delivered_value = self.db.scalar(
            select(func.coalesce(func.sum(CommercialOrder.total_amount_fcfa), 0.0)).where(
                CommercialOrder.cooperative_id == self.cooperative_id,
                func.lower(CommercialOrder.status) == "delivered",
            )
        )
        items = [
            {
                "order_count": int(total_orders or 0),
                "total_amount_fcfa": float(total_value or 0.0),
                "delivered_amount_fcfa": float(delivered_value or 0.0),
            }
        ]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "commercial_orders",
                    "label": "Totaux commerciaux",
                    "record_count": 1,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if int(total_orders or 0) == 0 else [],
        }

    def get_finance_expenses(self) -> dict[str, Any]:
        warnings: list[str] = []
        if not self.module_available("treasury_transactions") and not self.module_available("global_charges"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}

        treasury_total = 0.0
        treasury_count = 0
        if self.module_available("treasury_transactions"):
            treasury_count = int(
                self.db.scalar(
                    select(func.count(TreasuryTransaction.id)).where(
                        TreasuryTransaction.cooperative_id == self.cooperative_id
                    )
                )
                or 0
            )
            treasury_total = float(
                self.db.scalar(
                    select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
                        TreasuryTransaction.cooperative_id == self.cooperative_id
                    )
                )
                or 0.0
            )
        charge_total = 0.0
        charge_count = 0
        if self.module_available("global_charges"):
            charge_count = int(
                self.db.scalar(
                    select(func.count(GlobalCharge.id)).where(GlobalCharge.cooperative_id == self.cooperative_id)
                )
                or 0
            )
            charge_total = float(
                self.db.scalar(
                    select(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0)).where(
                        GlobalCharge.cooperative_id == self.cooperative_id
                    )
                )
                or 0.0
            )

        items = [
            {
                "treasury_count": treasury_count,
                "treasury_total_fcfa": treasury_total,
                "global_charge_count": charge_count,
                "global_charge_total_fcfa": charge_total,
            }
        ]
        if treasury_count == 0 and charge_count == 0:
            warnings.append("NO_SQL_DATA")
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "treasury_transactions,global_charges",
                    "label": "Charges et dépenses",
                    "record_count": treasury_count + charge_count,
                }
            ],
            "warnings": warnings,
        }

    def get_stage_efficiency_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt: Select = (
            select(
                ProcessStep.type,
                func.avg(func.coalesce((ProcessStep.qty_out * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)).label("eff"),
                func.avg(func.coalesce(((ProcessStep.qty_in - ProcessStep.qty_out) * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)).label("loss"),
                func.count(ProcessStep.id),
            )
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .group_by(ProcessStep.type)
            .order_by(func.avg(func.coalesce(((ProcessStep.qty_in - ProcessStep.qty_out) * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)).desc())
        )
        if product:
            aliases = _product_aliases(product)
            stmt = stmt.where(func.lower(Product.name).in_(aliases))
        stmt = _apply_step_date_range(stmt, date_range)
        rows = self.db.execute(stmt).all()
        items = [
            {
                "stage": str(stage),
                "avg_efficiency_pct": float(eff or 0.0),
                "avg_loss_pct": float(loss or 0.0),
                "record_count": int(count or 0),
            }
            for stage, eff, loss, count in rows
        ]
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "process_steps",
                    "label": "Efficacité moyenne par étape",
                    "record_count": len(items),
                    "related_product": product,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }


def _parse_date_values(date_range: list[str] | None) -> tuple[date | None, date | None]:
    if not date_range:
        return None, None
    parsed: list[date] = []
    for raw in date_range[:2]:
        try:
            parsed.append(date.fromisoformat(str(raw)))
        except ValueError:
            continue
    if not parsed:
        return None, None
    if len(parsed) == 1:
        return parsed[0], parsed[0]
    return min(parsed), max(parsed)


def _apply_input_date_range(stmt: Select, date_range: list[str] | None) -> Select:
    start, end = _parse_date_values(date_range)
    if start and end:
        return stmt.where(and_(Input.date >= start, Input.date <= end))
    return stmt


def _apply_step_date_range(stmt: Select, date_range: list[str] | None) -> Select:
    start, end = _parse_date_values(date_range)
    if start and end:
        return stmt.where(and_(ProcessStep.date >= start, ProcessStep.date <= end))
    return stmt


def _apply_charge_date_range(stmt: Select, date_range: list[str] | None) -> Select:
    start, end = _parse_date_values(date_range)
    if start and end:
        return stmt.where(and_(GlobalCharge.date >= start, GlobalCharge.date <= end))
    return stmt


def _canonical_product_name(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "mangue": "mango",
        "mango": "mango",
        "arachide": "peanut",
        "peanut": "peanut",
        "mil": "millet",
        "millet": "millet",
        "bissap": "bissap",
    }
    return aliases.get(normalized, normalized)


def _product_aliases(value: str | None) -> list[str]:
    canonical = _canonical_product_name(value)
    reverse = {
        "mango": ["mango", "mangue"],
        "peanut": ["peanut", "arachide"],
        "millet": ["millet", "mil"],
        "bissap": ["bissap"],
    }
    return reverse.get(canonical, [canonical])


def _canonical_stage_name(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "séchage": "drying",
        "sechage": "drying",
        "drying": "drying",
        "tri": "sorting",
        "sorting": "sorting",
        "nettoyage": "cleaning",
        "cleaning": "cleaning",
        "emballage": "packaging",
        "conditionnement": "packaging",
        "packaging": "packaging",
        "storage": "storage",
        "stockage": "storage",
    }
    return aliases.get(normalized, normalized)
