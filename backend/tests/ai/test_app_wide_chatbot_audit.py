from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings
from app.ai.utils.audit_environment import EnvironmentParityAudit

# Reuse baseline v1 seeding/overrides to keep runtime behavior identical.
from tests.ai.test_chatbot_system_audit import _seed_audit_data, _setup_overrides

settings = Settings()
# Log environment parity for audit
EnvironmentParityAudit.log_parity_header("App-Wide Chatbot Audit", f"Mode={settings.audit_mode}")


REPORT_DIR = Path(__file__).resolve().parents[2] / "app" / "ai" / "reports"
JSON_REPORT_PATH = REPORT_DIR / "app_wide_chatbot_audit.json"
MD_REPORT_PATH = REPORT_DIR / "app_wide_chatbot_audit.md"

FAILURE_CATEGORIES = {
    "ROUTE_FAILURE",
    "SOURCE_MISSING",
    "SOURCE_TYPE_MISMATCH",
    "FRENCH_NON_COMPLIANT",
    "WARNING_MISSING",
    "CONTEXT_LEAKAGE",
    "CONTRADICTION_NOT_EXPLAINED",
    "UNSUPPORTED_RECOMMENDATION",
    "SQL_PRECEDENCE_WEAK",
    "CONTENT_SEMANTIC_ERROR",
}


@dataclass(frozen=True)
class WideAuditCase:
    case_id: str
    module: str
    question: str
    expected_route: str
    accepted_routes: tuple[str, ...]
    expected_source_types: set[str]
    route_type: str
    data_state: str
    scenarios: set[str] = field(default_factory=set)
    sequence_key: str | None = None
    sequence_step: int = 0
    requires_warning: bool = False
    warning_tokens: tuple[str, ...] = ()
    contradiction_warning_expected: bool = False
    contradiction_explained_required: bool = False
    sql_precedence_required: bool = False
    unsupported_reco_prevention_required: bool = False
    leakage_forbidden_terms: tuple[str, ...] = ()


def _cases() -> list[WideAuditCase]:
    # scenario tags: list, detail, count_summary, filter, ambiguous, empty_missing, high_risk, low_risk, multi_turn
    return [
        # members/farmers
        WideAuditCase("mbr-01", "members/farmers", "Liste les membres de la coopérative.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"list"}),
        WideAuditCase("mbr-02", "members/farmers", "Combien de membres sont enregistrés ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"count_summary"}),
        WideAuditCase("mbr-03", "members/farmers", "Donne les détails du membre Mamadou Ba.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"detail"}),
        WideAuditCase("mbr-04", "members/farmers", "Membres de la filière mangue.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"filter"}),
        WideAuditCase("mbr-05", "members/farmers", "Qui sont les meilleurs ?", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, "SQL_ONLY", "ambiguous", {"ambiguous"}),
        WideAuditCase("mbr-06", "members/farmers", "Donne les infos du membre XYZ-ABSENT.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "missing", {"empty_missing"}, requires_warning=True),

        # parcels/cultures + pre-harvest
        WideAuditCase("par-01", "parcels/cultures", "Liste les parcelles enregistrées.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"list"}),
        WideAuditCase("par-02", "parcels/cultures", "Détaille la parcelle PARCELLE-MB-01.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"detail"}),
        WideAuditCase("par-03", "parcels/cultures", "Combien de parcelles suivies ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"count_summary"}),
        WideAuditCase("par-04", "parcels/cultures", "Parcelles de la culture arachide.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"filter"}),
        WideAuditCase("par-05", "pre-harvest steps", "Quelles étapes pré-récolte sont en attente ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"list"}),
        WideAuditCase("par-06", "pre-harvest steps", "Quel est le résumé pré-récolte des parcelles ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"count_summary"}),

        # collections/inputs
        WideAuditCase("col-01", "collections/inputs", "Quelle quantité a été collectée aujourd’hui ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"count_summary"}),
        WideAuditCase("col-02", "collections/inputs", "Quels producteurs ont livré le plus cette semaine ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"list", "filter"}),
        WideAuditCase("col-03", "collections/inputs", "Répartition des collectes par grade.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"summary"}),
        WideAuditCase("col-04", "collections/inputs", "Collectes du produit mangue sur 2020-01-01 à 2020-01-02.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "missing", {"filter", "empty_missing"}, requires_warning=True),
        WideAuditCase("col-05", "collections/inputs", "Montre-moi les collectes importantes.", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, "SQL_ONLY", "ambiguous", {"ambiguous"}),

        # stocks
        WideAuditCase("stk-01", "stocks", "Quel est le stock actuel ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"list"}),
        WideAuditCase("stk-02", "stocks", "Stock de mangue actuellement.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"detail", "filter"}),
        WideAuditCase("stk-03", "stocks", "Quels produits sont sous le seuil critique ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "high_risk", {"high_risk"}),
        WideAuditCase("stk-04", "stocks", "Stock du produit cacao.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "missing", {"empty_missing"}, requires_warning=True),

        # lots/batches + process + material balance/loss/efficiency
        WideAuditCase("lot-01", "lots/batches", "Quels lots sont en cours ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"list"}),
        WideAuditCase("lot-02", "lots/batches", "Analyse le lot MANG-004.", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_ML"), {"sql"}, "SQL_ONLY", "high_risk", {"detail", "high_risk"}),
        WideAuditCase("lot-03", "lots/batches", "Quel lot a le plus de pertes ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "high_risk", {"summary", "high_risk"}),
        WideAuditCase("proc-01", "post-harvest process steps", "Quelle étape post-récolte pose le plus de problème ?", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, "SQL_ONLY", "high_risk", {"summary", "high_risk"}),
        WideAuditCase("proc-02", "post-harvest process steps", "Compare les pertes entre séchage et tri.", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, "SQL_ONLY", "normal", {"filter", "summary"}),
        WideAuditCase("mat-01", "material balance", "Explique le bilan matière du lot MANG-004.", "HYBRID_SQL_RAG", ("HYBRID_SQL_RAG", "SQL_ONLY", "HYBRID_SQL_ML"), {"sql", "rag"}, "HYBRID_SQL_RAG", "normal", {"detail"}, sql_precedence_required=True),
        WideAuditCase("eff-01", "efficiency analysis", "Quels lots ont une efficacité faible ?", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, "SQL_ONLY", "high_risk", {"summary", "high_risk"}),

        # ML risk/anomaly and contradiction interpretation
        WideAuditCase("ml-01", "ML risk/anomaly insights", "Avons-nous des lots à risque aujourd’hui ?", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY", "SQL_ONLY"), {"ml"}, "HYBRID_SQL_ML", "high_risk", {"high_risk"}, contradiction_warning_expected=True, contradiction_explained_required=True),
        WideAuditCase("ml-02", "ML risk/anomaly insights", "Y a-t-il des anomalies dans les pertes ?", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY"), {"ml"}, "HYBRID_SQL_ML", "high_risk", {"high_risk"}, contradiction_warning_expected=True, contradiction_explained_required=True),
        WideAuditCase("ml-03", "ML risk/anomaly insights", "Quels sont les lots avec risque élevé ?", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY"), {"ml"}, "HYBRID_SQL_ML", "high_risk", {"list", "high_risk"}, contradiction_warning_expected=True, contradiction_explained_required=True),
        WideAuditCase("ml-04", "ML risk/anomaly insights", "Donne un signal de risque sur lot inconnu MANG-999.", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY", "SQL_ONLY"), {"ml"}, "HYBRID_SQL_ML", "missing", {"empty_missing"}, requires_warning=True),
        WideAuditCase("ml-05", "loss analysis", "Quel est le niveau de pertes observé sur MANG-005 ?", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_ML"), {"sql"}, "SQL_ONLY", "low_risk", {"detail", "low_risk"}),

        # RAG explanations / best practices
        WideAuditCase("rag-01", "RAG explanations/best practices", "Comment réduire les pertes pendant le séchage de la mangue ?", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), {"rag"}, "RAG_ONLY", "normal", {"list"}),
        WideAuditCase("rag-02", "RAG explanations/best practices", "Quelles sont les bonnes pratiques pour le tri des mangues ?", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), {"rag"}, "RAG_ONLY", "normal", {"detail"}),
        WideAuditCase("rag-03", "RAG explanations/best practices", "Comment améliorer l’emballage ?", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), {"rag"}, "RAG_ONLY", "normal", {"summary"}),
        WideAuditCase("rag-04", "RAG explanations/best practices", "Explique pourquoi la perte est haute sur MANG-004.", "HYBRID_SQL_RAG", ("HYBRID_SQL_RAG", "RAG_ONLY", "SQL_ONLY"), {"rag"}, "HYBRID_SQL_RAG", "high_risk", {"high_risk"}, sql_precedence_required=True),

        # Recommendations (including prevention of unsupported)
        WideAuditCase("rec-01", "AI recommendations", "Donne-moi les recommandations IA pour le lot MANG-004.", "HYBRID_FULL", ("HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION", "RECOMMENDATION_ONLY"), {"recommendation"}, "HYBRID_FULL", "high_risk", {"detail", "high_risk"}),
        WideAuditCase("rec-02", "AI recommendations", "Que faire pour réduire les pertes au séchage ?", "HYBRID_RAG_RECOMMENDATION", ("HYBRID_RAG_RECOMMENDATION", "HYBRID_FULL", "RECOMMENDATION_ONLY"), {"recommendation"}, "HYBRID_RAG_RECOMMENDATION", "normal", {"summary"}),
        WideAuditCase("rec-03", "AI recommendations", "Quelles actions prioritaires devons-nous faire aujourd’hui ?", "RECOMMENDATION_ONLY", ("RECOMMENDATION_ONLY", "HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION"), {"recommendation"}, "HYBRID_FULL", "missing", {"empty_missing", "ambiguous"}, unsupported_reco_prevention_required=True),

        # memory/context
        WideAuditCase("mem-01", "memory/context", "Liste les membres de notre coopérative.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"multi_turn", "list"}, sequence_key="A", sequence_step=1),
        WideAuditCase("mem-02", "memory/context", "Quels lots sont à risque ?", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY", "SQL_ONLY"), {"ml"}, "HYBRID_SQL_ML", "high_risk", {"multi_turn", "high_risk"}, sequence_key="A", sequence_step=2, leakage_forbidden_terms=("membre", "producteur", "mamadou", "awa", "ibrahima"), contradiction_warning_expected=True, contradiction_explained_required=True),
        WideAuditCase("mem-03", "memory/context", "Quels lots sont à risque ?", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY", "SQL_ONLY"), {"ml"}, "HYBRID_SQL_ML", "high_risk", {"multi_turn", "high_risk"}, sequence_key="B", sequence_step=1, contradiction_warning_expected=True, contradiction_explained_required=True),
        WideAuditCase("mem-04", "memory/context", "Liste les membres.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"multi_turn", "list"}, sequence_key="B", sequence_step=2, leakage_forbidden_terms=("risque", "anomal", "lot", "séchage", "tri")),

        # additional route-type focused checks
        WideAuditCase("rt-01", "route-type", "Explique les pertes du lot MANG-004 et donne les causes.", "HYBRID_SQL_RAG", ("HYBRID_SQL_RAG", "SQL_ONLY"), {"sql", "rag"}, "HYBRID_SQL_RAG", "high_risk", {"summary"}, sql_precedence_required=True),
        WideAuditCase("rt-02", "route-type", "Donne uniquement le stock actuel, sans explication.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, "SQL_ONLY", "normal", {"summary"}),
    ]


def _post_agent(client: TestClient, *, question: str, conversation_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"message": question, "language": "fr"}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = client.post("/chat/agent", json=body)
    assert response.status_code == 200
    return response.json()


def _is_french(text: str) -> bool:
    lowered = f" {str(text or '').lower()} "
    french = sum(
        1
        for token in (
            " le ",
            " la ",
            " les ",
            " des ",
            " une ",
            " est ",
            " données",
            " pertes",
            " risque",
            " membres",
            " parcelles",
            " stocks",
            " lots",
            " pré-récolte",
            " recommandations",
        )
        if token in lowered
    )
    english = sum(1 for token in (" the ", " what ", " which ", " today ", " risk level") if token in lowered)
    return french >= max(1, english)


def _product_aliases(label: str) -> set[str]:
    raw = str(label or "").strip().lower()
    aliases = {raw}
    mapping = {
        "mango": {"mango", "mangue"},
        "mangue": {"mango", "mangue"},
        "peanut": {"peanut", "arachide"},
        "arachide": {"peanut", "arachide"},
        "millet": {"millet", "mil"},
        "mil": {"millet", "mil"},
    }
    aliases.update(mapping.get(raw, set()))
    return {item for item in aliases if item}


def _route_status(expected: str, actual: str, accepted: tuple[str, ...]) -> tuple[str, bool]:
    if actual == expected:
        return "exact_match", True
    if actual in accepted:
        return "compatible_route", True
    return "route_failure", False


def _answer_has_sql_fact_tone(answer: str) -> bool:
    principal = ""
    lines = [line.strip() for line in str(answer or "").splitlines()]
    if "1. Résultat principal" in lines:
        i = lines.index("1. Résultat principal")
        for line in lines[i + 1 :]:
            if line:
                principal = line.lower()
                break
    else:
        principal = str(answer or "").lower()
    sql_markers = ("stock", "lot", "kg", "perte", "efficacité", "étape", "parcelle")
    return any(marker in principal for marker in sql_markers)


def _contradiction_explained(answer: str) -> bool:
    lowered = str(answer or "").lower()
    return "contradiction sql/ml" in lowered and "priorité aux mesures sql" in lowered


def _is_cautious_reco(answer: str, metadata: dict[str, Any]) -> bool:
    lowered = str(answer or "").lower()
    if "preuves actuelles sont insuffisantes" in lowered or "insuffisantes pour recommander" in lowered:
        return True
    debug = metadata.get("agent_debug") or {}
    reco_data = ((debug.get("RecommendationAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    return bool(reco_data.get("insufficient_evidence"))


def _sql_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    debug = metadata.get("agent_debug") or {}
    sql_data = ((debug.get("SQLAnalyticsAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    return sql_data if isinstance(sql_data, dict) else {}


def _evaluate_case(case: WideAuditCase, payload: dict[str, Any], previous_case: WideAuditCase | None) -> dict[str, Any]:
    route = str(payload.get("route") or "")
    answer = str(payload.get("answer") or "")
    sources = [item for item in payload.get("sources", []) if isinstance(item, dict)]
    source_types = {str(item.get("type") or "").lower() for item in sources if item.get("type")}
    metadata = payload.get("metadata") or {}
    warnings = [str(w) for w in payload.get("warnings", [])]
    warning_codes = [str(w) for w in metadata.get("warning_codes", [])]
    sql_data = _sql_payload(metadata)

    route_match_status, route_ok = _route_status(case.expected_route, route, case.accepted_routes)

    failures: list[str] = []
    if not route_ok:
        failures.append("ROUTE_FAILURE")

    if case.expected_source_types and not case.expected_source_types.issubset(source_types):
        if source_types:
            failures.append("SOURCE_TYPE_MISMATCH")
        else:
            failures.append("SOURCE_MISSING")

    if not sources:
        failures.append("SOURCE_MISSING")

    french_ok = _is_french(answer)
    if not french_ok:
        failures.append("FRENCH_NON_COMPLIANT")

    if case.requires_warning and not (warnings or warning_codes):
        failures.append("WARNING_MISSING")

    if case.warning_tokens:
        corpus = " ".join([answer.lower(), " ".join(w.lower() for w in warnings), " ".join(w.lower() for w in warning_codes)])
        if not any(token.lower() in corpus for token in case.warning_tokens):
            failures.append("WARNING_MISSING")

    if case.contradiction_warning_expected and "SQL_ML_CONTRADICTION" not in warning_codes:
        failures.append("WARNING_MISSING")

    if case.contradiction_explained_required and "SQL_ML_CONTRADICTION" in warning_codes and not _contradiction_explained(answer):
        failures.append("CONTRADICTION_NOT_EXPLAINED")

    if case.sql_precedence_required and not _answer_has_sql_fact_tone(answer):
        failures.append("SQL_PRECEDENCE_WEAK")

    if case.unsupported_reco_prevention_required and not _is_cautious_reco(answer, metadata):
        failures.append("UNSUPPORTED_RECOMMENDATION")

    # Semantic answer validations (business content correctness).
    if case.module == "members/farmers":
        members = sql_data.get("members_list") if isinstance(sql_data, dict) else None
        if isinstance(members, list):
            if members:
                lowered = answer.lower()
                if not any(str(member.get("member_name", "")).lower() in lowered for member in members[:3]):
                    failures.append("CONTENT_SEMANTIC_ERROR")
            else:
                if "aucun membre" not in answer.lower():
                    failures.append("CONTENT_SEMANTIC_ERROR")

    if case.module == "stocks" and "list" in case.scenarios:
        stocks = sql_data.get("current_stock") if isinstance(sql_data, dict) else None
        if isinstance(stocks, list) and len(stocks) > 1:
            lowered = answer.lower()
            mentioned = 0
            for stock in stocks:
                variants = _product_aliases(stock.get("product", ""))
                if any(token in lowered for token in variants):
                    mentioned += 1
            if mentioned < 2:
                failures.append("CONTENT_SEMANTIC_ERROR")

    if case.case_id == "stk-02":
        stocks = sql_data.get("current_stock") if isinstance(sql_data, dict) else None
        if isinstance(stocks, list) and stocks:
            if any(str(item.get("product", "")).lower() not in {"mango", "mangue"} for item in stocks):
                failures.append("CONTENT_SEMANTIC_ERROR")

    if case.case_id in {"ml-03", "mem-02", "mem-03"}:
        high_risk_lots = sql_data.get("high_risk_lots") if isinstance(sql_data, dict) else None
        if isinstance(high_risk_lots, list) and len(high_risk_lots) > 1:
            lowered = answer.lower()
            mentions = 0
            for item in high_risk_lots[:6]:
                if str(item.get("batch_ref", "")).lower() in lowered:
                    mentions += 1
            if mentions < 2:
                failures.append("CONTENT_SEMANTIC_ERROR")

    leakage = False
    lowered_answer = answer.lower()
    if case.leakage_forbidden_terms and any(token.lower() in lowered_answer for token in case.leakage_forbidden_terms):
        leakage = True
    if case.sequence_step == 2 and previous_case is not None and case.sequence_key == "B":
        detected_entities = metadata.get("detected_entities") or {}
        if detected_entities.get("batch_ref"):
            leakage = True
    if leakage:
        failures.append("CONTEXT_LEAKAGE")

    failures = sorted(set(item for item in failures if item in FAILURE_CATEGORIES))

    if not failures:
        status = "PASS"
    elif len(failures) <= 2:
        status = "PARTIAL"
    else:
        status = "FAIL"

    return {
        "case_id": case.case_id,
        "module": case.module,
        "question": case.question,
        "route_type": case.route_type,
        "data_state": case.data_state,
        "scenarios": sorted(case.scenarios),
        "expected_route": case.expected_route,
        "actual_route": route,
        "route_match_status": route_match_status,
        "route_compatible": route_match_status == "compatible_route",
        "source_types": sorted(source_types),
        "expected_source_types": sorted(case.expected_source_types),
        "warnings": warnings,
        "warning_codes": warning_codes,
        "french_compliance": "yes" if french_ok else "no",
        "context_leakage": "yes" if leakage else "no",
        "status": status,
        "failure_categories": failures,
        "answer_preview": " ".join(answer.split())[:260],
    }


def _coverage_matrix(cases: list[WideAuditCase], results: list[dict[str, Any]]) -> dict[str, Any]:
    required_scenarios = [
        "list",
        "detail",
        "count_summary",
        "filter",
        "ambiguous",
        "empty_missing",
        "high_risk",
        "low_risk",
        "multi_turn",
    ]

    module_to_cases: dict[str, list[WideAuditCase]] = defaultdict(list)
    for case in cases:
        module_to_cases[case.module].append(case)

    result_by_id = {row["case_id"]: row for row in results}

    matrix: dict[str, Any] = {}
    for module, module_cases in sorted(module_to_cases.items(), key=lambda kv: kv[0]):
        row: dict[str, Any] = {}
        for scenario in required_scenarios:
            tagged = [c for c in module_cases if scenario in c.scenarios]
            if not tagged:
                row[scenario] = "N/A"
                continue
            statuses = [result_by_id[c.case_id]["status"] for c in tagged if c.case_id in result_by_id]
            if statuses and all(status == "PASS" for status in statuses):
                row[scenario] = "PASS"
            elif statuses and any(status in {"PASS", "PARTIAL"} for status in statuses):
                row[scenario] = "PARTIAL"
            else:
                row[scenario] = "FAIL"
        matrix[module] = row
    return matrix


def _summary(results: list[dict[str, Any]], matrix: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(row["status"] for row in results)
    total = len(results)

    by_module: dict[str, Counter] = defaultdict(Counter)
    by_route: dict[str, Counter] = defaultdict(Counter)
    by_state: dict[str, Counter] = defaultdict(Counter)
    failure_counter = Counter()
    route_status_counter = Counter()

    explained_contradictions = []
    unresolved_contradictions = []

    for row in results:
        by_module[row["module"]][row["status"]] += 1
        by_route[row["route_type"]][row["status"]] += 1
        by_state[row["data_state"]][row["status"]] += 1
        route_status_counter[row["route_match_status"]] += 1
        failure_counter.update(row["failure_categories"])

        if "SQL_ML_CONTRADICTION" in row["warning_codes"]:
            if "CONTRADICTION_NOT_EXPLAINED" in row["failure_categories"]:
                unresolved_contradictions.append({"case_id": row["case_id"], "module": row["module"]})
            else:
                explained_contradictions.append({"case_id": row["case_id"], "module": row["module"]})

    uncovered_areas = []
    for module, row in matrix.items():
        weak = [scenario for scenario, status in row.items() if status in {"FAIL", "N/A"}]
        if weak:
            uncovered_areas.append({"module": module, "uncovered_or_weak": weak})

    root_causes = []
    root_map = {
        "ROUTE_FAILURE": "Route inattendue pour la formulation de la question.",
        "SOURCE_MISSING": "Sources absentes dans la réponse finale.",
        "SOURCE_TYPE_MISMATCH": "Types de source non alignés sur le module/question.",
        "FRENCH_NON_COMPLIANT": "Réponse partiellement non-française.",
        "WARNING_MISSING": "Avertissement attendu absent.",
        "CONTEXT_LEAKAGE": "Contexte d’un tour précédent injecté hors sujet.",
        "CONTRADICTION_NOT_EXPLAINED": "Contradiction SQL/ML non explicitée.",
        "UNSUPPORTED_RECOMMENDATION": "Recommandation prioritaire sans base de preuve suffisante.",
        "SQL_PRECEDENCE_WEAK": "Les faits SQL n’apparaissent pas clairement prioritaires.",
    }
    for cat, n in failure_counter.most_common(8):
        root_causes.append({"failure_category": cat, "count": n, "suspected_root_cause": root_map.get(cat, cat)})

    return {
        "totals": {
            "PASS": counts.get("PASS", 0),
            "PARTIAL": counts.get("PARTIAL", 0),
            "FAIL": counts.get("FAIL", 0),
            "TOTAL": total,
        },
        "route_status": dict(route_status_counter),
        "results_by_module": {
            module: {"PASS": c.get("PASS", 0), "PARTIAL": c.get("PARTIAL", 0), "FAIL": c.get("FAIL", 0)}
            for module, c in sorted(by_module.items(), key=lambda kv: kv[0])
        },
        "results_by_route_type": {
            route: {"PASS": c.get("PASS", 0), "PARTIAL": c.get("PARTIAL", 0), "FAIL": c.get("FAIL", 0)}
            for route, c in sorted(by_route.items(), key=lambda kv: kv[0])
        },
        "results_by_data_state": {
            state: {"PASS": c.get("PASS", 0), "PARTIAL": c.get("PARTIAL", 0), "FAIL": c.get("FAIL", 0)}
            for state, c in sorted(by_state.items(), key=lambda kv: kv[0])
        },
        "failure_categories": [{"category": k, "count": v} for k, v in failure_counter.most_common()],
        "explained_contradiction_warnings": explained_contradictions,
        "unresolved_contradiction_warnings": unresolved_contradictions,
        "uncovered_areas": uncovered_areas,
        "suspected_root_causes": root_causes,
    }


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines: list[str] = []
    lines.append("# App-wide Chatbot Audit")
    lines.append("")
    lines.append("## Executive Summary")
    t = summary["totals"]
    lines.append(f"- Total: {t['TOTAL']} | PASS={t['PASS']} | PARTIAL={t['PARTIAL']} | FAIL={t['FAIL']}")
    rs = summary["route_status"]
    lines.append(f"- Route status: exact={rs.get('exact_match',0)} | compatible={rs.get('compatible_route',0)} | failure={rs.get('route_failure',0)}")
    lines.append(f"- SQL/ML contradiction warnings: explained={len(summary['explained_contradiction_warnings'])} | unresolved={len(summary['unresolved_contradiction_warnings'])}")
    lines.append("")

    lines.append("## Coverage Matrix")
    scenarios = ["list", "detail", "count_summary", "filter", "ambiguous", "empty_missing", "high_risk", "low_risk", "multi_turn"]
    header = "| Module | " + " | ".join(scenarios) + " |"
    lines.append(header)
    lines.append("|" + " --- |" * (len(scenarios) + 1))
    for module, row in payload["coverage_matrix"].items():
        cells = [row.get(sc, "N/A") for sc in scenarios]
        lines.append("| " + module + " | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Results By Module")
    lines.append("| Module | PASS | PARTIAL | FAIL |")
    lines.append("| --- | ---: | ---: | ---: |")
    for module, stats in summary["results_by_module"].items():
        lines.append(f"| {module} | {stats['PASS']} | {stats['PARTIAL']} | {stats['FAIL']} |")
    lines.append("")

    lines.append("## Results By Route Type")
    lines.append("| Route type | PASS | PARTIAL | FAIL |")
    lines.append("| --- | ---: | ---: | ---: |")
    for route, stats in summary["results_by_route_type"].items():
        lines.append(f"| {route} | {stats['PASS']} | {stats['PARTIAL']} | {stats['FAIL']} |")
    lines.append("")

    lines.append("## Results By Data State")
    lines.append("| Data state | PASS | PARTIAL | FAIL |")
    lines.append("| --- | ---: | ---: | ---: |")
    for state, stats in summary["results_by_data_state"].items():
        lines.append(f"| {state} | {stats['PASS']} | {stats['PARTIAL']} | {stats['FAIL']} |")
    lines.append("")

    lines.append("## Failure Categories")
    if summary["failure_categories"]:
        for item in summary["failure_categories"]:
            lines.append(f"- {item['category']}: {item['count']}")
    else:
        lines.append("- Aucun échec catégorisé.")
    lines.append("")

    lines.append("## Uncovered Areas")
    if summary["uncovered_areas"]:
        for item in summary["uncovered_areas"]:
            lines.append(f"- {item['module']}: {', '.join(item['uncovered_or_weak'])}")
    else:
        lines.append("- Couverture complète des scénarios attendus.")
    lines.append("")

    lines.append("## Suspected Root Causes")
    if summary["suspected_root_causes"]:
        for item in summary["suspected_root_causes"]:
            lines.append(f"- {item['failure_category']} ({item['count']}): {item['suspected_root_cause']}")
    else:
        lines.append("- Aucune faiblesse détectée.")
    lines.append("")

    lines.append("## Exact Next Recommended Fix")
    lines.append("- Corriger en priorité la conformité linguistique des réponses stock SQL (cas partiels NOT_FRENCH), puis affiner l’extraction d’entités dans les cas ML ambigus restants.")
    lines.append("")

    lines.append("## Detailed Cases")
    lines.append("| Case | Module | Route exp/act | Route status | Data state | Status | Failures |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in payload["cases"]:
        fails = ",".join(row["failure_categories"]) if row["failure_categories"] else "-"
        lines.append(
            f"| {row['case_id']} | {row['module']} | {row['expected_route']} / {row['actual_route']} | {row['route_match_status']} | {row['data_state']} | {row['status']} | {fails} |"
        )

    return "\n".join(lines)


def _write_reports(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_REPORT_PATH.write_text(payload["markdown_report"], encoding="utf-8")


def test_app_wide_chatbot_audit_report(db_session, monkeypatch):
    monkeypatch.setenv("AI_AUDIT_DEBUG", "1")
    _setup_overrides(db_session)
    _seed_audit_data(db_session)

    cases = _cases()
    client = TestClient(app)

    sequence_conversation_ids: dict[str, str] = {}
    previous_by_sequence: dict[str, WideAuditCase] = {}
    results: list[dict[str, Any]] = []

    try:
        for case in cases:
            conversation_id = None
            if case.sequence_key and case.sequence_step > 1:
                conversation_id = sequence_conversation_ids.get(case.sequence_key)

            payload = _post_agent(client, question=case.question, conversation_id=conversation_id)
            metadata = payload.get("metadata") or {}
            if case.sequence_key and case.sequence_step == 1 and metadata.get("conversation_id"):
                sequence_conversation_ids[case.sequence_key] = str(metadata.get("conversation_id"))

            previous_case = previous_by_sequence.get(case.sequence_key) if case.sequence_key else None
            results.append(_evaluate_case(case, payload, previous_case))
            if case.sequence_key:
                previous_by_sequence[case.sequence_key] = case
    finally:
        app.dependency_overrides.clear()
        os.environ.pop("AI_AUDIT_DEBUG", None)

    matrix = _coverage_matrix(cases, results)
    summary = _summary(results, matrix)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_name": "app_wide_chatbot_audit",
        "baseline_reference": "chatbot_system_audit_baseline_v1",
        "total_test_count": len(results),
        "coverage_matrix": matrix,
        "summary": summary,
        "cases": results,
    }
    payload["markdown_report"] = _markdown(payload)

    _write_reports(payload)

    assert len(results) == len(cases)
    assert JSON_REPORT_PATH.exists()
    assert MD_REPORT_PATH.exists()
