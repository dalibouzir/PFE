from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
import unicodedata


class RetrievalIntentType(str, Enum):
    SMALL_TALK = "SMALL_TALK"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
    SQL_ONLY = "SQL_ONLY"
    RAG_ONLY = "RAG_ONLY"
    HYBRID = "HYBRID"
    UNSUPPORTED = "UNSUPPORTED"


SUPPORTED_SQL_DOMAINS = {
    "stocks",
    "inputs",
    "batches",
    "process_steps",
    "losses",
    "members",
    "parcels",
    "pre_harvest",
    "recommendations",
    "treasury",
    "farmer_advances",
    "commercial_orders",
    "commercial_invoices",
    "ml_metrics",
    "dashboard",
}

SUPPORTED_RAG_CHUNK_TYPES = {
    "batch_summary",
    "lot_status_summary",
    "lot_recommendation_summary",
    "operational_risk_summary",
    "scoped_loss_summary",
    "product_stage_summary",
    "process_step_summary",
    "recommendation_context",
    "anomaly_context",
    "agronomic_knowledge",
    "benchmark_reference",
    "parcel_context",
    "pre_harvest_context",
    "commercial_context",
    "ml_evaluation_context",
}


@dataclass
class RetrievalPlan:
    intent_type: str
    confidence: float
    sql_needed: bool
    rag_needed: bool
    reason: str
    suggested_sql_domains: list[str] = field(default_factory=list)
    suggested_rag_chunk_types: list[str] = field(default_factory=list)
    detected_entities: dict = field(default_factory=dict)
    safety_notes: list[str] = field(default_factory=list)


