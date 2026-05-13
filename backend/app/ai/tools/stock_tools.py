from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import canonical_product_name, missing_module_response, source, tool_response, warnings_for_empty
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User


class StockTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def get_current_stock(self, product: str | None = None) -> dict[str, Any]:
        rows = self.db.execute(
            select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold, Stock.unit)
            .join(Product, Product.id == Stock.product_id)
            .where(Stock.cooperative_id == self.current_user.cooperative_id)
            .order_by(Product.name.asc())
        ).all()
        data = []
        for name, total, reserved, threshold, unit in rows:
            if product and canonical_product_name(name) != canonical_product_name(product):
                continue
            available = float(total or 0.0) - float(reserved or 0.0)
            data.append(
                {
                    "product": str(name),
                    "total_stock_kg": float(total or 0.0),
                    "reserved_stock_kg": float(reserved or 0.0),
                    "available_stock_kg": available,
                    "threshold_kg": float(threshold or 0.0),
                    "unit": str(unit or "kg"),
                    "is_low": available < float(threshold or 0.0),
                }
            )
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="stocks", label="Stocks actuels", record_count=len(data), related_product=product)],
            warnings=warnings_for_empty(data),
        )

    def get_low_stock_alerts(self) -> dict[str, Any]:
        stock_result = self.get_current_stock()
        data = [item for item in stock_result["data"] if item.get("is_low")]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="stocks", label="Alertes de stock bas", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def get_stock_movements(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        return missing_module_response()

    def get_stock_summary_by_product(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(Product.name, func.coalesce(func.sum(Stock.total_stock_kg), 0.0), func.coalesce(func.sum(Stock.reserved_in_lots_kg), 0.0))
            .join(Product, Product.id == Stock.product_id)
            .where(Stock.cooperative_id == self.current_user.cooperative_id)
            .group_by(Product.name)
            .order_by(Product.name.asc())
        ).all()
        data = [
            {
                "product": str(name),
                "total_stock_kg": float(total or 0.0),
                "reserved_stock_kg": float(reserved or 0.0),
                "available_stock_kg": float(total or 0.0) - float(reserved or 0.0),
            }
            for name, total, reserved in rows
        ]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="stocks,products", label="Résumé des stocks par produit", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )
