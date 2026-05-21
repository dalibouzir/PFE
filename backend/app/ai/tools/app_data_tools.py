from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, and_
from sqlalchemy.orm import Session

from app.models.user import User


MISSING_MODULE_WARNING = "Ce module n’est pas encore disponible dans les données."
EMPTY_DATA_WARNING = "Aucune donnée disponible pour cette recherche."
INCOMPLETE_DATA_WARNING = "Certaines données nécessaires sont incomplètes."


def tool_response(
    *,
    ok: bool,
    data: Any,
    sources: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    evidence_status: str | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": ok,
        "data": data,
        "sources": sources or [],
        "warnings": warnings or [],
    }
    if evidence_status:
        payload["evidence_status"] = str(evidence_status)
    return payload


def missing_module_response() -> dict[str, Any]:
    return tool_response(ok=False, data=None, sources=[], warnings=[MISSING_MODULE_WARNING])


def source(*, table: str, label: str, record_count: int, source_type: str = "sql", **extra: Any) -> dict[str, Any]:
    payload = {"type": source_type, "table": table, "label": label, "record_count": int(record_count)}
    payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


def warnings_for_empty(data: Any) -> list[str]:
    if data is None:
        return [EMPTY_DATA_WARNING]
    if isinstance(data, (list, tuple, dict)) and len(data) == 0:
        return [EMPTY_DATA_WARNING]
    return []


def enum_value(value: Any) -> str:
    return str(value.value if hasattr(value, "value") else value)


def canonical_product_name(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "mangue": "mango",
        "mango": "mango",
        "arachide": "peanut",
        "peanut": "peanut",
        "mil": "millet",
        "millet": "millet",
    }
    return aliases.get(normalized, normalized)


def product_aliases(value: str | None) -> list[str]:
    canonical = canonical_product_name(value)
    reverse = {
        "mango": ["mango", "mangue"],
        "peanut": ["peanut", "arachide"],
        "millet": ["millet", "mil"],
    }
    return reverse.get(canonical, [canonical])


def parse_date_range(date_range: list[str] | None) -> tuple[date | None, date | None]:
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


def apply_date_filter(stmt: Select, column: Any, date_range: list[str] | None) -> Select:
    start, end = parse_date_range(date_range)
    if start and end:
        return stmt.where(and_(column >= start, column <= end))
    return stmt


class AppDataTools:
    """Facade exposing controlled app-data tools without arbitrary SQL execution."""

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    @property
    def members(self):
        from app.ai.tools.member_tools import MemberTools

        return MemberTools(self.db, self.current_user)

    @property
    def collections(self):
        from app.ai.tools.collection_tools import CollectionTools

        return CollectionTools(self.db, self.current_user)

    @property
    def stocks(self):
        from app.ai.tools.stock_tools import StockTools

        return StockTools(self.db, self.current_user)

    @property
    def preharvest(self):
        from app.ai.tools.preharvest_tools import PreharvestTools

        return PreharvestTools(self.db, self.current_user)

    @property
    def postharvest(self):
        from app.ai.tools.postharvest_tools import PostharvestTools

        return PostharvestTools(self.db, self.current_user)

    @property
    def material_balance(self):
        from app.ai.tools.material_balance_tools import MaterialBalanceTools

        return MaterialBalanceTools(self.db, self.current_user)

    @property
    def ml(self):
        from app.ai.tools.ml_tools import MLTools

        return MLTools(self.db, self.current_user)

    @property
    def rag(self):
        from app.ai.tools.rag_tools import RAGTools

        return RAGTools(self.db, self.current_user)

    @property
    def recommendations(self):
        from app.ai.tools.recommendation_tools import RecommendationTools

        return RecommendationTools(self.db, self.current_user)