TOKEN_PATTERN = re.compile(r"[\w\-']+", flags=re.UNICODE)
LOT_CODE_PATTERN = re.compile(r"\b(?:LOT|BATCH|DEMO-ML|BENCH-ML)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)
INVOICE_CODE_PATTERN = re.compile(r"\b(?:INV|FACT|FACTURE)[-_]?[A-Z0-9]{2,}\b", re.IGNORECASE)
ORDER_CODE_PATTERN = re.compile(r"\b(?:ORD|CMD|ORDER|COMMANDE)[-_]?[A-Z0-9]{2,}\b", re.IGNORECASE)

PRODUCT_MAP = {
    "mangue": "mangue",
    "mango": "mango",
    "arachide": "arachide",
    "peanut": "peanut",
    "mil": "mil",
    "millet": "millet",
    "bissap": "bissap",
}
STAGE_MAP = {
    "nettoyage": "nettoyage",
    "cleaning": "cleaning",
    "sechage": "sechage",
    "séchage": "sechage",
    "drying": "drying",
    "tri": "tri",
    "sorting": "sorting",
    "emballage": "emballage",
    "packaging": "packaging",
}
TIME_HINTS = {
    "today",
    "this week",
    "this month",
    "last week",
    "yesterday",
    "current",
    "latest",
    "aujourd'hui",
    "cette semaine",
    "ce mois",
    "semaine derniere",
    "semaine dernière",
    "hier",
    "actuel",
    "actuelle",
    "derniere",
    "dernière",
}

CURRENT_DATA_HINTS = {
    "current",
    "latest",
    "today",
    "yesterday",
    "aujourd hui",
    "actuel",
    "actuelle",
    "en ce moment",
    "cette semaine",
    "ce mois",
    "hier",
}

DOMAIN_HINTS = {
    "stock",
    "stocks",
    "input",
    "inputs",
    "collecte",
    "batch",
    "batches",
    "lot",
    "lots",
    "process",
    "loss",
    "losses",
    "perte",
    "pertes",
    "member",
    "members",
    "membre",
    "membres",
    "parcel",
    "parcels",
    "parcelle",
    "parcelles",
    "surface",
    "pre-harvest",
    "preharvest",
    "post-récolte",
    "post-recolte",
    "post recolte",
    "post récolte",
    "conservation",
    "stockage",
    "recommendation",
    "recommendations",
    "treasury",
    "avance",
    "advances",
    "invoice",
    "invoices",
    "facture",
    "factures",
    "order",
    "orders",
    "commande",
    "commandes",
    "agronomic",
    "agronomique",
    "agronomiques",
    "reference",
    "references",
    "références",
    "culture",
    "cooperative",
    "coopérative",
    "coop",
    "dashboard",
    "benchmark",
    "ml",
    "anomaly",
    "anomalie",
    "charge",
    "charges",
    "categorie",
    "catégorie",
    "prediction",
    "predictions",
}

SQL_FACTUAL_HINTS = {
    "stock actuel",
    "stock current",
    "current stock",
    "stock disponible",
    "available stock",
    "stock reserve",
    "stock réservé",
    "reserved stock",
    "quantite disponible",
    "quantité disponible",
    "quantite reservee",
    "quantité réservée",
    "statut du lot",
    "statut lot",
    "lot status",
    "total collecte",
    "collection total",
    "lots actifs",
    "active lots",
    "liste des lots actifs",
    "stock restant",
    "liste membres",
    "list members",
    "member details",
    "member total collection",
    "total collecte",
    "parcelles du membre",
    "parcels by member",
    "culture par parcelle",
    "surface parcelle",
    "open orders",
    "order status",
    "commande en cours",
    "statut commande",
    "unpaid invoices",
    "overdue invoices",
    "factures impayees",
    "factures impayées",
    "invoice status",
    "charges totales",
    "charges by category",
    "farmer advances",
    "tresorerie",
    "trésorerie",
    "latest predictions",
    "latest ml predictions",
    "risk predictions",
}

HYBRID_ANALYSIS_HINTS = {
    "why",
    "pourquoi",
    "explique",
    "explain",
    "expliquer",
    "compare",
    "comparer",
    "performance des lots",
    "bilan matiere",
    "bilan matière",
    "risques associes",
    "risques associés",
    "ecarts",
    "écarts",
    "anomalie",
    "anomalies",
    "recommandations operationnelles",
    "recommandations opérationnelles",
    "recommandation operationnelle",
    "recommandation opérationnelle",
    "efficacite",
    "efficacité",
    "rendement",
    "cause",
    "causes",
    "raison",
    "que faire",
    "croise",
    "croiser",
    "croisee",
    "croisée",
    "cross",
    "reasons",
    "what should we do",
    "should we do",
    "context",
}

RAG_GUIDANCE_HINTS = {
    "bonnes pratiques",
    "meilleures pratiques",
    "best practices",
    "good practices",
    "conseils",
    "references",
    "références",
    "benchmarks",
    "sources",
    "seuils recommandes",
    "seuils recommandés",
    "prevention",
    "prévention",
    "conservation",
    "pratiques agronomiques",
    "agronomique",
    "agronomic",
    "post recolte",
    "post récolte",
    "benchmark",
    "reference",
    "literature",
    "aphlis",
    "fao",
    "lessons learned",
}

OUT_OF_SCOPE_HINTS = {
    "movie",
    "movies",
    "film",
    "films",
    "politics",
    "politique",
    "president",
    "celebrity",
    "recipe",
    "travel",
    "football",
    "nba",
    "nfl",
    "bitcoin",
    "astrology",
    "horoscope",
    "dating",
    "crypto",
    "weather",
    "meteo",
    "météo",
}

SMALL_TALK_EXACT_HINTS = {
    "hello",
    "hi",
    "bonjour",
    "salut",
    "ca va",
    "ça va",
    "merci",
    "ok",
    "test",
    "coucou",
    "hey",
}

SMALL_TALK_TOKEN_HINTS = {
    "hello",
    "hi",
    "bonjour",
    "salut",
    "merci",
    "ok",
    "test",
    "coucou",
    "hey",
}

CLARIFICATION_HINTS = {
    "analyse",
    "donne moi",
    "quoi",
    "aide",
    "explique",
}

OPERATIONAL_TRIGGER_HINTS = {
    "stock",
    "stocks",
    "stockage",
    "disponible",
    "available",
    "reserve",
    "réservé",
    "réserve",
    "quantite",
    "quantité",
    "lot",
    "lots",
    "perte",
    "pertes",
    "risque",
    "risques",
    "rendement",
    "efficacite",
    "efficacité",
    "sechage",
    "séchage",
    "tri",
    "nettoyage",
    "emballage",
    "collecte",
    "mangue",
    "mil",
    "arachide",
    "producteur",
    "cooperative",
    "coopérative",
    "transformation",
    "recommandation",
    "recommandations",
    "anomalie",
    "processus",
    "bilan matiere",
    "bilan matière",
    "facture",
    "factures",
    "invoice",
    "invoices",
    "commande",
    "commandes",
    "order",
    "orders",
    "tresorerie",
    "trésorerie",
    "treasury",
    "member",
    "members",
    "membre",
    "membres",
    "farmer",
    "farmers",
    "parcel",
    "parcels",
    "parcelle",
    "parcelles",
    "surface",
    "grade",
    "grades",
    "feedback",
    "cout",
    "coût",
    "cost",
    "kg",
    "charge",
    "charges",
    "ml",
    "prediction",
    "predictions",
    "categorie",
    "catégorie",
}


def _is_member_directory_request(normalized: str, tokens: set[str]) -> bool:
    has_member = bool({"membre", "membres", "member", "members", "producteur", "producteurs", "farmer", "farmers"} & tokens)
    has_list = bool({"liste", "lister", "list", "listing", "affiche", "afficher", "montre", "montrer", "tableau", "table"} & tokens)
    return has_member and has_list


def _is_lot_table_request(normalized: str, tokens: set[str]) -> bool:
    has_lot = bool({"lot", "lots", "batch", "batches"} & tokens)
    has_table = bool({"tableau", "table", "liste", "lister", "list", "affiche", "afficher", "montre", "montrer"} & tokens)
    return has_lot and has_table


def build_retrieval_plan(message: str, *, mode: str | None = None) -> RetrievalPlan:
    text = " ".join(message.strip().split())
    lowered = text.lower()
    normalized = _strip_accents(_normalize_message(lowered))
    tokens = _tokenize(normalized)

    if mode == "quick" and re.fullmatch(r"\s*\d+(?:\s*[\+\-\*/]\s*\d+)+\s*\??\s*", text):
        return RetrievalPlan(
            intent_type=RetrievalIntentType.HYBRID.value,
            confidence=0.5,
            sql_needed=False,
            rag_needed=False,
            reason="Quick arithmetic input; no business retrieval required.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=[],
            detected_entities={},
            safety_notes=[],
        )

    if _is_small_talk(normalized, tokens):
        return RetrievalPlan(
            intent_type=RetrievalIntentType.SMALL_TALK.value,
            confidence=0.99,
            sql_needed=False,
            rag_needed=False,
            reason="Small-talk greeting or conversational acknowledgement detected.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=[],
            detected_entities={},
            safety_notes=["Do not run SQL, RAG, ML, or hybrid orchestration for small-talk inputs."],
        )
    if _needs_clarification(normalized, tokens):
        return RetrievalPlan(
            intent_type=RetrievalIntentType.CLARIFICATION_NEEDED.value,
            confidence=0.9,
            sql_needed=False,
            rag_needed=False,
            reason="Input is too vague and lacks operational entities or metrics.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=[],
            detected_entities={},
            safety_notes=["Ask for a precise operational question before retrieval."],
        )

    entities = _detect_entities(text=text, lowered=lowered)
    sql_domains = _detect_sql_domains(lowered, tokens)
    rag_chunk_types = _detect_rag_chunk_types(lowered, tokens)

    if _is_member_directory_request(normalized, tokens):
        return RetrievalPlan(
            intent_type=RetrievalIntentType.SQL_ONLY.value,
            confidence=0.96,
            sql_needed=True,
            rag_needed=False,
            reason="Deterministic member-directory list/table request.",
            suggested_sql_domains=["members"],
            suggested_rag_chunk_types=[],
            detected_entities=entities,
            safety_notes=["Prefer deterministic SQL member directory output with table schema."],
        )
    if _is_lot_table_request(normalized, tokens):
        return RetrievalPlan(
            intent_type=RetrievalIntentType.SQL_ONLY.value,
            confidence=0.96,
            sql_needed=True,
            rag_needed=False,
            reason="Deterministic lot table/list request.",
            suggested_sql_domains=["batches", "losses"],
            suggested_rag_chunk_types=[],
            detected_entities=entities,
            safety_notes=["Prefer deterministic SQL lot directory output with table schema."],
        )

    has_operational_trigger = _has_operational_trigger(normalized, tokens, entities)
    is_project_related = _is_project_related(lowered, tokens, entities, has_operational_trigger=has_operational_trigger)
    has_current_data_hint = _has_signal(normalized, CURRENT_DATA_HINTS)
    has_time_hint = bool(entities.get("time_hints"))
    hybrid_analysis_signal = _has_signal(normalized, HYBRID_ANALYSIS_HINTS)
    rag_guidance_signal = _has_signal(normalized, RAG_GUIDANCE_HINTS)
    out_of_scope_signal = _has_signal(normalized, OUT_OF_SCOPE_HINTS)
    sql_factual_signal = _is_sql_factual_question(normalized, tokens, entities)
    current_data_signal = has_current_data_hint or has_time_hint or bool(
        entities.get("batch_codes") or entities.get("invoice_codes") or entities.get("order_codes")
    )

    if mode == "quick" and is_project_related and not rag_guidance_signal and not hybrid_analysis_signal:
        sql_factual_signal = True
    if out_of_scope_signal and not is_project_related:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.UNSUPPORTED.value,
            confidence=0.95,
            sql_needed=False,
            rag_needed=False,
            reason="Question appears outside cooperative operations and agronomic scope.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=[],
            detected_entities=entities,
            safety_notes=["Return scope-safe guidance and do not invoke broad retrieval."],
        )
    if not is_project_related and not has_operational_trigger:
        if len(tokens) <= 7 and not out_of_scope_signal:
            return RetrievalPlan(
                intent_type=RetrievalIntentType.CLARIFICATION_NEEDED.value,
                confidence=0.82,
                sql_needed=False,
                rag_needed=False,
                reason="Input is conversational but does not identify an operational domain or metric.",
                suggested_sql_domains=[],
                suggested_rag_chunk_types=[],
                detected_entities=entities,
                safety_notes=["Ask for a precise operational target before retrieval."],
            )
        return RetrievalPlan(
            intent_type=RetrievalIntentType.UNSUPPORTED.value,
            confidence=0.9,
            sql_needed=False,
            rag_needed=False,
            reason="Input appears outside cooperative/agricultural/post-harvest operational scope.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=[],
            detected_entities=entities,
            safety_notes=["Return scope-safe guidance and do not invoke broad retrieval."],
        )
    if hybrid_analysis_signal and has_operational_trigger:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.HYBRID.value,
            confidence=0.9,
            sql_needed=True,
            rag_needed=True,
            reason="Question combines exact operational facts with explanatory context.",
            suggested_sql_domains=sql_domains or ["dashboard"],
            suggested_rag_chunk_types=rag_chunk_types or ["recommendation_context", "anomaly_context"],
            detected_entities=entities,
            safety_notes=[],
        )

    if {"efficace", "efficacité", "efficiency"} & tokens and {"membre", "members", "member", "producteur", "farmer"} & tokens:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.HYBRID.value,
            confidence=0.89,
            sql_needed=True,
            rag_needed=True,
            reason="Question asks comparative operational efficiency analysis by member.",
            suggested_sql_domains=sql_domains or ["inputs", "members", "farmer_advances"],
            suggested_rag_chunk_types=rag_chunk_types or ["recommendation_context"],
            detected_entities=entities,
            safety_notes=[],
        )

    cross_module_hybrid_signal = (
        bool({"stock", "stocks"} & tokens)
        and bool({"commande", "commandes", "order", "orders"} & tokens)
        and bool({"risque", "risques", "risk", "anomalie", "anomaly", "faire"} & tokens)
    ) or (
        bool({"prediction", "predictions", "ml"} & tokens)
        and bool({"perte", "pertes", "loss", "losses"} & tokens)
        and bool({"croise", "croiser", "cross", "explique", "expliquer", "compare", "comparer"} & tokens)
    )
    if cross_module_hybrid_signal and has_operational_trigger:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.HYBRID.value,
            confidence=0.91,
            sql_needed=True,
            rag_needed=True,
            reason="Cross-module analysis signal detected (risk/recommendation/prediction vs operational facts).",
            suggested_sql_domains=sql_domains or ["dashboard"],
            suggested_rag_chunk_types=rag_chunk_types or ["recommendation_context", "anomaly_context"],
            detected_entities=entities,
            safety_notes=[],
        )

    if rag_guidance_signal and not current_data_signal and not sql_factual_signal:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.RAG_ONLY.value,
            confidence=0.88,
            sql_needed=False,
            rag_needed=True,
            reason="Question asks for guidance/references rather than current cooperative operational facts.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=rag_chunk_types or ["agronomic_knowledge", "benchmark_reference"],
            detected_entities=entities,
            safety_notes=[],
        )
    if sql_factual_signal and has_operational_trigger:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.SQL_ONLY.value,
            confidence=0.92,
            sql_needed=True,
            rag_needed=False,
            reason="Question asks for exact deterministic operational values.",
            suggested_sql_domains=sql_domains or ["dashboard"],
            suggested_rag_chunk_types=[],
            detected_entities=entities,
            safety_notes=["Prefer live SQL metrics over semantic retrieval."],
        )

    if is_project_related and not has_operational_trigger:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.CLARIFICATION_NEEDED.value,
            confidence=0.84,
            sql_needed=False,
            rag_needed=False,
            reason="Project vocabulary exists but no actionable operational trigger was detected.",
            suggested_sql_domains=[],
            suggested_rag_chunk_types=[],
            detected_entities=entities,
            safety_notes=["Ask for a clearer operational target (stock, lot, loss, risk, recommendation)."],
        )

    if is_project_related and has_operational_trigger:
        return RetrievalPlan(
            intent_type=RetrievalIntentType.HYBRID.value,
            confidence=0.62,
            sql_needed=True,
            rag_needed=True,
            reason="Operational intent detected but query framing is broad; use guarded hybrid synthesis.",
            suggested_sql_domains=sql_domains or ["dashboard"],
            suggested_rag_chunk_types=rag_chunk_types or ["recommendation_context"],
            detected_entities=entities,
            safety_notes=["Low-confidence hybrid route: clarify scope if answer remains broad."],
        )

    return RetrievalPlan(
        intent_type=RetrievalIntentType.CLARIFICATION_NEEDED.value,
        confidence=0.8,
        sql_needed=False,
        rag_needed=False,
        reason="Query is ambiguous and should be clarified before any retrieval route.",
        suggested_sql_domains=[],
        suggested_rag_chunk_types=[],
        detected_entities=entities,
        safety_notes=["Avoid permissive hybrid fallback when intent confidence is low."],
    )


def _is_project_related(lowered: str, tokens: set[str], entities: dict, *, has_operational_trigger: bool = False) -> bool:
    if _has_signal(lowered, DOMAIN_HINTS):
        return True
    if has_operational_trigger:
        return True
    if entities.get("products") or entities.get("stages") or entities.get("batch_codes"):
        return True
    if {"loss", "losses", "perte", "pertes"} & tokens and {"week", "month", "semaine", "mois"} & tokens:
        return True
    return False


def _detect_entities(*, text: str, lowered: str) -> dict:
    products = sorted({value for token, value in PRODUCT_MAP.items() if token in lowered})
    stages = sorted({value for token, value in STAGE_MAP.items() if token in lowered})
    time_hints = sorted({hint for hint in TIME_HINTS if hint in lowered})
    batch_codes = sorted({code.upper() for code in LOT_CODE_PATTERN.findall(text)})
    invoice_codes = sorted({code.upper() for code in INVOICE_CODE_PATTERN.findall(text)})
    order_codes = sorted({code.upper() for code in ORDER_CODE_PATTERN.findall(text)})
    return {
        "products": products,
        "stages": stages,
        "time_hints": time_hints,
        "batch_codes": batch_codes,
        "invoice_codes": invoice_codes,
        "order_codes": order_codes,
    }


