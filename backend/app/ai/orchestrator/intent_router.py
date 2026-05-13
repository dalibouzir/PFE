from __future__ import annotations

import re
import unicodedata

from app.ai.orchestrator.agent_types import IntentRouteDecision
from app.ai.orchestrator.entity_extractor import EntityExtractor
from app.ai.schemas.agent_schemas import AgentRoute

PRODUCT_MAP = {
    "mangue": "mango",
    "mango": "mango",
    "arachide": "peanut",
    "peanut": "peanut",
    "mil": "millet",
    "millet": "millet",
    "bissap": "bissap",
}
STAGE_MAP = {
    "nettoyage": "cleaning",
    "cleaning": "cleaning",
    "sechage": "drying",
    "séchage": "drying",
    "drying": "drying",
    "tri": "sorting",
    "sorting": "sorting",
    "emballage": "packaging",
    "packaging": "packaging",
    "conditionnement": "packaging",
    "storage": "storage",
    "stockage": "storage",
}
SMALL_TALK = {"bonjour", "salut", "hello", "hi", "bonsoir"}
OUT_SCOPE = {"champions league", "football", "nba", "bitcoin", "weather", "météo", "movie", "film"}
RECO_HINTS = {"recommand", "actions prioritaires", "que faire", "plan d'action", "action plan"}
RISK_HINTS = {"risque", "risk", "anomal", "prédiction", "prediction"}
EXPLANATION_HINTS = {
    "explique",
    "explain",
    "pourquoi",
    "why",
    "cause",
    "bonnes pratiques",
    "best practices",
    "comment réduire",
    "comment ameliorer",
    "comment améliorer",
    "meilleures pratiques",
    "références",
    "references",
}
BEST_PRACTICE_HINTS = {
    "bonnes pratiques",
    "meilleures pratiques",
    "best practices",
    "références",
    "references",
    "comment réduire",
    "comment ameliorer",
    "comment améliorer",
}
REFERENCE_HINTS = {"ce lot", "celui-ci", "celui ci", "ces risques", "ce risque", "cette étape", "cette etape"}
DATE_RANGE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
LOT_PATTERN = re.compile(r"\b(?:LOT|BATCH|MANG|MANGO|ARA|ARACH|MIL|BISS)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)


class IntentRouter:
    """Ruflo-inspired architecture with lightweight agent orchestration and controlled tool execution."""

    def __init__(self, entity_extractor: EntityExtractor | None = None):
        self.entity_extractor = entity_extractor or EntityExtractor()

    def classify(self, query: str, *, language_hint: str | None = None, known_batch_refs: set[str] | None = None) -> IntentRouteDecision:
        raw = str(query or "").strip()
        normalized = _normalize(raw)
        lowered = normalized.lower()

        entities = self.entity_extractor.extract(raw, language_hint=language_hint, known_batch_refs=known_batch_refs).as_dict()
        scope = str(entities.get("scope") or "global")
        module = str(entities.get("module") or "global")

        if lowered in SMALL_TALK or len(lowered.split()) <= 2 and lowered in SMALL_TALK:
            return IntentRouteDecision(
                route=AgentRoute.SMALL_TALK,
                confidence=0.98,
                detected_entities=entities,
                required_agents=["SmallTalkAgent"],
                explanation="Greeting/small-talk pattern detected.",
            )

        if any(token in lowered for token in OUT_SCOPE):
            return IntentRouteDecision(
                route=AgentRoute.OUT_OF_SCOPE,
                confidence=0.97,
                detected_entities=entities,
                required_agents=["OutOfScopeAgent"],
                explanation="Query appears outside cooperative decision-support domain.",
            )

        asks_recommendation = _has_any(lowered, RECO_HINTS)
        asks_risk = _has_any(lowered, RISK_HINTS)
        asks_explanation = _has_any(lowered, EXPLANATION_HINTS)
        asks_reference = any(token in lowered for token in ("référence", "references", "source fiable", "avec source"))
        has_reference_pronoun = _has_any(lowered, REFERENCE_HINTS)
        has_batch_or_postharvest = bool(entities.get("batch_ref")) or scope in {"batch", "post_harvest"}

        is_members = module == "members"
        is_member_value = module == "member_value"
        is_collections = module == "collections"
        is_stocks = module == "stocks"
        is_invoices = module == "invoices"
        is_commercial = module == "commercial"
        is_finance = module == "finance"
        is_preharvest = module == "pre_harvest" or scope == "pre_harvest"
        is_material_balance = module == "material_balance" or "bilan matière" in lowered or "bilan matiere" in lowered or "material balance" in lowered
        is_process = has_batch_or_postharvest or any(
            token in lowered
            for token in ("étape", "etape", "process", "flux matière", "flux matiere", "séchage", "sechage", "tri", "emballage", "perte", "loss")
        )
        is_pure_knowledge = module == "rag_knowledge" and not any(
            [is_members, is_member_value, is_collections, is_stocks, is_invoices, is_commercial, is_finance, is_preharvest, is_material_balance, is_process, asks_risk]
        )
        asks_best_practice = _has_any(lowered, BEST_PRACTICE_HINTS)
        asks_stock = any(token in lowered for token in ("stock", "kg", "disponible"))
        explicit_operational_target = any(
            token in lowered for token in ("lot ", "lots ", "batch", "stock", "collecte", "membre", "facture", "commande", "charge", "trésorerie", "tresorerie")
        )
        asks_multi_sql_rag = asks_stock and (asks_best_practice or asks_explanation or asks_reference)

        if asks_multi_sql_rag:
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Question multi-intention SQL + bonnes pratiques.",
                0.9,
            )

        if asks_recommendation:
            if is_members or is_collections or is_stocks or is_preharvest or is_process or is_material_balance or asks_risk or has_reference_pronoun:
                return _decision(
                    AgentRoute.HYBRID_FULL,
                    entities,
                    ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                    "Recommendation with operational context.",
                    0.86,
                )
            if asks_explanation or is_pure_knowledge:
                return _decision(
                    AgentRoute.HYBRID_RAG_RECOMMENDATION,
                    entities,
                    ["RAGKnowledgeAgent", "RecommendationAgent"],
                    "Knowledge-backed recommendation request.",
                    0.84,
                )
            return _decision(
                AgentRoute.RECOMMENDATION_ONLY,
                entities,
                ["RecommendationAgent"],
                "Recommendation-only request.",
                0.76,
            )

        if asks_risk:
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Risk or anomaly operational request.",
                0.9,
            )

        if is_members or is_member_value or is_collections or is_invoices or is_commercial or is_finance:
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Operational business data request.",
                0.9,
            )

        if is_stocks:
            if asks_explanation or asks_best_practice or asks_reference:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Stock question with explicit explanation or best-practice request.",
                    0.84,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Operational stock request.",
                0.9,
            )

        if is_preharvest:
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Pre-harvest operational request.",
                0.88,
            )

        if is_material_balance:
            if asks_explanation:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Material balance with explicit explanation.",
                    0.84,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Material balance operational request.",
                0.88,
            )

        if asks_best_practice and not explicit_operational_target:
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Best-practice question should prioritize knowledge retrieval.",
                0.86,
            )

        if asks_reference and not explicit_operational_target:
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Reference-seeking question should prioritize knowledge retrieval.",
                0.84,
            )

        if is_process:
            if asks_explanation:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Process/loss request with explanation.",
                    0.85,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Process/loss operational request.",
                0.89,
            )

        if is_pure_knowledge or asks_explanation or asks_reference:
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Knowledge or best-practice explanation request.",
                0.82,
            )

        return _decision(
            AgentRoute.SQL_ONLY,
            entities,
            ["SQLAnalyticsAgent"],
            "Default deterministic operational fallback.",
            0.7,
        )


def _decision(route: AgentRoute, entities: dict, agents: list[str], explanation: str, confidence: float) -> IntentRouteDecision:
    return IntentRouteDecision(
        route=route,
        confidence=confidence,
        detected_entities=entities,
        required_agents=agents,
        explanation=explanation,
    )


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _detect_products(text: str) -> list[str]:
    return sorted({canonical for token, canonical in PRODUCT_MAP.items() if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)})


def _detect_stages(text: str) -> list[str]:
    return sorted({canonical for token, canonical in STAGE_MAP.items() if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)})


def _detect_lot(text: str) -> str | None:
    match = LOT_PATTERN.search(text or "")
    return match.group(0).upper() if match else None


def _detect_member(text: str) -> str | None:
    match = re.search(r"(?:membre|member|farmer)\s+([A-Za-z][\w\- ]{1,60})", text or "", re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _detect_metrics(text: str) -> list[str]:
    metric_map = {
        "perte": "loss",
        "loss": "loss",
        "efficacite": "efficiency",
        "efficacité": "efficiency",
        "efficiency": "efficiency",
        "stock": "stock",
        "collecte": "collection",
        "anomal": "anomaly",
        "risque": "risk",
        "risk": "risk",
        "recommand": "recommendation",
    }
    result = {value for key, value in metric_map.items() if key in text}
    return sorted(result)


def _detect_language(text: str, hint: str | None) -> str:
    if hint:
        hinted = str(hint).lower().strip()
        if hinted in {"fr", "en", "ar"}:
            return hinted
    french_markers = {"bonjour", "quel", "pourquoi", "lot", "séchage", "efficacité"}
    english_markers = {"hello", "what", "why", "which", "batch", "drying"}
    fr_hits = sum(1 for token in french_markers if token in text)
    en_hits = sum(1 for token in english_markers if token in text)
    if en_hits > fr_hits:
        return "en"
    return "fr"


def _has_any(text: str, hints: set[str]) -> bool:
    return any(hint in text for hint in hints)


def _is_stage_loss_causal_question(text: str, entities: dict) -> bool:
    if not entities.get("stage") or "loss" not in (entities.get("metric") or []):
        return False
    causal_terms = ("pourquoi", "why", "cause", "causes", "élev", "eleve", "beaucoup", "forte", "fortes")
    return any(term in text for term in causal_terms)
