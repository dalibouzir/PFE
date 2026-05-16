from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from app.ai.schemas.agent_schemas import AgentResult, AgentRoute


def _first_or_none(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str) and value.strip():
        return value
    return None


@dataclass
class AnswerPlan:
    module: str
    intent: str
    answer_type: str
    required_sources: list[str]
    required_fields: list[str]
    completeness_rules: list[str]
    output_blocks_needed: list[str]
    domain: str = "global"
    operation: str = "generic"
    metric: str = ""
    filters: dict[str, Any] | None = None
    product: str | None = None
    status: str | None = None
    grade: str | None = None
    date_range: str | None = None
    period: str | None = None
    limit: int | None = None
    required_answer_fields: list[str] | None = None
    allowed_sources: list[str] | None = None
    chart_target: str | None = None
    chart_metric: str | None = None
    chart_group_by: str | None = None
    chart_series: list[str] | None = None


@dataclass
class EvidencePack:
    question: str
    plan: AnswerPlan
    route: AgentRoute
    sql: dict[str, Any]
    rag: dict[str, Any]
    ml: dict[str, Any]
    recommendations: dict[str, Any]
    warnings: list[str]
    confidence: float
    module_registry: dict[str, dict[str, Any]]


@dataclass
class EvidenceVerification:
    ok: bool
    issues: list[str]


def plan_answer(*, query: str, detected_entities: dict[str, Any], route: AgentRoute) -> AnswerPlan:
    lowered = str(query or "").lower()
    normalized = _normalize_for_match(query)
    module = str((detected_entities or {}).get("module") or "global")
    has_stock_intent = any(token in lowered for token in ("stock", "kg", "disponible"))
    has_chart_intent = any(
        token in lowered
        for token in (
            "graphique",
            "graphe",
            "chart",
            "diagramme",
            "visualise",
            "affiche un graphique",
            "montre-moi un graphique",
            "montre moi un graphique",
        )
    )
    has_visual_request = has_chart_intent or any(token in lowered for token in ("affiche", "visualise", "visualiser", "montre", "montrez"))
    has_stage_loss_intent = any(token in lowered for token in ("perte", "pertes", "loss")) and any(
        token in lowered for token in ("étape", "etape", "transformation", "process", "processus", "stage")
    )
    has_lot_loss_intent = any(token in lowered for token in ("lot", "lots", "batch", "batches")) and any(
        token in lowered for token in ("perte", "pertes", "loss", "plus élev", "plus eleve", "top")
    )
    has_reco_risk_chart_intent = has_chart_intent and any(
        token in lowered
        for token in ("recommand", "actions", "action", "priorit", "risque", "risk", "niveau de risque")
    )
    has_best_practice_intent = any(
        token in lowered
        for token in ("bonnes pratiques", "meilleures pratiques", "best practices", "références", "references", "tri", "séchage", "sechage")
    )

    chart_target = None
    chart_metric = None
    chart_group_by = None
    chart_series: list[str] = []
    chart_limit = _extract_chart_limit(normalized)

    has_stock_multi_intent = has_chart_intent and has_stock_intent and any(
        token in lowered for token in ("total", "reserv", "réserv", "disponible net", "compar")
    )
    has_product_loss_chart_intent = has_chart_intent and any(token in lowered for token in ("perte", "pertes", "loss")) and any(
        token in lowered for token in ("par produit", "by product", "produit")
    )
    has_low_eff_lots_chart_intent = has_chart_intent and any(token in lowered for token in ("lot", "lots", "batch")) and any(
        token in lowered for token in ("moins efficaces", "moins efficient", "faible efficac", "lowest efficiency")
    )
    has_lot_critical_chart_intent = has_chart_intent and any(token in lowered for token in ("lot", "lots", "batch")) and any(
        token in lowered for token in ("critique", "top", "plus critiques", "plus critique")
    ) and any(token in lowered for token in ("perte", "efficac", "signal ml", "ml"))
    has_ml_anomaly_lot_chart_intent = has_visual_request and any(
        token in lowered for token in ("anomaly_score", "anomal", "ml")
    ) and any(token in lowered for token in ("lot", "lots", "batch"))

    if has_reco_risk_chart_intent:
        answer_type = "chart_recommendation_risk"
        intent = "chart_recommendations_by_risk"
        chart_target, chart_metric, chart_group_by = "recommendations", "count", "risk_level"
        chart_series = ["recommendation_count"]
    elif has_stock_multi_intent:
        answer_type = "chart_stock_multi"
        intent = "chart_stock_total_reserved_available"
        chart_target, chart_metric, chart_group_by = "stocks", "stock", "product"
        chart_series = ["total_stock_kg", "reserved_in_lots_kg", "available_stock_kg"]
    elif has_lot_critical_chart_intent:
        answer_type = "chart_lot_critical"
        intent = "chart_top_critical_lots"
        chart_target, chart_metric, chart_group_by = "lots", "criticality", "lot"
        chart_series = ["loss_pct", "efficiency_pct", "ml_signal"]
    elif has_chart_intent and has_stock_intent:
        answer_type = "chart_stock"
        intent = "chart_stock_by_product"
        chart_target, chart_metric, chart_group_by = "stocks", "available", "product"
        chart_series = ["available_stock_kg"]
    elif has_product_loss_chart_intent:
        answer_type = "chart_product_loss"
        intent = "chart_loss_by_product"
        chart_target, chart_metric, chart_group_by = "products", "loss_pct", "product"
        chart_series = ["avg_loss_pct"]
    elif has_chart_intent and has_stage_loss_intent:
        answer_type = "chart_stage_loss"
        intent = "chart_avg_stage_loss"
        chart_target, chart_metric, chart_group_by = "stages", "loss_pct", "stage"
        chart_series = ["avg_loss_pct"]
    elif has_low_eff_lots_chart_intent:
        answer_type = "chart_low_efficiency_lots"
        intent = "chart_low_efficiency_lots"
        chart_target, chart_metric, chart_group_by = "lots", "efficiency", "lot"
        chart_series = ["efficiency_pct", "loss_pct"]
    elif has_ml_anomaly_lot_chart_intent:
        answer_type = "chart_ml_anomaly_lots"
        intent = "chart_ml_anomaly_by_lot"
        chart_target, chart_metric, chart_group_by = "ml", "anomaly_score", "lot"
        chart_series = ["anomaly_score"]
    elif has_chart_intent and has_lot_loss_intent:
        answer_type = "chart_lot_loss"
        intent = "chart_top_lot_losses"
        chart_target, chart_metric, chart_group_by = "lots", "loss_pct", "lot"
        chart_series = ["loss_pct"]
    elif route in {AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_FULL} and has_stock_intent and has_best_practice_intent:
        answer_type = "multi_intent_sql_rag"
        intent = "stock_and_best_practices"
    elif any(token in lowered for token in ("classe", "top", "plus de kg", "plus de valeur", "ranking")):
        answer_type = "ranking"
        intent = "rank_entities"
    elif any(token in lowered for token in ("compare", "compar", "versus", "vs")):
        answer_type = "comparison"
        intent = "compare_metrics"
    elif route in {AgentRoute.RAG_ONLY}:
        answer_type = "explanation"
        intent = "explain_best_practices"
    elif route in {AgentRoute.HYBRID_SQL_ML, AgentRoute.ML_ONLY}:
        answer_type = "risk_list"
        intent = "risk_analysis"
    elif route in {AgentRoute.RECOMMENDATION_ONLY, AgentRoute.HYBRID_RAG_RECOMMENDATION}:
        answer_type = "recommendation"
        intent = "recommend_actions"
    elif route in {AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_FULL} and any(
        token in lowered for token in ("explique", "comment", "pourquoi", "causes")
    ):
        answer_type = "hybrid_analysis"
        intent = "analyze_with_explanation"
    elif "stock" in lowered:
        answer_type = "list"
        intent = "list_stock"
    elif any(token in lowered for token in ("quantité", "quantite", "combien", "total", "chiffre d'affaires", "chiffre d’affaires")):
        answer_type = "numeric_total"
        intent = "compute_total"
    elif any(token in lowered for token in ("liste", "lister", "quels", "quelles")):
        answer_type = "list"
        intent = "list_items"
    else:
        answer_type = "detail"
        intent = "describe_item"

    required_sources: list[str] = []
    if route in {AgentRoute.SQL_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL}:
        required_sources.append("SQL")
    if route in {AgentRoute.RAG_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL}:
        required_sources.append("RAG")
    if route in {AgentRoute.ML_ONLY, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL}:
        required_sources.append("ML")
    if route in {AgentRoute.RECOMMENDATION_ONLY, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL}:
        required_sources.append("RECOMMENDATION")

    required_fields: list[str] = []
    if answer_type in {"list", "ranking", "comparison", "risk_list", "multi_intent_sql_rag", "chart_stock", "chart_stock_multi", "chart_stage_loss", "chart_lot_loss", "chart_lot_critical", "chart_product_loss", "chart_low_efficiency_lots", "chart_ml_anomaly_lots", "chart_recommendation_risk"}:
        required_fields.append("rows")
    if answer_type == "ranking":
        required_fields.extend(["member_name", "member_code"])
    if module in {"stocks", "collections", "material_balance"}:
        required_fields.append("metrics")

    completeness_rules: list[str] = [
        "no_unrelated_lots_fallback",
        "numeric_values_must_come_from_sql_or_ml",
    ]
    if answer_type == "ranking":
        completeness_rules.append("ordered_totals_required")
    if answer_type == "comparison":
        completeness_rules.append("both_sides_required")
    if "RAG" in required_sources:
        completeness_rules.append("rag_concepts_required")

    output_blocks_needed = ["answer_summary", "sources", "warnings"]
    if answer_type in {"list", "ranking", "comparison", "risk_list", "multi_intent_sql_rag", "chart_stock", "chart_stock_multi", "chart_stage_loss", "chart_lot_loss", "chart_lot_critical", "chart_product_loss", "chart_low_efficiency_lots", "chart_ml_anomaly_lots", "chart_recommendation_risk"}:
        output_blocks_needed.append("table")
    if answer_type in {"comparison", "chart_stock", "chart_stock_multi", "chart_stage_loss", "chart_lot_loss", "chart_lot_critical", "chart_product_loss", "chart_low_efficiency_lots", "chart_ml_anomaly_lots", "chart_recommendation_risk"}:
        output_blocks_needed.append("chart")
    if answer_type in {"recommendation", "hybrid_analysis"}:
        output_blocks_needed.append("recommendation_cards")
    if answer_type == "multi_intent_sql_rag":
        output_blocks_needed.append("best_practices")

    operation = "generic"
    required_answer_fields: list[str] = []
    allowed_sources: list[str] = [s.lower() for s in required_sources]
    period = None
    limit = None
    metric = ""
    if ("mini check-list" in normalized or "check-list" in normalized or "checklist" in normalized) or (
        any(token in normalized for token in ("humidite", "sechage", "tri", "stockage", "casse"))
        and any(token in normalized for token in ("recommand", "priorite", "conseille"))
    ):
        operation = "rag_practical_checklist"
        required_answer_fields = ["checklist"]
        allowed_sources = ["rag"]
    elif (
        "trimestre" in normalized
        and re.search(r"\bmoyenn?e?s?\b", normalized)
        and re.search(r"\bfactur\w*\b", normalized)
        and re.search(r"\b(pay\w*|regl\w*)\b", normalized)
    ):
        operation = "avg_paid_invoices_current_quarter"
        required_answer_fields = ["avg_paid_invoice_fcfa"]
        metric = "avg_paid_invoice_fcfa"
    elif "client" in normalized and ("plus gros cumul" in normalized or "plus de commandes" in normalized):
        operation = "top_customer_by_orders"
        required_answer_fields = ["customer_name", "total_amount_fcfa"]
    elif "charges globales" in normalized and (
        "vs" in normalized
        or "mois dernier" in normalized
        or "mois precedent" in normalized
        or ("compare" in normalized and "ce mois" in normalized)
    ):
        operation = "month_vs_month_charges"
        required_answer_fields = ["current_month_fcfa", "previous_month_fcfa"]
    elif "plus petit contributeur" in normalized and "zero" in normalized:
        operation = "lowest_nonzero_member_contributor"
        required_answer_fields = ["member_name", "kg"]
    elif "parcelle" in normalized and "plus grande" in normalized:
        operation = "largest_parcel_by_product"
        required_answer_fields = ["parcel_name", "surface_ha", "member_name"]
    elif "grade" in normalized and (
        "pese le plus" in normalized
        or "plus en volume" in normalized
        or ("domine" in normalized and ("volume" in normalized or "collect" in normalized))
    ):
        operation = "top_grade_by_volume"
        required_answer_fields = ["grade", "kg"]
        period = "last_90_days"
        limit = 1
    elif "collecte" in normalized and re.search(r"\b(top\s*\d*|plus fort|plus forts|plus fortes)\b", normalized) and "jour" in normalized:
        operation = "top_collection_days"
        required_answer_fields = ["date", "kg"]
        period = "last_6_months"
        limit = 3
    elif "disponible net" in normalized and "seuil" in normalized:
        operation = "available_stock_gap"
        required_answer_fields = ["available_kg", "gap_kg"]
    elif ("lots encore ouverts" in normalized or "lots ouverts" in normalized) and "plus ancien" in normalized:
        operation = "oldest_open_lot"
        required_answer_fields = ["lot_code", "creation_date"]
    elif "etape" in normalized and re.search(r"plus\s+de\s+pertes?|plus\s+de\s+perte", normalized):
        operation = "process_stage_loss_ranking"
        required_answer_fields = ["stage", "kg_loss"]
        period = "last_30_days"
    elif "anomaly_score" in normalized and ("plus grand" in normalized or "max" in normalized):
        operation = "max_anomaly_score_lot"
        required_answer_fields = ["lot_code", "anomaly_score"]
        allowed_sources = ["ml"]
    elif (
        ("signaux ml" in normalized or "signal ml" in normalized or "alertes ml" in normalized or "alerte ml" in normalized)
        and "high" in normalized
    ):
        operation = "ml_high_signal_count"
        required_answer_fields = ["high_signal_count"]
        allowed_sources = ["ml"]
    elif "lot" in normalized and "anormal" in normalized and "ml" in normalized:
        operation = "max_anomaly_score_lot"
        required_answer_fields = ["lot_code", "anomaly_score"]
        allowed_sources = ["ml"]

    return AnswerPlan(
        module=module,
        intent=intent,
        answer_type=answer_type,
        required_sources=required_sources,
        required_fields=required_fields,
        completeness_rules=completeness_rules,
        output_blocks_needed=output_blocks_needed,
        domain=module,
        operation=operation,
        metric=metric,
        filters={},
        product=(_first_or_none((detected_entities or {}).get("product"))),
        status=None,
        grade=None,
        date_range=None,
        period=period,
        limit=chart_limit or limit,
        required_answer_fields=required_answer_fields,
        allowed_sources=allowed_sources,
        chart_target=chart_target,
        chart_metric=chart_metric,
        chart_group_by=chart_group_by,
        chart_series=chart_series,
    )