def _detect_sql_domains(lowered: str, tokens: set[str]) -> list[str]:
    domains: list[str] = []
    mapping = {
        "stocks": {"stock", "stocks", "inventory", "rupture"},
        "inputs": {"input", "inputs", "collecte", "collected"},
        "batches": {"batch", "batches", "lot", "lots"},
        "process_steps": {"process", "step", "steps", "stage", "stages", "sechage", "drying", "sorting"},
        "losses": {"loss", "losses", "perte", "pertes"},
        "members": {"member", "members", "membre", "membres", "farmer", "farmers"},
        "parcels": {"parcel", "parcels", "parcelle", "parcelles"},
        "pre_harvest": {"preharvest", "pre-harvest", "pre_harvest"},
        "recommendations": {"recommendation", "recommendations"},
        "treasury": {"treasury", "balance", "solde", "tresorerie", "trésorerie", "charge", "charges"},
        "farmer_advances": {"advance", "advances", "avances"},
        "commercial_orders": {"order", "orders", "commande", "commandes"},
        "commercial_invoices": {"invoice", "invoices", "facture", "factures", "unpaid", "pending"},
        "ml_metrics": {"ml", "prediction", "predictions", "model", "anomaly"},
        "dashboard": {"dashboard", "kpi", "overview"},
    }

    for domain, hints in mapping.items():
        if hints & tokens or any(hint in lowered for hint in hints if " " in hint):
            domains.append(domain)
    if not domains:
        domains.append("dashboard")
    return [domain for domain in domains if domain in SUPPORTED_SQL_DOMAINS]


def _detect_rag_chunk_types(lowered: str, tokens: set[str]) -> list[str]:
    benchmark_intent = bool({"benchmark", "reference", "literature", "aphlis", "fao"} & tokens or "best practices" in lowered)
    explicit_operational_intent = bool(
        {"lot", "lots", "batch", "batches", "current", "latest", "status", "this week", "today"} & tokens
    )
    if benchmark_intent and not explicit_operational_intent:
        return ["benchmark_reference", "agronomic_knowledge"]

    chunk_types: list[str] = []
    mapping = {
        "batch_summary": {"batch", "batches", "lot", "lots"},
        "lot_status_summary": {"lot", "lots", "status", "latest lot"},
        "lot_recommendation_summary": {"lot", "lots", "recommendation", "recommendations", "actions"},
        "operational_risk_summary": {"risk", "risky", "anomaly", "loss", "losses"},
        "scoped_loss_summary": {"loss", "losses", "perte", "pertes", "compared", "versus", "vs"},
        "product_stage_summary": {"stage", "drying", "sorting", "sechage", "tri", "mango", "millet", "peanut"},
        "process_step_summary": {"process", "step", "steps", "stage", "drying", "sorting", "sechage", "tri"},
        "recommendation_context": {"recommendation", "recommendations", "should", "actions"},
        "anomaly_context": {"anomaly", "anomalie", "risky", "risk"},
        "agronomic_knowledge": {"best", "practices", "agronomic", "agronomique", "drying", "quality"},
        "benchmark_reference": {"benchmark", "reference", "literature", "typical", "lessons"},
        "parcel_context": {"parcel", "parcels", "parcelle", "parcelles"},
        "pre_harvest_context": {"preharvest", "pre-harvest", "pre_harvest"},
        "commercial_context": {"invoice", "invoices", "facture", "orders", "commandes", "commercial"},
        "ml_evaluation_context": {"ml", "model", "evaluation", "prediction", "predictions"},
    }

    for chunk_type, hints in mapping.items():
        if hints & tokens or any(hint in lowered for hint in hints if " " in hint):
            chunk_types.append(chunk_type)
    if "benchmark_reference" in chunk_types and {
        "loss",
        "losses",
        "perte",
        "pertes",
        "mil",
        "millet",
        "mangue",
        "mango",
        "arachide",
        "peanut",
    } & tokens:
        if "agronomic_knowledge" not in chunk_types:
            chunk_types.append("agronomic_knowledge")
    return [chunk for chunk in chunk_types if chunk in SUPPORTED_RAG_CHUNK_TYPES]


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def _has_signal(text: str, hints: set[str]) -> bool:
    for hint in hints:
        if " " in hint:
            if hint in text:
                return True
        elif re.search(rf"\b{re.escape(hint)}\b", text):
            return True
    return False


def _normalize_message(text: str) -> str:
    compact = " ".join(text.strip().split()).lower()
    stripped = re.sub(r"[^\w\s]", " ", compact, flags=re.UNICODE)
    return " ".join(stripped.split())


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _is_small_talk(normalized: str, tokens: set[str]) -> bool:
    if not normalized:
        return False
    if normalized in SMALL_TALK_EXACT_HINTS:
        return True
    if normalized in {"ca va", "ça va"}:
        return True
    if len(tokens) <= 2 and tokens and tokens.issubset(SMALL_TALK_TOKEN_HINTS):
        return True
    return False


def _needs_clarification(normalized: str, tokens: set[str]) -> bool:
    if not normalized:
        return True
    if normalized in CLARIFICATION_HINTS:
        return True
    if len(tokens) <= 2 and not _has_signal(normalized, DOMAIN_HINTS) and not _has_signal(normalized, OPERATIONAL_TRIGGER_HINTS):
        return True
    return False


def _has_operational_trigger(normalized: str, tokens: set[str], entities: dict) -> bool:
    if _has_signal(normalized, OPERATIONAL_TRIGGER_HINTS):
        return True
    if entities.get("products") or entities.get("stages") or entities.get("batch_codes"):
        return True
    trigger_tokens = {
        "stock",
        "stocks",
        "lot",
        "lots",
        "loss",
        "losses",
        "perte",
        "pertes",
        "risk",
        "risque",
        "risques",
        "recommendation",
        "recommendations",
        "facture",
        "factures",
        "invoice",
        "invoices",
        "commande",
        "commandes",
        "order",
        "orders",
        "treasury",
        "member",
        "members",
        "membre",
        "membres",
        "farmer",
        "farmers",
        "parcel",
        "parcels",
        "parcelle",
        "parcelles",
        "surface",
        "grade",
        "grades",
        "feedback",
        "cout",
        "cost",
        "kg",
    }
    return bool(trigger_tokens & tokens)


def _is_sql_factual_question(normalized: str, tokens: set[str], entities: dict) -> bool:
    if _has_signal(normalized, SQL_FACTUAL_HINTS):
        return True
    if bool(entities.get("invoice_codes") or entities.get("order_codes")):
        return True
    if entities.get("batch_codes") and bool({"status", "statut", "step", "etape", "étape"} & tokens):
        return True
    if "stock" in tokens and bool({"actuel", "current", "disponible", "available", "dispo", "reserve", "réservé", "reste", "restant"} & tokens):
        return True
    if "stock" in tokens and bool(entities.get("products")):
        return True
    if {"collecte", "collection"} & tokens and {"total", "totale", "combien", "par"} & tokens:
        return True
    if {"membre", "membres", "member", "members", "producteur", "producteurs", "farmer", "farmers"} & tokens and {"liste", "list", "detail", "details", "total", "parcelle", "parcelles", "parcel", "parcels", "avance", "avances", "advance", "advances"} & tokens:
        return True
    if {"parcelle", "parcelles", "parcel", "parcels"} & tokens and {"surface", "culture", "statut", "status", "preharvest", "pre-harvest", "prerecolte"} & tokens:
        return True
    if {"commande", "commandes", "order", "orders"} & tokens and {"statut", "status", "open", "pending", "completed", "cancelled", "risque", "risk"} & tokens:
        return True
    if {"facture", "factures", "invoice", "invoices"} & tokens and {"statut", "status", "impayee", "impayees", "unpaid", "overdue", "paid"} & tokens:
        return True
    if {"charge", "charges", "avance", "avances", "advance", "advances", "tresorerie", "balance", "solde", "cost", "cout"} & tokens:
        return True
    if {"prediction", "predictions", "ml", "modele", "model"} & tokens and {"latest", "dernier", "derniere", "derniere", "risque", "risk", "anomaly", "anomalie"} & tokens:
        return True
    if {"prediction", "predictions", "ml"} & tokens and {"derniere", "latest", "recente", "recent"} & tokens:
        return True
    if {"collecte", "collection"} & tokens and {"produit", "product", "produits", "products"} & tokens:
        return True
    if {"lot", "lots", "batch", "batches"} & tokens and {"actif", "actifs", "active"} & tokens:
        return True
    if {"lot", "batch"} & tokens and {"status", "statut"} & tokens:
        return True
    return False
