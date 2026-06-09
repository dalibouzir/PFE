from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, String, and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.ai.tools.material_balance_tools import compute_material_balance
from app.ai.tools.lot_resolution import resolve_lot_reference
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
from app.models.farmer_advance import FarmerAdvance
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.models.treasury_transaction import TreasuryTransaction
from app.models.uploaded_file import UploadedFile
from app.models.user import User

POST_HARVEST_STAGES = {"cleaning", "drying", "sorting", "packaging"}


class SQLTools:
    """Controlled SQL tool execution for grounded response generation."""
    _global_table_availability_cache: dict[tuple[str, str], bool] = {}
    _global_module_capabilities_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.cooperative_id = current_user.cooperative_id
        self.preharvest = PreharvestTools(db, current_user)
        self._table_availability_cache: dict[str, bool] = {}

    def module_available(self, table_name: str) -> bool:
        bind = self.db.get_bind()
        cache_key = (str(getattr(bind, "url", "")), table_name)
        global_cached = SQLTools._global_table_availability_cache.get(cache_key)
        if global_cached is not None:
            return global_cached
        cached = self._table_availability_cache.get(table_name)
        if cached is not None:
            return cached
        try:
            available = bool(inspect(bind).has_table(table_name))
            self._table_availability_cache[table_name] = available
            SQLTools._global_table_availability_cache[cache_key] = available
            return available
        except Exception:
            self._table_availability_cache[table_name] = False
            SQLTools._global_table_availability_cache[cache_key] = False
            return False

    def get_module_capabilities(self) -> dict[str, dict[str, Any]]:
        bind_key = str(getattr(self.db.get_bind(), "url", ""))
        cached = SQLTools._global_module_capabilities_cache.get(bind_key)
        if cached is not None:
            return cached
        module_tables = {
            "members": ("members",),
            "parcels": ("parcels",),
            "inputs": ("inputs",),
            "stocks": ("stocks", "products"),
            "lots": ("batches",),
            "process_steps": ("process_steps",),
            "material_balance": ("batches", "process_steps"),
            "ml_logs": ("ml_prediction_logs", "ml_recommendation_logs"),
            "rag": ("rag_documents", "rag_chunks"),
            "recommendations": ("recommendations",),
            "commercial": ("commercial_orders",),
            "invoices": ("commercial_invoices",),
            "finance": ("treasury_transactions", "global_charges"),
        }
        capabilities: dict[str, dict[str, Any]] = {}
        for module, tables in module_tables.items():
            available_tables = [table for table in tables if self.module_available(table)]
            capabilities[module] = {
                "tables": list(tables),
                "available_tables": available_tables,
                "available": len(available_tables) > 0,
            }
        SQLTools._global_module_capabilities_cache[bind_key] = capabilities
        return capabilities

    def get_current_stock(self, product: str | None = None) -> dict[str, Any]:
        stmt = (
            select(
                Product.id,
                Product.name,
                Stock.grade,
                Stock.total_stock_kg,
                Stock.reserved_in_lots_kg,
                Stock.processed_output_kg,
                Stock.threshold,
                Stock.unit,
            )
            .join(Product, Product.id == Stock.product_id)
            .where(Stock.cooperative_id == self.cooperative_id)
            .order_by(Product.name.asc(), Stock.grade.asc())
        )
        rows = self.db.execute(stmt).all()
        normalized_filter = _canonical_product_name(product) if product else None
        known_products = {_canonical_product_name(name) for _, name, *_ in rows}
        filter_is_valid = bool(normalized_filter) and normalized_filter in known_products

        # Ignore low-quality product extraction (e.g. trailing phrase fragments).
        if normalized_filter and not filter_is_valid:
            normalized_filter = None

        grouped: dict[str, dict[str, Any]] = {}
        for product_id, name, grade, total, reserved, processed_output, threshold, unit in rows:
            if normalized_filter and _canonical_product_name(name) != normalized_filter:
                continue
            key = str(product_id)
            item = grouped.setdefault(
                key,
                {
                    "product_id": key,
                    "product": str(name),
                    "status": "stable",
                    "stock_total_kg": 0.0,
                    "sorties_vente_kg": 0.0,
                    "pertes_kg": 0.0,
                    "restant_kg": 0.0,
                    "alloue_en_lot_kg": 0.0,
                    "unit": str(unit or "kg"),
                    "threshold_kg": 0.0,
                    "grades": {"A": 0.0, "B": 0.0, "C": 0.0},
                    "grade_rows": [],
                },
            )
            total_val = float(total or 0.0)
            reserved_val = float(reserved or 0.0)
            available = max(total_val - reserved_val, 0.0)
            processed_val = float(processed_output or 0.0)
            threshold_val = float(threshold or 0.0)
            grade_label = str(grade or "Non spécifié")

            item["stock_total_kg"] += total_val
            item["sorties_vente_kg"] += processed_val
            item["restant_kg"] += available
            item["alloue_en_lot_kg"] += reserved_val
            item["threshold_kg"] += threshold_val
            if grade_label in {"A", "B", "C"}:
                item["grades"][grade_label] += available
            item["grade_rows"].append(
                {
                    "grade": grade_label,
                    "total_stock_kg": total_val,
                    "available_stock_kg": available,
                    "reserved_in_lots_kg": reserved_val,
                    "processed_output_kg": processed_val,
                }
            )

        items: list[dict[str, Any]] = []
        for data in grouped.values():
            data["available_stock_kg"] = float(data["restant_kg"])
            data["total_stock_kg"] = float(data["stock_total_kg"])
            data["reserved_in_lots_kg"] = float(data["alloue_en_lot_kg"])
            data["is_low"] = float(data["restant_kg"]) < float(data["threshold_kg"])
            data["status"] = "critical" if data["is_low"] else "stable"
            items.append(data)
        items.sort(key=lambda row: str(row.get("product") or "").lower())

        warnings = []
        if normalized_filter and not items:
            warnings.append("NO_SQL_DATA")
        elif not items:
            warnings.append("NO_SQL_DATA")
        if product and not filter_is_valid:
            warnings.append("PRODUCT_FILTER_IGNORED")

        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "stocks,products",
                    "label": "Stocks courants par produit",
                    "record_count": len(items),
                    "related_product": product,
                }
            ],
            "warnings": warnings,
        }

    def get_available_postharvest_lots(self, product: str | None = None) -> dict[str, Any]:
        """List available post-harvest lots (simple listing, not ranking)."""
        stmt = (
            select(
                Batch.id,
                Batch.code,
                Product.name,
                Batch.initial_qty,
                Batch.current_qty,
                Batch.status,
                Batch.postharvest_started_at,
                Batch.unit,
            )
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .where(Batch.postharvest_started_at.isnot(None))
            .order_by(Batch.postharvest_started_at.desc())
        )
        rows = self.db.execute(stmt).all()
        items = []
        for batch_id, code, product_name, initial_qty, current_qty, status, started_at, unit in rows:
            if product and _canonical_product_name(product_name) != _canonical_product_name(product):
                continue
            initial = float(initial_qty or 0.0)
            current = float(current_qty or 0.0)
            items.append(
                {
                    "batch_id": str(batch_id),
                    "batch_ref": str(code),
                    "product": str(product_name),
                    "initial_qty": initial,
                    "current_qty": current,
                    "loss_qty": initial - current,
                    "status": str(status.value if hasattr(status, "value") else status),
                    "started_at": str(started_at) if started_at else None,
                    "unit": str(unit or "kg"),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "batches",
                    "label": "Lots disponibles en post-récolte",
                    "record_count": len(items),
                    "filter": "postharvest_started_at IS NOT NULL",
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
        resolved_lot = resolve_lot_reference(self.db, self.cooperative_id, batch_ref) if batch_ref else None
        stmt = (
            select(Batch.id, Batch.code, Batch.postharvest_reference, Product.name, Batch.initial_qty, Batch.current_qty, Batch.unit, Batch.status)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .order_by(Batch.creation_date.desc())
        )
        if batch_ref and resolved_lot is None:
            rows = []
        elif resolved_lot is not None:
            stmt = stmt.where(Batch.id == resolved_lot.batch_id)
            rows = self.db.execute(stmt).all()
        else:
            rows = self.db.execute(stmt).all()
        items = []
        for batch_id, code, postharvest_reference, product_name, initial_qty, current_qty, unit, status in rows:
            initial = float(initial_qty or 0.0)
            current = float(current_qty or 0.0)
            loss_pct = ((initial - current) / initial * 100.0) if initial > 0 else 0.0
            items.append(
                {
                    "batch_id": str(batch_id),
                    "batch_ref": str(code),
                    "requested_batch_ref": batch_ref,
                    "postharvest_reference": str(postharvest_reference) if postharvest_reference else None,
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
        resolved_lot = resolve_lot_reference(self.db, self.cooperative_id, batch_ref) if batch_ref else None
        if batch_ref and resolved_lot is None:
            return {
                "items": [],
                "sources": [
                    {
                        "type": "sql",
                        "table": "process_steps,batches",
                        "label": "Pertes par étape",
                        "record_count": 0,
                        "related_batch": batch_ref,
                        "related_stage": stage,
                        "related_product": product,
                    }
                ],
                "warnings": ["NO_MATCHING_BATCH"],
            }
        stmt = (
            select(
                ProcessStep.id,
                Batch.code,
                Product.name,
                ProcessStep.type,
                ProcessStep.qty_in,
                ProcessStep.qty_out,
                ProcessStep.date,
                ProcessStep.sequence_order,
            )
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .order_by(ProcessStep.sequence_order.asc(), ProcessStep.date.asc())
        )
        if resolved_lot is not None:
            stmt = stmt.where(Batch.id == resolved_lot.batch_id)
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        stmt = _apply_step_date_range(stmt, date_range)
        rows = self.db.execute(stmt).all()

        items = []
        for step_id, code, product_name, step_type, qty_in, qty_out, step_date, sequence_order in rows:
            if stage and _canonical_stage_name(step_type) != _canonical_stage_name(stage):
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
                    "sequence_order": int(sequence_order or 0),
                }
            )

        warnings = ["NO_SQL_DATA"] if not items else []
        if batch_ref and not items and resolved_lot is not None:
            fallback = self._postharvest_stock_movement_step_fallback(resolved_lot.batch_id)
            if fallback:
                warnings = ["PROCESS_STEP_DETAILS_MISSING_BUT_STOCK_MOVEMENTS_EXIST"]
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
            "warnings": warnings,
        }

    def get_postharvest_process_step_losses(
        self,
        batch_ref: str | None = None,
        stage: str | None = None,
        product: str | None = None,
        date_range: list[str] | None = None,
    ) -> dict[str, Any]:
        base = self.get_process_step_losses(
            batch_ref=batch_ref,
            stage=None,
            product=product,
            date_range=date_range,
        )
        rows = base.get("items", []) or []
        base_warnings = list(base.get("warnings", []))
        wanted_stage = _canonical_stage_name(stage) if stage else None
        items: list[dict[str, Any]] = []
        for row in rows:
            canonical_stage = _canonical_stage_name(row.get("stage"))
            if canonical_stage not in POST_HARVEST_STAGES and not batch_ref:
                continue
            if wanted_stage and canonical_stage != wanted_stage:
                continue
            enriched = dict(row)
            enriched["stage"] = _stage_display_label(canonical_stage) if canonical_stage in POST_HARVEST_STAGES else str(row.get("stage") or "")
            enriched["stage_canonical"] = canonical_stage
            items.append(enriched)
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "process_steps",
                    "label": "Pertes post-récolte par étape",
                    "record_count": len(items),
                    "related_batch": batch_ref,
                    "related_stage": stage,
                    "related_product": product,
                }
            ],
            "warnings": base_warnings if not items and base_warnings else ([] if items else ["NO_SQL_DATA"]),
        }

    def get_postharvest_material_balance(self, batch_ref: str | None = None, product: str | None = None) -> dict[str, Any]:
        resolved_lot = resolve_lot_reference(self.db, self.cooperative_id, batch_ref) if batch_ref else None
        if batch_ref and resolved_lot is None:
            return {
                "items": [],
                "sources": [
                    {
                        "type": "sql",
                        "table": "batches,process_steps",
                        "label": "Bilan matière post-récolte",
                        "record_count": 0,
                        "related_batch": batch_ref,
                        "related_product": product,
                    }
                ],
                "warnings": ["NO_MATCHING_BATCH"],
            }
        stmt = (
            select(
                Batch.id,
                Batch.code,
                Product.name,
                ProcessStep.type,
                ProcessStep.qty_in,
                ProcessStep.qty_out,
                ProcessStep.date,
                ProcessStep.sequence_order,
            )
            .join(ProcessStep, ProcessStep.batch_id == Batch.id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.cooperative_id)
            .order_by(Batch.code.asc(), ProcessStep.date.asc(), ProcessStep.sequence_order.asc())
        )
        if resolved_lot is not None:
            stmt = stmt.where(Batch.id == resolved_lot.batch_id)
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        rows = self.db.execute(stmt).all()
        grouped: dict[str, dict[str, Any]] = {}
        for batch_id, code, product_name, step_type, qty_in, qty_out, step_date, seq in rows:
            ref = str(code or "")
            if not ref:
                continue
            canonical_stage = _canonical_stage_name(step_type)
            if canonical_stage not in POST_HARVEST_STAGES and resolved_lot is None:
                continue
            entry = grouped.setdefault(
                ref,
                {
                    "batch_id": str(batch_id),
                    "batch_ref": ref,
                    "product": str(product_name or ""),
                    "steps": [],
                },
            )
            entry["steps"].append(
                {
                    "stage_canonical": canonical_stage,
                    "stage": _stage_display_label(canonical_stage) if canonical_stage in POST_HARVEST_STAGES else str(step_type or ""),
                    "qty_in": float(qty_in or 0.0),
                    "qty_out": float(qty_out or 0.0),
                    "date": str(step_date),
                    "sequence_order": int(seq or 0),
                }
            )

        items: list[dict[str, Any]] = []
        warnings: list[str] = []
        for ref, entry in grouped.items():
            steps = entry.get("steps", [])
            if not steps:
                continue
            steps = sorted(steps, key=lambda s: (int(s.get("sequence_order") or 0), str(s.get("date") or "")))
            input_qty = float(steps[0].get("qty_in", 0.0) or 0.0)
            output_qty = float(steps[-1].get("qty_out", 0.0) or 0.0)
            if input_qty <= 0:
                items.append(
                    {
                        "batch_id": entry["batch_id"],
                        "batch_ref": ref,
                        "product": entry["product"],
                        "input_quantity": None,
                        "output_quantity": None,
                        "loss_percentage": None,
                        "efficiency_percentage": None,
                        "is_consistent": False,
                        "consistency_issue": "MATERIAL_BALANCE_INPUT_MISSING",
                    }
                )
                warnings.append("MATERIAL_BALANCE_INPUT_MISSING")
                continue
            if output_qty > input_qty:
                items.append(
                    {
                        "batch_id": entry["batch_id"],
                        "batch_ref": ref,
                        "product": entry["product"],
                        "input_quantity": input_qty,
                        "output_quantity": output_qty,
                        "loss_percentage": None,
                        "efficiency_percentage": None,
                        "is_consistent": False,
                        "consistency_issue": "MATERIAL_BALANCE_OUTPUT_EXCEEDS_INPUT",
                    }
                )
                warnings.append("MATERIAL_BALANCE_OUTPUT_EXCEEDS_INPUT")
                continue
            loss_pct = ((input_qty - output_qty) / input_qty) * 100.0
            items.append(
                {
                    "batch_id": entry["batch_id"],
                    "batch_ref": ref,
                    "product": entry["product"],
                    "input_quantity": input_qty,
                    "output_quantity": output_qty,
                    "loss_percentage": loss_pct,
                    "efficiency_percentage": (output_qty / input_qty) * 100.0,
                    "is_consistent": True,
                    "consistency_issue": None,
                }
            )
        if not items:
            if batch_ref and resolved_lot is not None and self._postharvest_stock_movement_step_fallback(resolved_lot.batch_id):
                warnings.append("PROCESS_STEP_DETAILS_MISSING_BUT_STOCK_MOVEMENTS_EXIST")
            else:
                warnings.append("NO_SQL_DATA")
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "batches,process_steps",
                    "label": "Bilan matière post-récolte",
                    "record_count": len(items),
                    "related_batch": batch_ref,
                    "related_product": product,
                }
            ],
            "warnings": sorted(set(warnings)),
        }

    def get_canonical_material_balance(self, batch_ref: str | None = None, product: str | None = None) -> dict[str, Any]:
        """Canonical material-balance source for loss/gap/efficiency facts."""
        postharvest = self.get_postharvest_material_balance(batch_ref=batch_ref, product=product)
        rows = postharvest.get("items", []) or []
        canonical: list[dict[str, Any]] = []
        for row in rows:
            input_qty = row.get("input_quantity")
            output_qty = row.get("output_quantity")
            input_val = float(input_qty or 0.0) if input_qty is not None else 0.0
            output_val = float(output_qty or 0.0) if output_qty is not None else 0.0
            gap = input_val - output_val if input_qty is not None and output_qty is not None else None
            canonical.append(
                {
                    "batch_id": row.get("batch_id"),
                    "batch_ref": row.get("batch_ref"),
                    "product": row.get("product"),
                    "input_qty": input_qty,
                    "output_qty": output_qty,
                    "gap_qty": gap,
                    "loss_pct": row.get("loss_percentage"),
                    "efficiency_pct": row.get("efficiency_percentage"),
                    "source_tables": ["process_steps", "batches"],
                    "validity_status": "VALID" if bool(row.get("is_consistent")) else str(row.get("consistency_issue") or "INVALID"),
                }
            )
        return {
            "items": canonical,
            "sources": [
                {
                    "type": "sql",
                    "table": "process_steps,batches",
                    "label": "Bilan matière canonique",
                    "record_count": len(canonical),
                    "related_batch": batch_ref,
                    "related_product": product,
                }
            ],
            "warnings": list(postharvest.get("warnings", [])),
        }

    def get_canonical_material_balance_for_lots(self, batch_refs: list[str]) -> dict[str, Any]:
        refs = {str(item or "").strip().upper() for item in (batch_refs or []) if str(item or "").strip()}
        base = self.get_canonical_material_balance(batch_ref=None, product=None)
        rows = [row for row in (base.get("items") or []) if str(row.get("batch_ref") or "").strip().upper() in refs]
        warnings = list(base.get("warnings", []))
        if refs and not rows:
            warnings.append("NO_SQL_DATA")
        return {
            "items": rows,
            "sources": [
                {
                    "type": "sql",
                    "table": "process_steps,batches",
                    "label": "Bilan matière canonique (comparaison lots)",
                    "record_count": len(rows),
                    "related_batches": sorted(refs),
                }
            ],
            "warnings": sorted(set(warnings)),
        }

    def get_stage_loss_analysis(
        self,
        *,
        batch_ref: str | None = None,
        product: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        source = self.get_postharvest_process_step_losses(batch_ref=batch_ref, product=product, stage=stage)
        rows = source.get("items", [])
        source_warnings = source.get("warnings", [])
        if batch_ref:
            items = []
            for row in rows:
                q_in = float(row.get("qty_in", 0.0) or 0.0)
                q_out = float(row.get("qty_out", 0.0) or 0.0)
                items.append(
                    {
                        "batch_ref": row.get("batch_ref"),
                        "product": row.get("product"),
                        "stage_name": row.get("stage"),
                        "input_qty": q_in,
                        "output_qty": q_out,
                        "gap_qty": q_in - q_out,
                        "loss_pct": float(row.get("loss_pct", 0.0) or 0.0),
                        "efficiency_pct": float(row.get("efficiency_pct", 0.0) or 0.0),
                        "validity_status": "VALID" if q_in >= q_out else "INVALID_OUTPUT_GT_INPUT",
                        "source_tables": ["process_steps", "batches"],
                    }
                )
            items.sort(key=lambda item: float(item.get("loss_pct", 0.0) or 0.0), reverse=True)
        else:
            buckets: dict[str, dict[str, float | int | str]] = {}
            for row in rows:
                stage_name = str(row.get("stage") or "").strip() or "N/A"
                q_in = float(row.get("qty_in", 0.0) or 0.0)
                q_out = float(row.get("qty_out", 0.0) or 0.0)
                bucket = buckets.setdefault(
                    stage_name,
                    {
                        "input_qty": 0.0,
                        "output_qty": 0.0,
                        "loss_pct_sum": 0.0,
                        "efficiency_pct_sum": 0.0,
                        "count": 0,
                    },
                )
                bucket["input_qty"] = float(bucket["input_qty"] or 0.0) + q_in
                bucket["output_qty"] = float(bucket["output_qty"] or 0.0) + q_out
                bucket["loss_pct_sum"] = float(bucket["loss_pct_sum"] or 0.0) + float(row.get("loss_pct", 0.0) or 0.0)
                bucket["efficiency_pct_sum"] = float(bucket["efficiency_pct_sum"] or 0.0) + float(row.get("efficiency_pct", 0.0) or 0.0)
                bucket["count"] = int(bucket["count"] or 0) + 1
            items = []
            for stage_name, bucket in buckets.items():
                count = int(bucket["count"] or 0)
                if count <= 0:
                    continue
                input_qty = float(bucket["input_qty"] or 0.0)
                output_qty = float(bucket["output_qty"] or 0.0)
                items.append(
                    {
                        "batch_ref": None,
                        "product": product or "global",
                        "stage_name": stage_name,
                        "input_qty": input_qty,
                        "output_qty": output_qty,
                        "gap_qty": input_qty - output_qty,
                        "loss_pct": float(bucket["loss_pct_sum"] or 0.0) / count,
                        "efficiency_pct": float(bucket["efficiency_pct_sum"] or 0.0) / count,
                        "validity_status": "VALID",
                        "source_tables": ["process_steps", "batches"],
                    }
                )
            items.sort(key=lambda item: float(item.get("efficiency_pct", 100.0) or 100.0))
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "process_steps,batches",
                    "label": "Analyse pertes/efficacité par étape",
                    "record_count": len(items),
                    "related_batch": batch_ref,
                    "related_stage": stage,
                    "related_product": product,
                }
            ],
            "warnings": source_warnings if not items and source_warnings else ([] if items else ["NO_SQL_DATA"]),
        }

    def get_postharvest_batch_summary(self, batch_ref: str | None = None, product: str | None = None) -> dict[str, Any]:
        balance = self.get_postharvest_material_balance(batch_ref=batch_ref, product=product)
        items: list[dict[str, Any]] = []
        for row in balance.get("items", []) or []:
            items.append(
                {
                    "batch_id": row.get("batch_id"),
                    "batch_ref": row.get("batch_ref"),
                    "product": row.get("product"),
                    "initial_qty": row.get("input_quantity"),
                    "current_qty": row.get("output_quantity"),
                    "loss_pct": row.get("loss_percentage"),
                    "efficiency_pct": row.get("efficiency_percentage"),
                    "lot_domain": "POST_HARVEST_BATCH",
                    "is_consistent": bool(row.get("is_consistent")),
                    "consistency_issue": row.get("consistency_issue"),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "batches,process_steps",
                    "label": "Résumé lots post-récolte",
                    "record_count": len(items),
                    "related_batch": batch_ref,
                    "related_product": product,
                }
            ],
            "warnings": balance.get("warnings", []),
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
            .where(Member.cooperative_id == self.cooperative_id, Input.cooperative_id == self.cooperative_id)
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
        status_map: dict[str, dict[str, float]] = {}
        for row in items:
            key = str(row.get("status") or "UNKNOWN")
            entry = status_map.setdefault(key, {"count": 0.0, "amount": 0.0})
            entry["count"] += 1.0
            entry["amount"] += float(row.get("total_amount_fcfa", 0.0) or 0.0)
        status_summary = [
            {"status": status, "count": int(values["count"]), "total_amount_fcfa": float(values["amount"])}
            for status, values in sorted(status_map.items(), key=lambda kv: kv[0])
        ]
        return {
            "items": items,
            "status_summary": status_summary,
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
        status_map: dict[str, dict[str, float]] = {}
        for row in items:
            key = str(row.get("status") or "UNKNOWN")
            entry = status_map.setdefault(key, {"count": 0.0, "amount": 0.0})
            entry["count"] += 1.0
            entry["amount"] += float(row.get("total_amount_fcfa", 0.0) or 0.0)
        status_summary = [
            {"status": status, "count": int(values["count"]), "total_amount_fcfa": float(values["amount"])}
            for status, values in sorted(status_map.items(), key=lambda kv: kv[0])
        ]
        return {
            "items": items,
            "status_summary": status_summary,
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

    def get_stock_movements_journal(
        self,
        *,
        limit: int = 30,
        product: str | None = None,
        batch_ref: str | None = None,
        input_ref: str | None = None,
        direction: str | None = None,
    ) -> dict[str, Any]:
        if not self.module_available("stock_movements"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        resolved_lot = resolve_lot_reference(self.db, self.cooperative_id, batch_ref) if batch_ref else None
        if batch_ref and resolved_lot is None:
            return {
                "items": [],
                "sources": [
                    {
                        "type": "sql",
                        "table": "stock_movements,inputs,batches,products,members",
                        "label": "Journal des mouvements de stock",
                        "record_count": 0,
                        "related_product": product,
                        "related_batch": batch_ref,
                        "related_input": input_ref,
                        "related_direction": direction,
                    }
                ],
                "warnings": ["NO_MATCHING_BATCH"],
            }
        stmt = (
            select(
                StockMovement.id,
                StockMovement.movement_date,
                StockMovement.quantity_kg,
                StockMovement.movement_type,
                StockMovement.action_type,
                StockMovement.source,
                StockMovement.idempotency_key,
                StockMovement.notes,
                Product.name,
                Batch.code,
                Batch.postharvest_reference,
                Input.id,
                Input.bl_number,
                Member.full_name,
            )
            .join(Product, Product.id == StockMovement.product_id)
            .outerjoin(Batch, Batch.id == StockMovement.batch_id)
            .outerjoin(Input, Input.id == StockMovement.input_id)
            .outerjoin(Member, Member.id == Input.member_id)
            .where(StockMovement.cooperative_id == self.cooperative_id)
            .order_by(StockMovement.movement_date.desc(), StockMovement.created_at.desc())
        )
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        if resolved_lot is not None:
            stmt = stmt.where(StockMovement.batch_id == resolved_lot.batch_id)
        if input_ref:
            input_needle = str(input_ref).strip().lower()
            if input_needle.startswith("col-") and len(input_needle) > 4:
                stmt = stmt.where(func.lower(func.cast(Input.id, String)).contains(input_needle[4:]))
        if direction:
            direction_norm = str(direction).strip().lower()
            if direction_norm in {"in", "out"}:
                stmt = stmt.where(func.lower(StockMovement.movement_type) == direction_norm)
        stmt = stmt.limit(max(1, int(limit)))
        rows = self.db.execute(stmt).all()
        items: list[dict[str, Any]] = []
        batch_needle = str(batch_ref or "").strip().lower()
        input_needle = str(input_ref or "").strip().lower()
        direction_norm = str(direction or "").strip().lower()
        for movement_id, movement_date, quantity_kg, movement_type, action_type, source, idem_key, notes, product_name, lot_code, postharvest_reference, input_id, bl_number, member_name in rows:
            movement_type_norm = str(movement_type or "").strip().lower()
            if direction_norm == "out" and movement_type_norm != "out":
                continue
            if direction_norm == "in" and movement_type_norm != "in":
                continue
            lot_code_str = str(lot_code or "")
            postharvest_ref_str = str(postharvest_reference or "")
            if batch_needle and batch_needle not in lot_code_str.lower() and batch_needle not in postharvest_ref_str.lower():
                continue
            input_reference = f"COL-{str(input_id)[:8].upper()}" if input_id is not None else ""
            if input_needle and input_needle not in input_reference.lower():
                continue
            items.append(
                {
                    "movement_id": str(movement_id),
                    "movement_date": str(movement_date),
                    "quantity_kg": float(quantity_kg or 0.0),
                    "movement_type": str(movement_type or ""),
                    "action_type": str(action_type or ""),
                    "source": str(source or ""),
                    "product": str(product_name or ""),
                    "batch_ref": lot_code_str,
                    "requested_batch_ref": batch_ref,
                    "postharvest_reference": postharvest_ref_str or None,
                    "input_reference": input_reference or None,
                    "bl_number": str(bl_number or ""),
                    "member_name": str(member_name or ""),
                    "idempotency_key": str(idem_key or ""),
                    "notes": str(notes or ""),
                }
            )
        return {
            "items": items,
            "sources": [
                {
                    "type": "sql",
                    "table": "stock_movements,inputs,batches,products,members",
                    "label": "Journal des mouvements de stock",
                    "record_count": len(items),
                    "related_product": product,
                    "related_batch": batch_ref,
                    "related_input": input_ref,
                    "related_direction": direction_norm or None,
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def _postharvest_stock_movement_step_fallback(self, batch_id) -> dict[str, Any] | None:
        if not self.module_available("stock_movements"):
            return None
        row = self.db.execute(
            select(func.count(StockMovement.id), func.min(StockMovement.action_type))
            .where(
                StockMovement.cooperative_id == self.cooperative_id,
                StockMovement.batch_id == batch_id,
                func.lower(StockMovement.source) == "post_harvest_step",
            )
        ).first()
        if not row:
            return None
        count, sample_action = row
        if int(count or 0) <= 0:
            return None
        return {"movement_count": int(count or 0), "sample_action_type": str(sample_action or "")}

    def get_collecte_traceability(self) -> dict[str, Any]:
        counts_row = self.db.execute(
            select(
                func.count(Input.id),
                func.count(Input.bl_number),
                func.count(Input.justificatif_file_id),
                func.count(Input.batch_id),
            ).where(Input.cooperative_id == self.cooperative_id)
        ).one()
        total_inputs, with_bl, with_justif, linked_lot = [int(value or 0) for value in counts_row]
        rows = self.db.execute(
            select(
                Input.id,
                Input.date,
                Input.quantity,
                Input.grade,
                Input.bl_number,
                Input.justificatif_file_id,
                Batch.code,
                Product.name,
                Member.full_name,
                Input.source_type,
                Input.status,
            )
            .outerjoin(Batch, Batch.id == Input.batch_id)
            .join(Product, Product.id == Input.product_id)
            .join(Member, Member.id == Input.member_id)
            .where(Input.cooperative_id == self.cooperative_id)
            .order_by(Input.date.desc(), Input.created_at.desc())
            .limit(20)
        ).all()
        items = []
        for input_id, input_date, qty, grade, bl_number, justif_id, lot_code, product_name, member_name, source_type, status in rows:
            items.append(
                {
                    "input_id": str(input_id),
                    "input_date": str(input_date),
                    "quantity_kg": float(qty or 0.0),
                    "grade": str(grade or ""),
                    "bl_number": str(bl_number or ""),
                    "has_justificatif": bool(justif_id),
                    "batch_ref": str(lot_code or ""),
                    "product": str(product_name or ""),
                    "member_name": str(member_name or ""),
                    "source_type": str(source_type or ""),
                    "status": str(status.value if hasattr(status, "value") else status),
                }
            )
        summary = [
            {
                "total_inputs": total_inputs,
                "with_bl_number": with_bl,
                "with_justificatif": with_justif,
                "linked_to_lot": linked_lot,
            }
        ]
        return {
            "items": items,
            "summary": summary,
            "sources": [
                {
                    "type": "sql",
                    "table": "inputs,batches,members,products",
                    "label": "Traçabilité des collectes",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if total_inputs == 0 else [],
        }

    def get_uploaded_files_evidence(self) -> dict[str, Any]:
        if not self.module_available("uploaded_files"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        type_rows = self.db.execute(
            select(UploadedFile.entity_type, func.count(UploadedFile.id))
            .where(UploadedFile.cooperative_id == self.cooperative_id)
            .group_by(UploadedFile.entity_type)
            .order_by(func.count(UploadedFile.id).desc())
        ).all()
        file_rows = self.db.execute(
            select(
                UploadedFile.entity_type,
                UploadedFile.entity_id,
                UploadedFile.filename,
                UploadedFile.file_url,
                UploadedFile.mime_type,
                UploadedFile.size_bytes,
                UploadedFile.uploaded_at,
            )
            .where(UploadedFile.cooperative_id == self.cooperative_id)
            .order_by(UploadedFile.uploaded_at.desc())
            .limit(25)
        ).all()
        input_with_file = int(
            self.db.scalar(
                select(func.count(Input.id)).where(Input.cooperative_id == self.cooperative_id, Input.justificatif_file_id.isnot(None))
            )
            or 0
        )
        advance_with_devis = int(
            self.db.scalar(
                select(func.count(FarmerAdvance.id)).where(FarmerAdvance.cooperative_id == self.cooperative_id, FarmerAdvance.devis_file_id.isnot(None))
            )
            or 0
        )
        treasury_with_file = int(
            self.db.scalar(
                select(func.count(TreasuryTransaction.id)).where(
                    TreasuryTransaction.cooperative_id == self.cooperative_id,
                    TreasuryTransaction.justificatif_file_id.isnot(None),
                )
            )
            or 0
        )
        items = [
            {
                "entity_type": str(entity_type or ""),
                "entity_id": str(entity_id),
                "filename": str(filename or ""),
                "file_url": str(file_url or ""),
                "mime_type": str(mime or ""),
                "size_bytes": int(size_bytes or 0),
                "uploaded_at": str(uploaded_at),
            }
            for entity_type, entity_id, filename, file_url, mime, size_bytes, uploaded_at in file_rows
        ]
        summary = [
            {
                "uploaded_files_total": int(sum(int(c or 0) for _, c in type_rows)),
                "collecte_with_justificatif": input_with_file,
                "advance_with_devis": advance_with_devis,
                "treasury_with_justificatif": treasury_with_file,
                "entity_type_counts": [{ "entity_type": str(t or ""), "count": int(c or 0)} for t, c in type_rows],
            }
        ]
        return {
            "items": items,
            "summary": summary,
            "sources": [
                {
                    "type": "sql",
                    "table": "uploaded_files,inputs,farmer_advances,treasury_transactions",
                    "label": "Preuves documentaires uploadées",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_farmer_advances_traceability(self) -> dict[str, Any]:
        if not self.module_available("farmer_advances"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        rows = self.db.execute(
            select(
                FarmerAdvance.id,
                FarmerAdvance.advance_date,
                FarmerAdvance.amount_fcfa,
                FarmerAdvance.reason,
                FarmerAdvance.status,
                FarmerAdvance.source_type,
                FarmerAdvance.devis_file_id,
                FarmerAdvance.treasury_transaction_id,
                Member.full_name,
                Batch.code,
                Parcel.name,
                Product.name,
            )
            .join(Member, Member.id == FarmerAdvance.farmer_id)
            .outerjoin(Batch, Batch.id == FarmerAdvance.batch_id)
            .outerjoin(Parcel, Parcel.id == FarmerAdvance.parcel_id)
            .outerjoin(Product, Product.id == FarmerAdvance.product_id)
            .where(FarmerAdvance.cooperative_id == self.cooperative_id)
            .order_by(FarmerAdvance.advance_date.desc(), FarmerAdvance.created_at.desc())
            .limit(30)
        ).all()
        items = []
        with_devis = 0
        with_treasury = 0
        for advance_id, advance_date, amount_fcfa, reason, status, source_type, devis_file_id, treasury_id, member_name, batch_code, parcel_name, product_name in rows:
            if devis_file_id:
                with_devis += 1
            if treasury_id:
                with_treasury += 1
            items.append(
                {
                    "advance_id": str(advance_id),
                    "advance_date": str(advance_date),
                    "amount_fcfa": float(amount_fcfa or 0.0),
                    "reason": str(reason or ""),
                    "status": str(status.value if hasattr(status, "value") else status),
                    "source_type": str(source_type or ""),
                    "has_devis": bool(devis_file_id),
                    "treasury_synced": bool(treasury_id),
                    "member_name": str(member_name or ""),
                    "batch_ref": str(batch_code or ""),
                    "parcel_name": str(parcel_name or ""),
                    "product": str(product_name or ""),
                }
            )
        summary = [{"advance_total": len(items), "with_devis": with_devis, "with_treasury_sync": with_treasury}]
        return {
            "items": items,
            "summary": summary,
            "sources": [
                {
                    "type": "sql",
                    "table": "farmer_advances,members,batches,parcels,products,treasury_transactions",
                    "label": "Traçabilité des avances producteurs",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_treasury_traceability(self) -> dict[str, Any]:
        if not self.module_available("treasury_transactions"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        status_rows = self.db.execute(
            select(
                TreasuryTransaction.status,
                func.count(TreasuryTransaction.id),
                func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0),
            )
            .where(TreasuryTransaction.cooperative_id == self.cooperative_id)
            .group_by(TreasuryTransaction.status)
            .order_by(func.count(TreasuryTransaction.id).desc())
        ).all()
        txn_rows = self.db.execute(
            select(
                TreasuryTransaction.reference,
                TreasuryTransaction.transaction_date,
                TreasuryTransaction.type,
                TreasuryTransaction.status,
                TreasuryTransaction.amount_fcfa,
                TreasuryTransaction.source_type,
                TreasuryTransaction.source_id,
                TreasuryTransaction.receipt_reference,
                TreasuryTransaction.justificatif_file_id,
            )
            .where(TreasuryTransaction.cooperative_id == self.cooperative_id)
            .order_by(TreasuryTransaction.transaction_date.desc(), TreasuryTransaction.created_at.desc())
            .limit(40)
        ).all()
        missing_justif = 0
        enregistre_complet = 0
        with_receipt = 0
        linked_advances = 0
        linked_invoice_income = 0
        items = []
        for reference, tx_date, tx_type, status, amount_fcfa, source_type, source_id, receipt_reference, justificatif_file_id in txn_rows:
            status_value = str(status.value if hasattr(status, "value") else status)
            source_type_value = str(source_type or "")
            if not justificatif_file_id:
                missing_justif += 1
            if status_value.lower() == "enregistre_complet":
                enregistre_complet += 1
            if receipt_reference:
                with_receipt += 1
            if source_type_value == "farmer_advance":
                linked_advances += 1
            if source_type_value == "commercial_invoice":
                linked_invoice_income += 1
            items.append(
                {
                    "reference": str(reference or ""),
                    "transaction_date": str(tx_date),
                    "type": str(tx_type.value if hasattr(tx_type, "value") else tx_type),
                    "status": status_value,
                    "amount_fcfa": float(amount_fcfa or 0.0),
                    "source_type": source_type_value,
                    "source_id": str(source_id) if source_id else "",
                    "receipt_reference": str(receipt_reference or ""),
                    "has_justificatif": bool(justificatif_file_id),
                }
            )
        summary = [
            {
                "status_counts": [
                    {
                        "status": str(status.value if hasattr(status, "value") else status),
                        "count": int(count or 0),
                        "amount_fcfa": float(amount or 0.0),
                    }
                    for status, count, amount in status_rows
                ],
                "missing_justificatif_count": missing_justif,
                "enregistre_complet_count": enregistre_complet,
                "with_receipt_reference_count": with_receipt,
                "farmer_advance_linked_count": linked_advances,
                "commercial_invoice_income_linked_count": linked_invoice_income,
            }
        ]
        return {
            "items": items,
            "summary": summary,
            "sources": [
                {
                    "type": "sql",
                    "table": "treasury_transactions",
                    "label": "Traçabilité trésorerie",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
        }

    def get_commercial_invoice_linkage(self) -> dict[str, Any]:
        if not self.module_available("commercial_orders") or not self.module_available("commercial_invoices"):
            return {"items": [], "sources": [], "warnings": ["MODULE_NOT_AVAILABLE"]}
        rows = self.db.execute(
            select(
                CommercialOrder.order_number,
                CommercialOrder.status,
                CommercialOrder.total_amount_fcfa,
                CommercialInvoice.invoice_number,
                CommercialInvoice.status,
                CommercialInvoice.total_amount_fcfa,
                TreasuryTransaction.id,
                TreasuryTransaction.reference,
                TreasuryTransaction.receipt_reference,
            )
            .join(CommercialInvoice, CommercialInvoice.order_id == CommercialOrder.id)
            .outerjoin(
                TreasuryTransaction,
                and_(
                    TreasuryTransaction.source_type == "commercial_invoice",
                    TreasuryTransaction.source_id == CommercialInvoice.id,
                ),
            )
            .where(CommercialOrder.cooperative_id == self.cooperative_id)
            .order_by(CommercialOrder.received_at.desc())
            .limit(30)
        ).all()
        items = []
        paid_with_invoice = 0
        invoice_paid = 0
        treasury_linked = 0
        for order_number, order_status, order_total, invoice_number, invoice_status, invoice_total, treasury_id, treasury_ref, receipt_ref in rows:
            order_status_value = str(order_status.value if hasattr(order_status, "value") else order_status)
            invoice_status_value = str(invoice_status.value if hasattr(invoice_status, "value") else invoice_status)
            has_treasury_income = bool(treasury_id)
            if order_status_value.lower() == "paid":
                paid_with_invoice += 1
            if invoice_status_value.lower() == "paid":
                invoice_paid += 1
            if has_treasury_income:
                treasury_linked += 1
            items.append(
                {
                    "order_number": str(order_number or ""),
                    "order_status": order_status_value,
                    "order_total_fcfa": float(order_total or 0.0),
                    "invoice_number": str(invoice_number or ""),
                    "invoice_status": invoice_status_value,
                    "invoice_total_fcfa": float(invoice_total or 0.0),
                    "treasury_income_linked": has_treasury_income,
                    "treasury_reference": str(treasury_ref or ""),
                    "receipt_reference": str(receipt_ref or ""),
                }
            )
        summary = [
            {
                "linked_rows": len(items),
                "paid_orders_with_invoice": paid_with_invoice,
                "paid_invoices_count": invoice_paid,
                "treasury_income_linked_count": treasury_linked,
            }
        ]
        return {
            "items": items,
            "summary": summary,
            "sources": [
                {
                    "type": "sql",
                    "table": "commercial_orders,commercial_invoices,treasury_transactions",
                    "label": "Lien commandes/factures/trésorerie",
                    "record_count": len(items),
                }
            ],
            "warnings": ["NO_SQL_DATA"] if not items else [],
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
        items = []
        for stage, eff, loss, count in rows:
            canonical_stage = _canonical_stage_name(stage)
            if canonical_stage not in POST_HARVEST_STAGES:
                continue
            items.append(
                {
                    "stage": _stage_display_label(canonical_stage),
                    "stage_canonical": canonical_stage,
                    "avg_efficiency_pct": float(eff or 0.0),
                    "avg_loss_pct": float(loss or 0.0),
                    "record_count": int(count or 0),
                }
            )
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

    # Deterministic tools for strict query plans.
    def top_grade_by_volume(self, days: int) -> dict[str, Any]:
        since = date.today() - timedelta(days=max(1, int(days)))
        rows = self.db.execute(
            select(Input.grade, func.coalesce(func.sum(Input.quantity), 0.0).label("kg"))
            .where(Input.cooperative_id == self.cooperative_id, Input.date >= since)
            .group_by(Input.grade)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
            .limit(1)
        ).all()
        items = [{"grade": str(g), "kg": float(kg or 0.0)} for g, kg in rows]
        return {"items": items, "sources": [{"type": "sql", "table": "inputs", "label": "Top grade by volume", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def top_collection_days(self, days: int, limit: int) -> dict[str, Any]:
        since = date.today() - timedelta(days=max(1, int(days)))
        rows = self.db.execute(
            select(Input.date, func.coalesce(func.sum(Input.quantity), 0.0).label("kg"))
            .where(Input.cooperative_id == self.cooperative_id, Input.date >= since)
            .group_by(Input.date)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
            .limit(max(1, int(limit)))
        ).all()
        items = [{"date": str(d), "kg": float(kg or 0.0)} for d, kg in rows]
        return {"items": items, "sources": [{"type": "sql", "table": "inputs", "label": "Top collection days", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def lowest_nonzero_member_contributor(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(Member.full_name, func.coalesce(func.sum(Input.quantity), 0.0).label("kg"))
            .join(Input, Input.member_id == Member.id)
            .where(Member.cooperative_id == self.cooperative_id, Input.cooperative_id == self.cooperative_id)
            .group_by(Member.full_name)
            .having(func.coalesce(func.sum(Input.quantity), 0.0) > 0)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).asc())
            .limit(1)
        ).all()
        items = [{"member_name": str(name), "kg": float(kg or 0.0)} for name, kg in rows]
        return {"items": items, "sources": [{"type": "sql", "table": "members,inputs", "label": "Lowest non-zero contributor", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def largest_parcel_by_product(self, product: str) -> dict[str, Any]:
        rows = self.db.execute(
            select(Parcel.name, Parcel.surface_ha, Member.full_name, Parcel.main_culture)
            .join(Member, Member.id == Parcel.member_id)
            .where(Parcel.cooperative_id == self.cooperative_id)
            .order_by(Parcel.surface_ha.desc())
        ).all()
        items: list[dict[str, Any]] = []
        for name, area, member, culture in rows:
            if product and _canonical_product_name(culture or "") != _canonical_product_name(product or ""):
                continue
            items = [{"parcel_name": str(name), "surface_ha": float(area or 0.0), "member_name": str(member)}]
            break
        return {"items": items, "sources": [{"type": "sql", "table": "parcels,members", "label": "Largest parcel by product", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def available_stock_gap(self, product: str) -> dict[str, Any]:
        rows = self.get_current_stock(product=product).get("items", [])
        if not rows:
            return {"items": [], "sources": [{"type": "sql", "table": "stocks", "label": "Available stock gap", "record_count": 0}], "warnings": ["NO_SQL_DATA"]}
        row = rows[0]
        available = float(row.get("available_stock_kg", 0.0) or 0.0)
        threshold = float(row.get("threshold_kg", 0.0) or 0.0)
        return {"items": [{"product": row.get("product"), "available_kg": available, "gap_kg": available - threshold}], "sources": [{"type": "sql", "table": "stocks", "label": "Available stock gap", "record_count": 1}], "warnings": []}

    def oldest_open_lot(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(Batch.code, Batch.creation_date, Batch.status)
            .where(Batch.cooperative_id == self.cooperative_id)
            .order_by(Batch.creation_date.asc())
        ).all()
        items: list[dict[str, Any]] = []
        for code, created, status in rows:
            s = str(status.value if hasattr(status, "value") else status).lower()
            if s in {"completed", "cancelled", "archived"}:
                continue
            items = [{"lot_code": str(code), "creation_date": str(created)}]
            break
        return {"items": items, "sources": [{"type": "sql", "table": "batches", "label": "Oldest open lot", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def process_stage_loss_ranking(self, days: int) -> dict[str, Any]:
        since = date.today() - timedelta(days=max(1, int(days)))
        rows = self.db.execute(
            select(ProcessStep.type, func.coalesce(func.sum(ProcessStep.loss_value), 0.0).label("kg_loss"))
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .where(Batch.cooperative_id == self.cooperative_id, ProcessStep.date >= since)
            .group_by(ProcessStep.type)
            .order_by(func.coalesce(func.sum(ProcessStep.loss_value), 0.0).desc())
            .limit(1)
        ).all()
        items = [{"stage": str(stage), "kg_loss": float(kg or 0.0)} for stage, kg in rows]
        return {"items": items, "sources": [{"type": "sql", "table": "process_steps", "label": "Process stage loss ranking", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def avg_paid_invoices_current_quarter(self) -> dict[str, Any]:
        today = date.today()
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        start = date(today.year, q_start_month, 1)
        rows = self.db.execute(
            select(CommercialInvoice.total_amount_fcfa, CommercialInvoice.status, CommercialInvoice.issue_date)
            .where(CommercialInvoice.cooperative_id == self.cooperative_id, CommercialInvoice.issue_date >= start)
        ).all()
        paid_values: list[float] = []
        for total, status, _ in rows:
            s = str(status.value if hasattr(status, "value") else status).lower()
            if s == "paid":
                paid_values.append(float(total or 0.0))
        avg_value = (sum(paid_values) / len(paid_values)) if paid_values else None
        items = [{"avg_paid_invoice_fcfa": float(avg_value)}] if avg_value is not None else []
        return {"items": items, "sources": [{"type": "sql", "table": "commercial_invoices", "label": "Average paid invoice (current quarter)", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def top_customer_by_orders(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(CommercialOrder.customer_name, func.coalesce(func.sum(CommercialOrder.total_amount_fcfa), 0.0).label("total"))
            .where(CommercialOrder.cooperative_id == self.cooperative_id)
            .group_by(CommercialOrder.customer_name)
            .order_by(func.coalesce(func.sum(CommercialOrder.total_amount_fcfa), 0.0).desc())
            .limit(1)
        ).all()
        items = [{"customer_name": str(name), "total_amount_fcfa": float(total or 0.0)} for name, total in rows]
        return {"items": items, "sources": [{"type": "sql", "table": "commercial_orders", "label": "Top customer by orders", "record_count": len(items)}], "warnings": ["NO_SQL_DATA"] if not items else []}

    def month_vs_month_charges(self) -> dict[str, Any]:
        today = date.today()
        start_current = date(today.year, today.month, 1)
        if today.month == 1:
            start_previous = date(today.year - 1, 12, 1)
        else:
            start_previous = date(today.year, today.month - 1, 1)
        end_previous = start_current - timedelta(days=1)

        current_total = 0.0
        previous_total = 0.0
        using_global = self.module_available("global_charges")
        if using_global:
            gc_rows = self.db.execute(
                select(GlobalCharge.date, GlobalCharge.amount_fcfa).where(GlobalCharge.cooperative_id == self.cooperative_id)
            ).all()
            for dt, amt in gc_rows:
                if dt is None:
                    continue
                value = float(amt or 0.0)
                if dt >= start_current:
                    current_total += value
                elif start_previous <= dt <= end_previous:
                    previous_total += value
        elif self.module_available("treasury_transactions"):
            tx_rows = self.db.execute(
                select(TreasuryTransaction.transaction_date, TreasuryTransaction.amount_fcfa, TreasuryTransaction.type, TreasuryTransaction.status).where(
                    TreasuryTransaction.cooperative_id == self.cooperative_id
                )
            ).all()
            for dt, amt, tx_type, tx_status in tx_rows:
                if dt is None:
                    continue
                tx_type_value = str(tx_type.value if hasattr(tx_type, "value") else tx_type).lower()
                tx_status_value = str(tx_status.value if hasattr(tx_status, "value") else tx_status).lower()
                if tx_type_value != "expense" or tx_status_value == "cancelled":
                    continue
                value = float(amt or 0.0)
                if dt >= start_current:
                    current_total += value
                elif start_previous <= dt <= end_previous:
                    previous_total += value
        items = [{"current_month_fcfa": current_total, "previous_month_fcfa": previous_total}]
        return {"items": items, "sources": [{"type": "sql", "table": "global_charges,treasury_transactions", "label": "Month vs month charges", "record_count": 1}], "warnings": []}


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


def _stage_display_label(canonical_stage: str) -> str:
    labels = {
        "cleaning": "Nettoyage",
        "drying": "Séchage",
        "sorting": "Tri",
        "packaging": "Emballage / Conditionnement",
        "storage": "Stockage",
    }
    return labels.get(str(canonical_stage or "").strip().lower(), str(canonical_stage or ""))