def build_evidence_pack(*, question: str, plan: AnswerPlan, route: AgentRoute, agent_results: list[AgentResult]) -> EvidencePack:
    sql_data: dict[str, Any] = {}
    rag_data: dict[str, Any] = {"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []}
    ml_data: dict[str, Any] = {}
    reco_data: dict[str, Any] = {"actions": [], "insufficient_evidence": False}

    warnings: list[str] = []
    confidences: list[float] = []
    tables_used: set[str] = set()

    for result in agent_results:
        confidences.append(float(result.confidence or 0.0))
        warnings.extend(result.warnings)

        if result.agent_name == "SQLAnalyticsAgent":
            sql_data = dict(result.data or {})
            for src in result.sources or []:
                table = str(src.get("table") or "").strip()
                if table:
                    for part in table.split(","):
                        if part.strip():
                            tables_used.add(part.strip())

        elif result.agent_name == "RAGKnowledgeAgent":
            rag_data["chunks"] = (result.data or {}).get("chunks") or []
            for chunk in rag_data["chunks"]:
                if not isinstance(chunk, dict):
                    continue
                title = str(chunk.get("title") or "").strip()
                content = str(chunk.get("content") or "").strip()
                score = float(chunk.get("final_score") or chunk.get("hybrid_score") or 0.0)
                metadata = chunk.get("metadata") or {}
                topic = str(metadata.get("topic") or metadata.get("chunk_type") or "").strip()
                if title:
                    rag_data["titles"].append(title)
                if content:
                    rag_data["content_snippets"].append(_compact(content, 260))
                rag_data["scores"].append(score)
                if topic:
                    rag_data["topics"].append(topic)

        elif result.agent_name == "MLLossAgent":
            ml_data = dict(result.data or {})

        elif result.agent_name == "RecommendationAgent":
            recs = (result.data or {}).get("recommendations") or []
            reco_data["actions"] = recs if isinstance(recs, list) else []
            reco_data["insufficient_evidence"] = bool((result.data or {}).get("insufficient_evidence", False))

    sql_rows = _extract_sql_rows(sql_data)
    sql_metrics = _extract_sql_metrics(sql_data)

    module_registry = _build_module_registry(sql_data=sql_data, tables_used=tables_used)

    return EvidencePack(
        question=question,
        plan=plan,
        route=route,
        sql={
            "tables_used": sorted(tables_used),
            "rows": sql_rows,
            "metrics": sql_metrics,
            "calculations": {},
            "payload": sql_data,
        },
        rag=rag_data,
        ml=ml_data,
        recommendations=reco_data,
        warnings=sorted(set(warnings)),
        confidence=sum(confidences) / max(1, len(confidences)),
        module_registry=module_registry,
    )


def verify_evidence(pack: EvidencePack) -> EvidenceVerification:
    issues: list[str] = []
    required = set(pack.plan.required_sources)
    op = str(pack.plan.operation or "")

    available = {
        "SQL": bool(pack.sql.get("payload")),
        "RAG": bool(pack.rag.get("chunks")),
        "ML": bool(pack.ml),
        "RECOMMENDATION": bool(pack.recommendations.get("actions") or pack.recommendations.get("insufficient_evidence")),
    }

    for src in required:
        if not available.get(src, False):
            issues.append(f"MISSING_{src}_EVIDENCE")

    answer_type = pack.plan.answer_type
    rows = pack.sql.get("rows") or []

    if (
        answer_type in {"list", "ranking", "comparison", "risk_list"}
        and not rows
        and not pack.sql.get("metrics")
        and op not in {"max_anomaly_score_lot", "ml_high_signal_count"}
    ):
        issues.append("MISSING_SQL_ROWS")

    if answer_type == "ranking":
        ranking_rows = _ranking_rows(pack.sql.get("payload") or {})
        if ranking_rows:
            sorted_rows = sorted(ranking_rows, key=lambda r: float(r.get("total_quantity_kg", 0.0) or 0.0), reverse=True)
            if ranking_rows != sorted_rows:
                issues.append("RANKING_NOT_ORDERED")

    if "RAG" in required and pack.rag.get("chunks"):
        snippets = " ".join(pack.rag.get("content_snippets") or []).lower()
        if not snippets:
            issues.append("RAG_CONTENT_MISSING")

    if pack.plan.module in {"invoices", "commercial", "finance", "members", "member_value"}:
        text_probe = " ".join([str(v) for v in (pack.sql.get("tables_used") or [])]).lower()
        if "batches" in text_probe and len(pack.sql.get("tables_used") or []) == 1:
            issues.append("UNRELATED_BATCH_FALLBACK")

    # Strict operation-level validation.
    payload = pack.sql.get("payload") or {}
    required_fields = pack.plan.required_answer_fields or []
    op_rows = payload.get(op) if op else None
    if op.startswith("rag_") and not pack.rag.get("chunks"):
        issues.append("MISSING_RAG_PRACTICAL_CONTENT")
    if op.startswith("ml_") or op == "max_anomaly_score_lot":
        if not pack.ml:
            issues.append("MISSING_ML_EVIDENCE")
    if op and not op.startswith("rag_") and not op.startswith("ml_") and op != "max_anomaly_score_lot":
        if op_rows is None:
            issues.append("MISSING_OPERATION_RESULT")
        elif not op_rows:
            issues.append("EMPTY_OPERATION_RESULT")
        elif required_fields:
            first = op_rows[0] if isinstance(op_rows, list) else {}
            for field in required_fields:
                if field not in first:
                    issues.append(f"MISSING_REQUIRED_FIELD_{field.upper()}")

    return EvidenceVerification(ok=not issues, issues=sorted(set(issues)))


def compose_answer(pack: EvidencePack, verification: EvidenceVerification) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    has_any_evidence = bool(
        pack.sql.get("rows")
        or pack.sql.get("metrics")
        or pack.rag.get("chunks")
        or pack.ml
        or pack.recommendations.get("actions")
    )
    if not has_any_evidence:
        return (
            "Donnée non disponible pour cette requête précise.",
            [
                {"type": "summary", "title": "Résumé", "content": "Donnée non disponible pour cette requête précise."},
                {"type": "warnings", "title": "Avertissements", "items": [_warning_label("NO_VERIFIED_EVIDENCE")]},
            ],
            {"answer_type": pack.plan.answer_type, "evidence_roles": _evidence_roles(pack), "module_registry": pack.module_registry},
        )
    if not verification.ok and pack.plan.operation != "generic":
        return (
            "Donnée non disponible pour cette requête précise.",
            [
                {"type": "summary", "title": "Résumé", "content": "Donnée non disponible pour cette requête précise."},
                {"type": "warnings", "title": "Avertissements", "items": [_warning_label(i) for i in verification.issues]},
            ],
            {"answer_type": pack.plan.answer_type, "evidence_roles": _evidence_roles(pack), "module_registry": pack.module_registry},
        )
    sql_payload = pack.sql.get("payload") or {}
    blocks: list[dict[str, Any]] = []

    summary = _compose_summary(pack=pack, sql_payload=sql_payload)
    blocks.append({"type": "summary", "title": "Résumé", "content": summary})

    table_block = _compose_table_block(pack=pack, sql_payload=sql_payload)
    if table_block:
        blocks.append(table_block)

    best_practice_block = _compose_best_practice_block(pack=pack)
    if best_practice_block:
        blocks.append(best_practice_block)

    chart_block = _compose_chart_block(pack=pack, sql_payload=sql_payload)
    if chart_block:
        blocks.append(chart_block)

    recommendation_block = _compose_recommendation_block(pack=pack)
    if recommendation_block:
        blocks.append(recommendation_block)

    blocks.append(
        {
            "type": "sources",
            "title": "Sources",
            "items": [
                {
                    "source": table,
                    "role": "SQL",
                }
                for table in (pack.sql.get("tables_used") or [])
            ]
            + [
                {
                    "source": title,
                    "role": "RAG",
                }
                for title in (pack.rag.get("titles") or [])[:5]
            ]
            + ([{"source": str(pack.ml.get("model_version") or "ml_signal"), "role": "ML"}] if pack.ml else []),
        }
    )

    warning_items = [
        _warning_label(item)
        for item in sorted(set([*pack.warnings, *verification.issues]))
        if item
    ]
    blocks.append({"type": "warnings", "title": "Avertissements", "items": warning_items})

    answer_lines = [
        "1. Résultat principal",
        summary,
        "",
        "2. Explication courte",
    ]

    explanation = _compose_explanation(pack=pack, sql_payload=sql_payload)
    answer_lines.append(explanation)

    answer_lines.extend(["", "3. Recommandations si pertinentes"])
    if recommendation_block and recommendation_block.get("items"):
        for idx, item in enumerate(recommendation_block.get("items", [])[:3], start=1):
            priority = str(item.get("priority") or "MEDIUM").upper()
            reason = str(item.get("reason") or "").strip()
            target_tokens = [item.get("affected_lot"), item.get("affected_product"), item.get("affected_stage")]
            target = " / ".join([str(token) for token in target_tokens if str(token or "").strip()])
            suffix = f" | Cible: {target}" if target else ""
            if reason:
                answer_lines.append(f"{idx}. [{priority}] {item.get('action')} - {reason}{suffix}")
            else:
                answer_lines.append(f"{idx}. [{priority}] {item.get('action')}{suffix}")
    else:
        answer_lines.append("Aucune recommandation prioritaire confirmée.")

    answer_lines.extend(["", "4. Sources utilisées"])
    for item in blocks[-2].get("items", [])[:8]:
        answer_lines.append(f"- {item.get('role')}: {item.get('source')}")

    answer_lines.extend(["", "5. Avertissements si nécessaires"])
    if warning_items:
        for item in warning_items:
            answer_lines.append(f"- {item}")
    else:
        answer_lines.append("Aucun avertissement critique.")

    answer = "\n".join(answer_lines)
    answer, post_warnings = post_validate_answer(answer=answer, pack=pack)
    if post_warnings:
        blocks[-1]["items"] = sorted(set([*blocks[-1].get("items", []), *post_warnings]))

    metadata = {
        "answer_type": pack.plan.answer_type,
        "evidence_roles": _evidence_roles(pack),
        "module_registry": pack.module_registry,
    }

    return answer, blocks, metadata


def post_validate_answer(*, answer: str, pack: EvidencePack) -> tuple[str, list[str]]:
    warnings: list[str] = []
    updated_answer = answer
    snippets = pack.rag.get("content_snippets") or []

    if snippets and "sources de connaissance récupérées donnent un contexte post-récolte" in updated_answer:
        # Hard guard: never keep generic wording when real RAG content exists.
        updated_answer = updated_answer.replace(
            "Les sources de connaissance récupérées donnent un contexte post-récolte, mais elles restent limitées pour cette question.",
            snippets[0],
        )
        warnings.append("GENERIC_RAG_REPLACED")

    if pack.plan.answer_type in {"list", "ranking", "comparison", "risk_list"} and "table" not in pack.plan.output_blocks_needed:
        warnings.append("RESPONSE_BLOCK_TABLE_MISSING")

    return updated_answer, warnings


def _compose_summary(*, pack: EvidencePack, sql_payload: dict[str, Any]) -> str:
    plan = pack.plan
    rec_actions = pack.recommendations.get("actions") or []
    op = str(plan.operation or "")
    if op == "rag_practical_checklist":
        snippets = pack.rag.get("content_snippets") or []
        return snippets[0] if snippets else "Donnée non disponible pour cette requête précise."
    if op and op in sql_payload:
        rows = sql_payload.get(op) or []
        if not rows:
            return "Donnée non disponible pour cette requête précise."
        row = rows[0]
        if op == "avg_paid_invoices_current_quarter":
            return f"Montant moyen factures payées (trimestre courant): {float(row.get('avg_paid_invoice_fcfa', 0.0)):.0f} FCFA."
        if op == "top_customer_by_orders":
            return f"Client leader: {row.get('customer_name')} ({float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA)."
        if op == "month_vs_month_charges":
            return f"Charges: mois courant {float(row.get('current_month_fcfa', 0.0)):.0f} FCFA vs mois précédent {float(row.get('previous_month_fcfa', 0.0)):.0f} FCFA."
        if op == "lowest_nonzero_member_contributor":
            return f"Plus petit contributeur hors zéro: {row.get('member_name')} ({float(row.get('kg', 0.0)):.1f} kg)."
        if op == "largest_parcel_by_product":
            return f"Plus grande parcelle: {row.get('parcel_name')} ({float(row.get('surface_ha', 0.0)):.2f} ha), membre {row.get('member_name')}."
        if op == "top_grade_by_volume":
            return f"Grade dominant: {row.get('grade')} ({float(row.get('kg', 0.0)):.1f} kg)."
        if op == "top_collection_days":
            return "; ".join(f"{r.get('date')}: {float(r.get('kg', 0.0)):.1f} kg" for r in rows[:3])
        if op == "available_stock_gap":
            return f"{row.get('product')}: disponible net {float(row.get('available_kg', 0.0)):.1f} kg, écart seuil {float(row.get('gap_kg', 0.0)):.1f} kg."
        if op == "oldest_open_lot":
            return f"Lot ouvert le plus ancien: {row.get('lot_code')} ({row.get('creation_date')})."
        if op == "process_stage_loss_ranking":
            return f"Étape la plus pénalisante: {row.get('stage')} ({float(row.get('kg_loss', 0.0)):.1f} kg)."
    if op == "max_anomaly_score_lot":
        rows = pack.ml.get("max_anomaly_score_lot") or []
        if rows:
            r = rows[0]
            return f"Lot anomaly_score max: {r.get('lot_code')} ({float(r.get('anomaly_score', 0.0)):.4f})."
        return "Donnée non disponible pour cette requête précise."
    if op == "ml_high_signal_count":
        rows = pack.ml.get("ml_high_signal_count") or []
        if rows:
            r = rows[0]
            return f"Signaux ML HIGH ({int(r.get('days', 0))} jours): {int(r.get('high_signal_count', 0))}."
        return "Donnée non disponible pour cette requête précise."

    if plan.answer_type == "chart_stock":
        rows = sql_payload.get("current_stock") or []
        if rows:
            total = sum(float(row.get("available_stock_kg", 0.0) or 0.0) for row in rows)
            lead = max(rows, key=lambda row: float(row.get("available_stock_kg", 0.0) or 0.0))
            return (
                f"Graphique stock prêt: {len(rows)} produit(s), total {total:.1f} kg. "
                f"Produit principal: {_fr_product(lead.get('product'))} ({float(lead.get('available_stock_kg', 0.0) or 0.0):.1f} kg)."
            )
        return "Aucune donnée de stock disponible pour générer le graphique."

    if plan.answer_type == "chart_stock_multi":
        rows = sql_payload.get("current_stock") or []
        if rows:
            return f"Graphique comparatif stock total/réservé/disponible prêt ({len(rows)} produit(s))."
        return "Aucune donnée de stock disponible pour ce graphique comparatif."

    if plan.answer_type == "chart_product_loss":
        rows = _product_loss_rows(sql_payload)
        if rows:
            return f"Graphique des pertes par produit prêt ({len(rows)} produit(s))."
        return "Aucune donnée de pertes par produit disponible pour ce graphique."

    if plan.answer_type == "chart_stage_loss":
        rows = sql_payload.get("stage_efficiency_summary") or []
        if rows:
            top = max(rows, key=lambda row: float(row.get("avg_loss_pct", 0.0) or 0.0))
            return (
                f"Graphique des pertes moyennes par étape prêt ({len(rows)} étape(s)). "
                f"Étape la plus critique: {_fr_stage(top.get('stage'))} ({float(top.get('avg_loss_pct', 0.0) or 0.0):.1f}%)."
            )
        return "Aucune donnée d’étape disponible pour calculer les pertes moyennes."

    if plan.answer_type == "chart_lot_loss":
        rows = _top_loss_rows(sql_payload)
        if rows:
            top = rows[0]
            return (
                f"Graphique des lots à plus fortes pertes prêt ({len(rows)} lot(s)). "
                f"Lot le plus touché: {top.get('batch_ref')} ({float(top.get('loss_pct', 0.0) or 0.0):.1f}%)."
            )
        return "Aucune donnée lot/perte disponible pour ce graphique."

    if plan.answer_type == "chart_lot_critical":
        rows = _critical_lot_rows(sql_payload=sql_payload, ml_payload=pack.ml, limit=pack.plan.limit or 5)
        if rows:
            return f"Graphique des lots critiques prêt ({len(rows)} lot(s))."
        return "Aucune donnée de lots critiques disponible pour ce graphique."

    if plan.answer_type == "chart_low_efficiency_lots":
        rows = _low_efficiency_rows(sql_payload, limit=pack.plan.limit or 5)
        if rows:
            return f"Graphique des lots les moins efficaces prêt ({len(rows)} lot(s))."
        return "Aucune donnée de lots à faible efficacité disponible pour ce graphique."

    if plan.answer_type == "chart_ml_anomaly_lots":
        rows = _ml_anomaly_rows(pack.ml, limit=pack.plan.limit or 5)
        if rows:
            return f"Graphique anomaly_score ML par lot prêt ({len(rows)} lot(s))."
        return "Les données ML anomaly_score par lot ne sont pas disponibles pour ce graphique."

    if plan.answer_type == "chart_recommendation_risk":
        recs = pack.recommendations.get("actions") or []
        if recs:
            return f"Graphique des recommandations par niveau de risque prêt ({len(recs)} recommandation(s))."
        return "Données de recommandations par risque indisponibles pour ce graphique."

    if plan.answer_type == "recommendation":
        if rec_actions:
            high_count = sum(1 for item in rec_actions if str(item.get("priority") or "").upper() == "HIGH")
            lead = rec_actions[0]
            target_tokens = [lead.get("related_batch"), lead.get("related_product"), lead.get("related_stage")]
            target = " / ".join([str(token) for token in target_tokens if str(token or "").strip()])
            if target:
                target = f" (cible: {target})"
            return (
                f"{len(rec_actions)} action(s) priorisée(s) générée(s), dont {high_count} priorité haute. "
                f"Action principale: {lead.get('action')}{target}."
            )
        return "Aucune action prioritaire n’a pu être établie avec les preuves disponibles."

    if plan.answer_type == "multi_intent_sql_rag":
        stock_rows = sql_payload.get("current_stock") or []
        snippets = pack.rag.get("content_snippets") or []
        stock_part = "Les stocks actuels ne sont pas disponibles."
        if stock_rows:
            stock_part = f"Stocks disponibles: {len(stock_rows)} produit(s), total {sum(float(r.get('available_stock_kg', 0.0) or 0.0) for r in stock_rows):.1f} kg."
        rag_part = "Bonnes pratiques: aucune source RAG exploitable."
        if snippets:
            rag_part = f"Bonnes pratiques: {_compact(snippets[0], 160)}"
        return f"{stock_part}\n{rag_part}"

    if pack.route == AgentRoute.HYBRID_FULL:
        sql_rows = _top_loss_rows(sql_payload) or (sql_payload.get("high_risk_lots") or []) or (sql_payload.get("batch_summary") or [])
        sql_line = "SQL indisponible."
        if sql_rows:
            row = sql_rows[0]
            sql_line = (
                f"SQL: lot {row.get('batch_ref') or row.get('lot_code') or '?'} | "
                f"perte {float(row.get('loss_pct', row.get('loss_percentage', 0.0)) or 0.0):.1f}% | "
                f"efficacité {float(row.get('efficiency_pct', row.get('efficiency_percentage', 0.0)) or 0.0):.1f}%."
            )
        ml_line = "ML indisponible."
        if pack.ml:
            ml_line = (
                f"ML: risque {str(pack.ml.get('risk_level') or 'UNKNOWN').upper()} | "
                f"anomaly_score {float(pack.ml.get('anomaly_score', 0.0) or 0.0):.4f}."
            )
        rag_line = "RAG indisponible."
        if pack.rag.get("content_snippets"):
            rag_line = f"RAG: {_compact(pack.rag.get('content_snippets')[0], 150)}"
        reco_line = "Recommandations indisponibles."
        if rec_actions:
            reco_line = f"Action prioritaire: {rec_actions[0].get('action') or rec_actions[0].get('title') or 'N/A'}."
        return f"{sql_line}\n{ml_line}\n{rag_line}\n{reco_line}"

    if sql_payload.get("cooperative_overview"):
        row = (sql_payload.get("cooperative_overview") or [{}])[0]
        return (
            "Résumé coopérative: "
            f"{int(row.get('member_count', 0) or 0)} membre(s), "
            f"{int(row.get('parcel_count', 0) or 0)} parcelle(s), "
            f"{int(row.get('batch_count', 0) or 0)} lot(s) dont "
            f"{int(row.get('open_batch_count', 0) or 0)} en cours, "
            f"stock total {float(row.get('stock_total_kg', 0.0) or 0.0):.1f} kg, "
            f"perte moyenne {float(row.get('avg_loss_pct', 0.0) or 0.0):.1f}%."
        )

    if sql_payload.get("parcel_count") is not None:
        return f"La coopérative compte {int(sql_payload.get('parcel_count', 0) or 0)} parcelle(s) enregistrée(s)."

    if sql_payload.get("members_list") is not None and plan.module == "members":
        members = sql_payload.get("members_list") or []
        return f"La coopérative compte {len(members)} membre(s) inscrit(s)."

    ranking_rows = _ranking_rows(sql_payload)
    if ranking_rows and plan.answer_type in {"ranking", "list"}:
        lines = [f"Classement des membres par quantité collectée ({len(ranking_rows)}):"]
        for row in ranking_rows[:10]:
            lines.append(
                f"- {row.get('member_name')} ({row.get('member_code')}): {float(row.get('total_quantity_kg', 0.0)):.1f} kg"
            )
        return "\n".join(lines)

    if sql_payload.get("in_progress_lots") is not None:
        rows = sql_payload.get("in_progress_lots") or []
        if rows:
            lines = [f"Lots en cours ({len(rows)}):"]
            for row in rows:
                lines.append(
                    f"- {row.get('batch_ref')}: perte {float(row.get('loss_pct', 0.0)):.1f} % | efficacité {float(row.get('efficiency_pct', 0.0)):.1f} %"
                )
            return "\n".join(lines)
        return "Aucun lot en cours n’a été trouvé."

    if sql_payload.get("low_efficiency_lots") is not None:
        rows = sql_payload.get("low_efficiency_lots") or []
        if rows:
            rows = sorted(rows, key=lambda item: float(item.get("efficiency_pct", 100.0) or 100.0))
            lines = [f"Lots à efficacité faible ({len(rows)}):"]
            for row in rows:
                lines.append(
                    f"- {row.get('batch_ref')}: efficacité {float(row.get('efficiency_pct', 0.0)):.1f} % | perte {float(row.get('loss_pct', 0.0)):.1f} %"
                )
            return "\n".join(lines)
        return "Aucun lot à efficacité faible n’a été détecté."

    if sql_payload.get("high_risk_lots") is not None:
        rows = sql_payload.get("high_risk_lots") or []
        if rows:
            lines = [f"Lots à risque élevé ({len(rows)}):"]
            for row in rows:
                lines.append(
                    f"- {row.get('batch_ref')}: perte {float(row.get('loss_pct', 0.0)):.1f} % | efficacité {float(row.get('efficiency_pct', 0.0)):.1f} %"
                )
            return "\n".join(lines)
        return "Aucun lot à risque élevé n’a été détecté."

    if sql_payload.get("stage_loss_comparison"):
        rows = sql_payload.get("stage_loss_comparison") or []
        if len(rows) >= 2:
            left, right = rows[0], rows[1]
            return (
                f"Comparaison des pertes: {left.get('stage_label')} {float(left.get('avg_loss_pct', 0.0)):.1f}% vs "
                f"{right.get('stage_label')} {float(right.get('avg_loss_pct', 0.0)):.1f}%."
            )

    if sql_payload.get("current_stock"):
        rows = sql_payload.get("current_stock") or []
        lines = [f"Les stocks actuels ({len(rows)} produits) sont:"]
        for row in rows:
            lines.append(f"- {_fr_product(row.get('product'))}: {float(row.get('available_stock_kg', 0.0)):.1f} kg disponibles")
        return "\n".join(lines)

    if sql_payload.get("collections_summary") is not None:
        rows = sql_payload.get("collections_summary") or []
        if rows:
            total = sum(float(row.get("total_quantity_kg", 0.0) or 0.0) for row in rows)
            return f"Quantité collectée observée: {total:.1f} kg."
        return "Aucune collecte n’est disponible dans les données actuelles."

    if sql_payload.get("parcels_list") is not None:
        rows = sql_payload.get("parcels_list") or []
        if rows:
            lines = [f"Parcelles enregistrées ({len(rows)}):"]
            for row in rows[:20]:
                lines.append(f"- {row.get('parcel_name')}: {float(row.get('surface_ha', 0.0)):.2f} ha")
            return "\n".join(lines)
        return "Aucune parcelle n’est enregistrée pour cette coopérative."

    if sql_payload.get("material_balance"):
        rows = sql_payload.get("material_balance") or []
        if not rows:
            return "Le bilan matière n’est pas disponible pour cette requête."
        if len(rows) == 1:
            item = rows[0]
            return (
                f"Le bilan matière du lot {item.get('batch_ref')} montre une perte de {float(item.get('loss_percentage', 0.0) or 0.0):.1f} % "
                f"et une efficacité de {float(item.get('efficiency_percentage', 0.0) or 0.0):.1f} %."
            )
        total_in = sum(float(item.get("input_quantity", 0.0) or 0.0) for item in rows)
        total_out = sum(float(item.get("output_quantity", 0.0) or 0.0) for item in rows)
        loss_pct = ((total_in - total_out) / total_in * 100.0) if total_in > 0 else 0.0
        return (
            "Bilan matière global: "
            f"entrée {total_in:.1f} kg, sortie {total_out:.1f} kg, perte {loss_pct:.1f}%."
        )

    if sql_payload.get("process_step_losses"):
        rows = sql_payload.get("process_step_losses") or []
        top = max(rows, key=lambda row: float(row.get("loss_pct", 0.0) or 0.0), default=None)
        if top:
            return (
                f"Perte observée sur {_fr_stage(top.get('stage'))} "
                f"du lot {top.get('batch_ref')}: {float(top.get('loss_pct', 0.0) or 0.0):.1f}% "
                f"({float(top.get('qty_in', 0.0) or 0.0):.1f} kg -> {float(top.get('qty_out', 0.0) or 0.0):.1f} kg)."
            )

    if sql_payload.get("batch_summary"):
        item = (sql_payload.get("batch_summary") or [{}])[0]
        return (
            f"Le lot {item.get('batch_ref')} présente une perte de {float(item.get('loss_pct', 0.0) or 0.0):.1f}% "
            f"et une efficacité de {float(item.get('efficiency_pct', 0.0) or 0.0):.1f}%."
        )

    if sql_payload.get("invoices_summary") is not None:
        rows = sql_payload.get("invoices_summary") or []
        if rows:
            return f"Factures disponibles: {len(rows)}."
        return "Aucune facture n’est disponible dans les données actuelles."

    if sql_payload.get("commercial_orders") is not None:
        rows = sql_payload.get("commercial_orders") or []
        if rows:
            return f"Commandes commerciales disponibles: {len(rows)}."
        return "Aucune commande commerciale n’est disponible dans les données actuelles."

    if sql_payload.get("finance_expenses") is not None:
        row = (sql_payload.get("finance_expenses") or [{}])[0]
        tc = int(row.get("treasury_count", 0) or 0)
        gc = int(row.get("global_charge_count", 0) or 0)
        if tc == 0 and gc == 0:
            return "Aucune charge ou dépense n’est disponible dans les données actuelles."
        return (
            "Synthèse charges/dépenses: "
            f"{tc} transaction(s) trésorerie pour {float(row.get('treasury_total_fcfa', 0.0)):.0f} FCFA, "
            f"{gc} charge(s) globales pour {float(row.get('global_charge_total_fcfa', 0.0)):.0f} FCFA."
        )

    if pack.route in {AgentRoute.RAG_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL}:
        snippets = pack.rag.get("content_snippets") or []
        if snippets:
            return snippets[0]

    if pack.route in {AgentRoute.HYBRID_SQL_ML, AgentRoute.ML_ONLY} and pack.ml:
        risk = str(pack.ml.get("risk_level") or "UNKNOWN").upper()
        anomaly = bool(pack.ml.get("anomaly_detected"))
        return f"Signal ML: risque {risk} | anomalie {'oui' if anomaly else 'non'}."

    return "Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande."


def _compose_explanation(*, pack: EvidencePack, sql_payload: dict[str, Any]) -> str:
    snippets = pack.rag.get("content_snippets") or []
    rec_actions = pack.recommendations.get("actions") or []

    if pack.plan.answer_type == "recommendation":
        if rec_actions:
            parts = []
            for item in rec_actions[:2]:
                reason = str(item.get("reason") or "").strip()
                if reason:
                    parts.append(reason)
            if parts:
                return "Priorisation: " + " ".join(parts)
            return "Les actions sont priorisées selon les signaux pertes/efficacité, disponibilité stock et contexte documentaire."
        return "Les preuves disponibles sont insuffisantes pour établir une priorisation robuste."

    if pack.route in {AgentRoute.RAG_ONLY}:
        if snippets:
            points = _best_practice_points(snippets[0])
            if points:
                return "Bonnes pratiques: " + " ; ".join(points[:4])
            return snippets[0]
        return "Aucune explication détaillée n’a pu être extraite des sources RAG disponibles."

    if pack.route in {AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_FULL}:
        sql_line = ""
        if sql_payload.get("material_balance"):
            item = (sql_payload.get("material_balance") or [{}])[0]
            sql_line = (
                f"Mesures SQL: perte {float(item.get('loss_percentage', 0.0)):.1f}% et efficacité "
                f"{float(item.get('efficiency_percentage', 0.0)):.1f}%"
            )
        elif sql_payload.get("process_step_losses"):
            top = max(
                sql_payload.get("process_step_losses") or [],
                key=lambda r: float(r.get("loss_pct", 0.0) or 0.0),
                default=None,
            )
            if top:
                sql_line = f"Mesures SQL: étape critique {top.get('stage')} ({float(top.get('loss_pct', 0.0)):.1f}%)."

        if snippets:
            rag_line = "Explication RAG: " + snippets[0]
            return (sql_line + " " + rag_line).strip()
        if sql_line:
            return sql_line

    if pack.route in {AgentRoute.HYBRID_SQL_ML, AgentRoute.ML_ONLY} and pack.ml:
        return (
            f"Signal ML: risque {str(pack.ml.get('risk_level') or 'UNKNOWN').upper()} | "
            f"anomalie {'oui' if pack.ml.get('anomaly_detected') else 'non'}; "
            "les mesures SQL restent la vérité opérationnelle."
        )

    return "Aucune explication détaillée disponible."


def _compose_table_block(*, pack: EvidencePack, sql_payload: dict[str, Any]) -> dict[str, Any] | None:
    if pack.plan.answer_type not in {"list", "ranking", "comparison", "risk_list", "hybrid_analysis", "chart_stock", "chart_stock_multi", "chart_stage_loss", "chart_lot_loss", "chart_lot_critical", "chart_product_loss", "chart_low_efficiency_lots", "chart_ml_anomaly_lots", "chart_recommendation_risk"}:
        return None

    if pack.plan.answer_type == "chart_stock":
        rows = sql_payload.get("current_stock") or []
        if rows:
            return {
                "type": "table",
                "title": "Stock actuel",
                "columns": ["Produit", "Stock disponible"],
                "rows": [[_fr_product(row.get("product")), f"{float(row.get('available_stock_kg', 0.0)):.1f} kg"] for row in rows],
            }

    if pack.plan.answer_type == "chart_stock_multi":
        rows = sql_payload.get("current_stock") or []
        if rows:
            return {
                "type": "table",
                "title": "Stock total / réservé / disponible",
                "columns": ["Produit", "Stock total", "Stock réservé", "Disponible net"],
                "rows": [
                    [
                        _fr_product(row.get("product")),
                        f"{float(row.get('total_stock_kg', 0.0) or 0.0):.1f} kg",
                        f"{float(row.get('reserved_in_lots_kg', 0.0) or 0.0):.1f} kg",
                        f"{float(row.get('available_stock_kg', 0.0) or 0.0):.1f} kg",
                    ]
                    for row in rows
                ],
            }

    if pack.plan.answer_type == "chart_product_loss":
        rows = _product_loss_rows(sql_payload)
        if rows:
            return {
                "type": "table",
                "title": "Pertes par produit",
                "columns": ["Produit", "Perte moyenne", "Efficacité moyenne", "Occurrences"],
                "rows": [
                    [
                        _fr_product(row.get("product")),
                        f"{float(row.get('avg_loss_pct', 0.0) or 0.0):.1f} %",
                        f"{float(row.get('avg_efficiency_pct', 0.0) or 0.0):.1f} %",
                        int(row.get("count", 0) or 0),
                    ]
                    for row in rows
                ],
            }

    if pack.plan.answer_type == "chart_stage_loss":
        rows = sql_payload.get("stage_efficiency_summary") or []
        if rows:
            return {
                "type": "table",
                "title": "Pertes moyennes par étape",
                "columns": ["Étape", "Perte moyenne", "Efficacité moyenne"],
                "rows": [
                    [
                        _fr_stage(row.get("stage")),
                        f"{float(row.get('avg_loss_pct', 0.0) or 0.0):.1f} %",
                        f"{float(row.get('avg_efficiency_pct', 0.0) or 0.0):.1f} %",
                    ]
                    for row in rows
                ],
            }

    if pack.plan.answer_type == "chart_lot_loss":
        rows = _top_loss_rows(sql_payload)
        if rows:
            return {
                "type": "table",
                "title": "Lots avec les pertes les plus élevées",
                "columns": ["Lot", "Produit", "Perte", "Efficacité"],
                "rows": [
                    [
                        str(row.get("batch_ref") or ""),
                        _fr_product(row.get("product")),
                        f"{float(row.get('loss_pct', 0.0) or 0.0):.1f} %",
                        f"{float(row.get('efficiency_pct', 0.0) or 0.0):.1f} %",
                    ]
                    for row in rows
                ],
            }

    if pack.plan.answer_type == "chart_lot_critical":
        rows = _critical_lot_rows(sql_payload=sql_payload, ml_payload=pack.ml, limit=pack.plan.limit or 5)
        if rows:
            return {
                "type": "table",
                "title": "Top lots critiques",
                "columns": ["Lot", "Produit", "Perte", "Efficacité", "Signal ML"],
                "rows": [
                    [
                        str(row.get("batch_ref") or ""),
                        _fr_product(row.get("product")),
                        f"{float(row.get('loss_pct', 0.0) or 0.0):.1f} %",
                        f"{float(row.get('efficiency_pct', 0.0) or 0.0):.1f} %",
                        str(row.get("ml_signal") or "ML indisponible"),
                    ]
                    for row in rows
                ],
            }

    if pack.plan.answer_type == "chart_low_efficiency_lots":
        rows = _low_efficiency_rows(sql_payload, limit=pack.plan.limit or 5)
        if rows:
            return {
                "type": "table",
                "title": "Lots les moins efficaces",
                "columns": ["Lot", "Produit", "Efficacité", "Perte"],
                "rows": [
                    [
                        str(row.get("batch_ref") or ""),
                        _fr_product(row.get("product")),
                        f"{float(row.get('efficiency_pct', 0.0) or 0.0):.1f} %",
                        f"{float(row.get('loss_pct', 0.0) or 0.0):.1f} %",
                    ]
                    for row in rows
                ],
            }

    if pack.plan.answer_type == "chart_ml_anomaly_lots":
        rows = _ml_anomaly_rows(pack.ml, limit=pack.plan.limit or 5)
        if rows:
            return {
                "type": "table",
                "title": "Anomaly score ML par lot",
                "columns": ["Lot", "Anomaly score"],
                "rows": [[str(row.get("lot_code") or row.get("batch_ref") or ""), f"{float(row.get('anomaly_score', 0.0) or 0.0):.4f}"] for row in rows],
            }

    if pack.plan.answer_type == "chart_recommendation_risk":
        recs = pack.recommendations.get("actions") or []
        if recs:
            grouped: dict[str, int] = {}
            for rec in recs:
                level = str(rec.get("priority") or rec.get("risk_level") or "UNKNOWN").upper()
                grouped[level] = grouped.get(level, 0) + 1
            ordered = sorted(grouped.items(), key=lambda item: item[0])
            return {
                "type": "table",
                "title": "Recommandations par niveau de risque",
                "columns": ["Niveau", "Nombre de recommandations"],
                "rows": [[level, count] for level, count in ordered],
            }

    if _ranking_rows(sql_payload):
        rows = _ranking_rows(sql_payload)
        return {
            "type": "table",
            "title": "Classement des membres par quantité collectée",
            "columns": ["Membre", "Code", "Quantité collectée"],
            "rows": [
                [
                    str(row.get("member_name") or ""),
                    str(row.get("member_code") or ""),
                    f"{float(row.get('total_quantity_kg', 0.0)):.1f} kg",
                ]
                for row in rows
            ],
        }

    if sql_payload.get("low_efficiency_lots") is not None:
        rows = sql_payload.get("low_efficiency_lots") or []
        return {
            "type": "table",
            "title": "Lots à efficacité faible",
            "columns": ["Lot", "Efficacité", "Perte"],
            "rows": [
                [
                    str(row.get("batch_ref") or ""),
                    f"{float(row.get('efficiency_pct', 0.0)):.1f} %",
                    f"{float(row.get('loss_pct', 0.0)):.1f} %",
                ]
                for row in rows
            ],
        }

    if sql_payload.get("high_risk_lots") is not None:
        rows = sql_payload.get("high_risk_lots") or []
        return {
            "type": "table",
            "title": "Lots à risque élevé",
            "columns": ["Lot", "Perte", "Efficacité"],
            "rows": [
                [
                    str(row.get("batch_ref") or ""),
                    f"{float(row.get('loss_pct', 0.0)):.1f} %",
                    f"{float(row.get('efficiency_pct', 0.0)):.1f} %",
                ]
                for row in rows
            ],
        }

    if sql_payload.get("in_progress_lots") is not None:
        rows = sql_payload.get("in_progress_lots") or []
        return {
            "type": "table",
            "title": "Lots en cours",
            "columns": ["Lot", "Perte", "Efficacité"],
            "rows": [
                [
                    str(row.get("batch_ref") or ""),
                    f"{float(row.get('loss_pct', 0.0)):.1f} %",
                    f"{float(row.get('efficiency_pct', 0.0)):.1f} %",
                ]
                for row in rows
            ],
        }

    if sql_payload.get("stage_loss_comparison"):
        rows = sql_payload.get("stage_loss_comparison") or []
        return {
            "type": "table",
            "title": "Comparaison des pertes par étape",
            "columns": ["Étape", "Perte moyenne"],
            "rows": [[str(row.get("stage_label") or ""), f"{float(row.get('avg_loss_pct', 0.0)):.1f} %"] for row in rows],
        }

    if sql_payload.get("invoices_summary") is not None:
        rows = sql_payload.get("invoices_summary") or []
        return {
            "type": "table",
            "title": "Factures",
            "columns": ["Numéro", "Statut", "Montant"],
            "rows": [
                [str(row.get("invoice_number") or ""), str(row.get("status") or ""), f"{float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA"]
                for row in rows
            ],
        }

    if sql_payload.get("commercial_orders") is not None:
        rows = sql_payload.get("commercial_orders") or []
        return {
            "type": "table",
            "title": "Commandes commerciales",
            "columns": ["Numéro", "Statut", "Montant"],
            "rows": [
                [str(row.get("order_number") or ""), str(row.get("status") or ""), f"{float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA"]
                for row in rows
            ],
        }

    if sql_payload.get("finance_expenses") is not None:
        rows = sql_payload.get("finance_expenses") or []
        return {
            "type": "table",
            "title": "Charges et dépenses",
            "columns": ["Transactions trésorerie", "Total trésorerie", "Charges globales", "Total charges globales"],
            "rows": [
                [
                    int(row.get("treasury_count", 0) or 0),
                    f"{float(row.get('treasury_total_fcfa', 0.0)):.0f} FCFA",
                    int(row.get("global_charge_count", 0) or 0),
                    f"{float(row.get('global_charge_total_fcfa', 0.0)):.0f} FCFA",
                ]
                for row in rows
            ],
        }

    if sql_payload.get("current_stock"):
        rows = sql_payload.get("current_stock") or []
        return {
            "type": "table",
            "title": "Stock actuel",
            "columns": ["Produit", "Stock disponible"],
            "rows": [[_fr_product(row.get("product")), f"{float(row.get('available_stock_kg', 0.0)):.1f} kg"] for row in rows],
        }

    if sql_payload.get("stage_efficiency_summary"):
        rows = sql_payload.get("stage_efficiency_summary") or []
        return {
            "type": "table",
            "title": "Pertes moyennes par étape",
            "columns": ["Étape", "Perte moyenne", "Efficacité moyenne"],
            "rows": [
                [
                    _fr_stage(row.get("stage")),
                    f"{float(row.get('avg_loss_pct', 0.0) or 0.0):.1f} %",
                    f"{float(row.get('avg_efficiency_pct', 0.0) or 0.0):.1f} %",
                ]
                for row in rows
            ],
        }

    top_loss_rows = _top_loss_rows(sql_payload)
    if top_loss_rows:
        return {
            "type": "table",
            "title": "Lots avec les pertes les plus élevées",
            "columns": ["Lot", "Produit", "Perte", "Efficacité"],
            "rows": [
                [
                    str(row.get("batch_ref") or ""),
                    _fr_product(row.get("product")),
                    f"{float(row.get('loss_pct', 0.0) or 0.0):.1f} %",
                    f"{float(row.get('efficiency_pct', 0.0) or 0.0):.1f} %",
                ]
                for row in top_loss_rows
            ],
        }

    if sql_payload.get("parcels_list") is not None:
        rows = sql_payload.get("parcels_list") or []
        return {
            "type": "table",
            "title": "Parcelles enregistrées",
            "columns": ["Parcelle", "Surface", "Culture", "Membre"],
            "rows": [
                [
                    str(row.get("parcel_name") or ""),
                    f"{float(row.get('surface_ha', 0.0)):.2f} ha",
                    str(row.get("main_culture") or ""),
                    str(row.get("member_name") or ""),
                ]
                for row in rows
            ],
        }

    if sql_payload.get("collections_summary") is not None:
        rows = sql_payload.get("collections_summary") or []
        return {
            "type": "table",
            "title": "Collectes par produit",
            "columns": ["Produit", "Quantité", "Enregistrements"],
            "rows": [
                [
                    _fr_product(row.get("product")),
                    f"{float(row.get('total_quantity_kg', 0.0)):.1f} kg",
                    int(row.get("records", 0) or 0),
                ]
                for row in rows
            ],
        }

    return None


def _compose_chart_block(*, pack: EvidencePack, sql_payload: dict[str, Any]) -> dict[str, Any] | None:
    if pack.plan.answer_type == "chart_stock_multi":
        rows = sql_payload.get("current_stock") or []
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Stock total / réservé / disponible par produit",
            "x_key": "product",
            "y_key": "available_stock_kg",
            "data": [
                {
                    "product": _fr_product(row.get("product")),
                    "total_stock_kg": round(float(row.get("total_stock_kg", 0.0) or 0.0), 2),
                    "reserved_in_lots_kg": round(float(row.get("reserved_in_lots_kg", 0.0) or 0.0), 2),
                    "available_stock_kg": round(float(row.get("available_stock_kg", 0.0) or 0.0), 2),
                }
                for row in rows
            ],
            "series": ["total_stock_kg", "reserved_in_lots_kg", "available_stock_kg"],
        }

    if pack.plan.answer_type == "chart_product_loss":
        rows = _product_loss_rows(sql_payload)
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Pertes par produit",
            "x_key": "product",
            "y_key": "avg_loss_pct",
            "data": rows,
        }

    if pack.plan.answer_type == "chart_lot_critical":
        rows = _critical_lot_rows(sql_payload=sql_payload, ml_payload=pack.ml, limit=pack.plan.limit or 5)
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Top lots critiques (perte, efficacité, signal ML)",
            "x_key": "batch_ref",
            "y_key": "loss_pct",
            "data": rows,
            "series": ["loss_pct", "efficiency_pct", "ml_score"],
        }

    if pack.plan.answer_type == "chart_low_efficiency_lots":
        rows = _low_efficiency_rows(sql_payload, limit=pack.plan.limit or 5)
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Lots les moins efficaces",
            "x_key": "batch_ref",
            "y_key": "efficiency_pct",
            "data": rows,
        }

    if pack.plan.answer_type == "chart_ml_anomaly_lots":
        rows = _ml_anomaly_rows(pack.ml, limit=pack.plan.limit or 5)
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Anomaly score ML par lot",
            "x_key": "lot_code",
            "y_key": "anomaly_score",
            "data": rows,
        }

    if pack.plan.answer_type == "chart_recommendation_risk":
        recs = pack.recommendations.get("actions") or []
        if not recs:
            return None
        grouped: dict[str, int] = {}
        for rec in recs:
            level = str(rec.get("priority") or rec.get("risk_level") or "UNKNOWN").upper()
            grouped[level] = grouped.get(level, 0) + 1
        data = [{"risk_level": level, "recommendation_count": count} for level, count in sorted(grouped.items(), key=lambda item: item[0])]
        if not data:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Recommandations par niveau de risque",
            "x_key": "risk_level",
            "y_key": "recommendation_count",
            "data": data,
        }

    if pack.plan.answer_type == "chart_stock":
        rows = sql_payload.get("current_stock") or []
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Stock actuel par produit",
            "x_key": "product",
            "y_key": "available_stock_kg",
            "data": [
                {
                    "product": _fr_product(row.get("product")),
                    "available_stock_kg": round(float(row.get("available_stock_kg", 0.0) or 0.0), 2),
                }
                for row in rows
            ],
        }

    if pack.plan.answer_type == "chart_stage_loss":
        rows = sql_payload.get("stage_efficiency_summary") or []
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Pertes moyennes par étape de transformation",
            "x_key": "stage",
            "y_key": "avg_loss_pct",
            "data": [
                {
                    "stage": _fr_stage(row.get("stage")),
                    "avg_loss_pct": round(float(row.get("avg_loss_pct", 0.0) or 0.0), 2),
                }
                for row in rows
            ],
        }

    if pack.plan.answer_type == "chart_lot_loss":
        rows = _top_loss_rows(sql_payload, limit=pack.plan.limit or 10)
        if not rows:
            return None
        return {
            "type": "chart",
            "chart_type": "bar",
            "title": "Lots avec les pertes les plus élevées",
            "x_key": "batch_ref",
            "y_key": "loss_pct",
            "data": [
                {
                    "batch_ref": str(row.get("batch_ref") or ""),
                    "loss_pct": round(float(row.get("loss_pct", 0.0) or 0.0), 2),
                }
                for row in rows
            ],
        }

    if not sql_payload.get("stage_loss_comparison"):
        return None
    rows = sql_payload.get("stage_loss_comparison") or []
    if len(rows) < 2:
        return None
    return {
        "type": "chart",
        "chart_type": "bar",
        "title": "Pertes par étape",
        "x_key": "stage",
        "y_key": "loss_pct",
        "data": [
            {
                "stage": str(row.get("stage_label") or ""),
                "loss_pct": round(float(row.get("avg_loss_pct", 0.0) or 0.0), 2),
            }
            for row in rows
        ],
    }


def _compose_recommendation_block(*, pack: EvidencePack) -> dict[str, Any] | None:
    actions = pack.recommendations.get("actions") or []
    if not actions:
        return None
    items = []
    for action in actions[:5]:
        if not isinstance(action, dict):
            continue
        ev = action.get("evidence") or []
        items.append(
            {
                "priority": str(action.get("priority") or "MEDIUM").upper(),
                "title": str(action.get("title") or "Action recommandée"),
                "action": str(action.get("action") or action.get("title") or ""),
                "reason": str(action.get("reason") or ""),
                "evidence": [str(item).split(":")[0] for item in ev if str(item).strip()],
                "evidence_details": [str(item) for item in ev if str(item).strip()],
                "affected_lot": action.get("related_batch"),
                "affected_product": action.get("related_product"),
                "affected_stage": action.get("related_stage"),
            }
        )
    if not items:
        return None
    return {
        "type": "recommendations",
        "title": "Actions recommandées",
        "items": items,
    }


def _compose_best_practice_block(*, pack: EvidencePack) -> dict[str, Any] | None:
    snippets = pack.rag.get("content_snippets") or []
    if not snippets:
        return None
    points = _best_practice_points(snippets[0])
    if not points:
        points = [snippets[0]]
    return {
        "type": "best_practices",
        "title": "Bonnes pratiques",
        "items": points[:5],
    }


def _extract_sql_rows(sql_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in sql_data.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            rows.extend(value)
    return rows


def _extract_sql_metrics(sql_data: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key, value in sql_data.items():
        if isinstance(value, (int, float)):
            metrics[key] = float(value)
    return metrics


def _ranking_rows(sql_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = sql_payload.get("top_farmers")
    if isinstance(rows, list):
        return rows
    return []


def _top_loss_rows(sql_payload: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    explicit = sql_payload.get("top_loss_batches")
    if isinstance(explicit, list) and explicit:
        return explicit[:limit]
    batches = sql_payload.get("batch_summary")
    if isinstance(batches, list) and batches:
        sorted_rows = sorted(
            [row for row in batches if isinstance(row, dict)],
            key=lambda row: float(row.get("loss_pct", 0.0) or 0.0),
            reverse=True,
        )
        return sorted_rows[:limit]
    return []


def _low_efficiency_rows(sql_payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows = sql_payload.get("batch_summary") or []
    if not isinstance(rows, list):
        return []
    ranked = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: float(row.get("efficiency_pct", 100.0) or 100.0),
    )
    return ranked[: max(1, int(limit or 5))]


def _product_loss_rows(sql_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = sql_payload.get("process_step_losses") or []
    if not isinstance(rows, list) or not rows:
        return []
    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        product = str(row.get("product") or "").strip() or "inconnu"
        bucket = grouped.setdefault(product, {"loss_sum": 0.0, "eff_sum": 0.0, "count": 0.0})
        bucket["loss_sum"] += float(row.get("loss_pct", 0.0) or 0.0)
        bucket["eff_sum"] += float(row.get("efficiency_pct", 0.0) or 0.0)
        bucket["count"] += 1.0
    data = []
    for product, agg in grouped.items():
        count = int(agg["count"] or 0)
        if count <= 0:
            continue
        data.append(
            {
                "product": _fr_product(product),
                "avg_loss_pct": round(agg["loss_sum"] / count, 2),
                "avg_efficiency_pct": round(agg["eff_sum"] / count, 2),
                "count": count,
            }
        )
    data.sort(key=lambda row: float(row.get("avg_loss_pct", 0.0) or 0.0), reverse=True)
    return data


def _critical_lot_rows(sql_payload: dict[str, Any], ml_payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    lots = _top_loss_rows(sql_payload, limit=max(1, int(limit or 5)))
    if not lots:
        return []
    ml_signal = str((ml_payload or {}).get("risk_level") or "").upper()
    ml_score = float((ml_payload or {}).get("anomaly_score", 0.0) or 0.0)
    data = []
    for row in lots:
        item = dict(row)
        item["ml_signal"] = ml_signal if ml_signal else "ML indisponible"
        item["ml_score"] = round(ml_score, 4)
        data.append(item)
    return data


def _ml_anomaly_rows(ml_payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows = (ml_payload or {}).get("ml_insight_summary") or (ml_payload or {}).get("max_anomaly_score_lot") or []
    if not isinstance(rows, list):
        return []
    data = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lot = row.get("lot_code") or row.get("batch_ref") or row.get("batch_id")
        if not lot:
            continue
        score = float(row.get("anomaly_score", 0.0) or 0.0)
        data.append({"lot_code": str(lot), "anomaly_score": round(score, 4)})
    data.sort(key=lambda item: float(item.get("anomaly_score", 0.0) or 0.0), reverse=True)
    return data[: max(1, int(limit or 5))]


def _extract_chart_limit(normalized: str) -> int | None:
    text = str(normalized or "")
    m = re.search(r"\btop\s*(\d+)\b", text)
    if m:
        return max(1, min(int(m.group(1)), 20))
    m = re.search(r"\b(\d+)\s+(?:lots?|produits?|etapes?|étapes?)\b", text)
    if m:
        return max(1, min(int(m.group(1)), 20))
    return None


def _best_practice_points(text: str) -> list[str]:
    content = str(text or "")
    parts = [item.strip(" .") for item in content.replace("\n", " ").split(",")]
    points = [part for part in parts if len(part) >= 8]
    return points


def _normalize_for_match(text: str) -> str:
    value = str(text or "").lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.split())


def _compact(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _warning_label(code: str) -> str:
    value = str(code or "").strip()
    mapping = {
        "NO_SQL_DATA": "Aucune donnée SQL exploitable n’a été trouvée.",
        "SQL_DATA_INCOMPLETE": "Les données SQL sont incomplètes.",
        "WEAK_RETRIEVAL": "Le contexte documentaire RAG est faible.",
        "MISSING_SQL_ROWS": "Des lignes attendues sont manquantes dans les données SQL.",
        "MISSING_RAG_EVIDENCE": "Aucune preuve RAG exploitable n’a été récupérée.",
        "MISSING_ML_EVIDENCE": "Aucune preuve ML exploitable n’a été récupérée.",
        "MISSING_RECOMMENDATION_EVIDENCE": "Aucune preuve de recommandation exploitable n’a été récupérée.",
        "RAG_CONTENT_MISSING": "Le contenu RAG attendu n’est pas présent dans la réponse.",
        "UNRELATED_BATCH_FALLBACK": "La réponse a tenté un fallback lots non pertinent.",
        "RECOMMENDATION_WITHOUT_EVIDENCE": "Une recommandation manque de preuves suffisantes.",
        "NUMERIC_CLAIMS_NOT_GROUNDED": "Certaines valeurs numériques ne sont pas correctement justifiées.",
        "MISSING_RAG_SOURCE": "Aucune source RAG fiable n’a été trouvée.",
        "MISSING_RECOMMENDATION_SOURCE": "Aucune source de recommandation n’a été trouvée.",
        "SQL_ML_CONTRADICTION": "Les signaux SQL et ML ne sont pas totalement cohérents.",
        "CONTRADICTORY_CONTEXT_POSSIBLE": "Des informations contradictoires peuvent exister dans les sources.",
        "INCOMPLETE_SQL_DATA": "Les données SQL sont incomplètes.",
    }
    if value in mapping:
        return mapping[value]
    if re.fullmatch(r"[A-Z0-9_]+", value):
        return "Un avertissement technique a été détecté. Voir les métadonnées pour le détail."
    return value


def _evidence_roles(pack: EvidencePack) -> list[str]:
    roles: list[str] = []
    if pack.sql.get("payload"):
        roles.append("SQL_FACTS")
    if pack.rag.get("chunks"):
        roles.append("RAG_EXPLANATION")
    if pack.ml:
        roles.append("ML_SIGNAL")
    if pack.recommendations.get("actions") or pack.recommendations.get("insufficient_evidence"):
        roles.append("RECOMMENDATION_ACTIONS")
    return roles


def _build_module_registry(*, sql_data: dict[str, Any], tables_used: set[str]) -> dict[str, dict[str, Any]]:
    modules = {
        "members": {"tables": ["members", "inputs"], "available": False, "rows": 0},
        "collections": {"tables": ["inputs"], "available": False, "rows": 0},
        "stocks": {"tables": ["stocks"], "available": False, "rows": 0},
        "parcels": {"tables": ["parcels", "pre_harvest_steps"], "available": False, "rows": 0},
        "lots": {"tables": ["batches", "process_steps"], "available": False, "rows": 0},
        "ml_logs": {"tables": ["ml_prediction_logs"], "available": False, "rows": 0},
        "recommendations": {"tables": ["recommendations"], "available": False, "rows": 0},
        "rag": {"tables": ["rag_documents", "rag_chunks"], "available": True, "rows": len(sql_data.get("process_step_losses", []))},
        "invoices": {"tables": ["commercial_invoices"], "available": False, "rows": 0},
        "commercial": {"tables": ["commercial_orders"], "available": False, "rows": 0},
        "finance": {"tables": ["treasury_transactions", "global_charges"], "available": False, "rows": 0},
    }

    for module, descriptor in modules.items():
        tables = set(descriptor.get("tables") or [])
        descriptor["available"] = bool(tables.intersection(tables_used))

    if isinstance(sql_data.get("members_list"), list):
        modules["members"]["rows"] = len(sql_data.get("members_list") or [])
    if isinstance(sql_data.get("top_farmers"), list):
        modules["members"]["rows"] = max(modules["members"]["rows"], len(sql_data.get("top_farmers") or []))
    if isinstance(sql_data.get("collections_summary"), list):
        modules["collections"]["rows"] = len(sql_data.get("collections_summary") or [])
    if isinstance(sql_data.get("current_stock"), list):
        modules["stocks"]["rows"] = len(sql_data.get("current_stock") or [])
    if isinstance(sql_data.get("invoices_summary"), list):
        modules["invoices"]["rows"] = len(sql_data.get("invoices_summary") or [])
        modules["invoices"]["available"] = True
    if isinstance(sql_data.get("commercial_orders"), list):
        modules["commercial"]["rows"] = len(sql_data.get("commercial_orders") or [])
        modules["commercial"]["available"] = True
    if isinstance(sql_data.get("finance_expenses"), list):
        fin = (sql_data.get("finance_expenses") or [{}])[0]
        modules["finance"]["rows"] = int(fin.get("treasury_count", 0) or 0) + int(fin.get("global_charge_count", 0) or 0)
        modules["finance"]["available"] = True

    return modules


def _fr_product(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "mango": "Mangue",
        "mangue": "Mangue",
        "peanut": "Arachide",
        "arachide": "Arachide",
        "millet": "Mil",
        "mil": "Mil",
        "bissap": "Bissap",
    }
    return mapping.get(raw, str(value or "Produit"))


def _fr_stage(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "drying": "séchage",
        "sechage": "séchage",
        "séchage": "séchage",
        "sorting": "tri",
        "tri": "tri",
        "cleaning": "nettoyage",
        "nettoyage": "nettoyage",
        "packaging": "emballage",
        "emballage": "emballage",
        "conditionnement": "emballage",
    }
    return mapping.get(raw, str(value or "étape"))
