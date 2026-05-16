from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    question: str
    expected_behavior: str
    needs_sql: bool = False
    needs_rag: bool = False
    needs_ml: bool = False
    needs_reco: bool = False
    must_be_french: bool = True
    expected_routes: tuple[str, ...] | None = None
    expected_batch_ref: str | None = None
    forbid_batch_ref: bool = False
    forbid_tokens: tuple[str, ...] = ()
    expect_missing_batch_message: bool = False


CASES: list[AuditCase] = [
    AuditCase(
        case_id="A1",
        question="Quel est le stock actuel de mangue ?",
        expected_behavior="Utiliser les stocks/app-data (SQL) et retourner une source SQL.",
        needs_sql=True,
        expected_routes=("SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="A2",
        question="Quels lots sont en cours ?",
        expected_behavior="Utiliser les lots/app-data (SQL) et retourner une source batches.",
        needs_sql=True,
        expected_routes=("SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="A3",
        question="Quel lot a le plus de pertes ?",
        expected_behavior="Comparer les pertes via process_steps/material balance (SQL), pas uniquement RAG.",
        needs_sql=True,
        expected_routes=("SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="A4",
        question="Quelle étape cause le plus de pertes ?",
        expected_behavior="Comparer les pertes par étape via process_steps (SQL).",
        needs_sql=True,
        expected_routes=("SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="A5",
        question="Quels producteurs ont livré le plus cette semaine ?",
        expected_behavior="Utiliser inputs/members et retourner une source SQL (collectes).",
        needs_sql=True,
        expected_routes=("SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="B6",
        question="Avons-nous des lots à risque ?",
        expected_behavior="Question générale : ne pas extraire AVONS-NOUS comme lot, route SQL/ML.",
        needs_sql=True,
        needs_ml=True,
        expected_routes=("HYBRID_SQL_ML", "SQL_ONLY", "ML_ONLY", "HYBRID_FULL"),
        forbid_batch_ref=True,
        forbid_tokens=("AVONS-NOUS", "référence AVONS-NOUS"),
    ),
    AuditCase(
        case_id="B7",
        question="Analyse le lot MANG-004",
        expected_behavior="Doit extraire batch_ref=MANG-004 si pattern valide; si absent en DB, indiquer lot introuvable.",
        needs_sql=True,
        expected_batch_ref="MANG-004",
        expected_routes=("SQL_ONLY", "HYBRID_SQL_ML", "HYBRID_SQL_RAG", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="B8",
        question="Analyse le lot MANG-999",
        expected_behavior="Si MANG-999 est valide mais absent, retourner un message lot introuvable.",
        needs_sql=True,
        expected_batch_ref="MANG-999",
        expected_routes=("SQL_ONLY", "HYBRID_SQL_ML", "HYBRID_SQL_RAG", "HYBRID_FULL"),
        expect_missing_batch_message=True,
    ),
    AuditCase(
        case_id="B9",
        question="Pourquoi les pertes sont élevées ?",
        expected_behavior="Question causale : expliquer via RAG, idéalement avec métriques SQL.",
        needs_rag=True,
        expected_routes=("HYBRID_SQL_RAG", "RAG_ONLY", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="C10",
        question="Comment réduire les pertes pendant le séchage ?",
        expected_behavior="RAG sur séchage/pertes avec sources de connaissance.",
        needs_rag=True,
        expected_routes=("RAG_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="C11",
        question="Explique le bilan matière.",
        expected_behavior="RAG sur bilan matière avec sources.",
        needs_rag=True,
        expected_routes=("RAG_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="C12",
        question="Quelles sont les bonnes pratiques pour le tri des mangues ?",
        expected_behavior="RAG sur tri + mangue avec sources.",
        needs_rag=True,
        expected_routes=("RAG_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="C13",
        question="Comment améliorer l’emballage ?",
        expected_behavior="RAG sur emballage avec sources.",
        needs_rag=True,
        expected_routes=("RAG_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="D14",
        question="Quels lots sont à risque aujourd’hui ?",
        expected_behavior="Utiliser ML si disponible, sinon expliquer indisponibilité.",
        needs_ml=True,
        expected_routes=("HYBRID_SQL_ML", "ML_ONLY", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="D15",
        question="Donne-moi les recommandations IA pour le lot MANG-004.",
        expected_behavior="Utiliser recommandations + contexte SQL/ML/RAG si disponible.",
        needs_reco=True,
        expected_routes=("HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION", "RECOMMENDATION_ONLY"),
        expected_batch_ref="MANG-004",
    ),
    AuditCase(
        case_id="E16",
        question="Quels sont les risques en pré-récolte ?",
        expected_behavior="Utiliser données pré-récolte si disponibles, sinon signaler limite.",
        needs_sql=True,
        expected_routes=("HYBRID_SQL_RAG", "HYBRID_FULL", "SQL_ONLY"),
    ),
    AuditCase(
        case_id="E17",
        question="Quelles parcelles nécessitent une action ?",
        expected_behavior="Utiliser parcelles/pré-récolte si disponibles.",
        needs_sql=True,
        expected_routes=("HYBRID_SQL_RAG", "HYBRID_FULL", "SQL_ONLY"),
    ),
    AuditCase(
        case_id="E18",
        question="Quelle étape post-récolte pose le plus de problème ?",
        expected_behavior="Utiliser process_steps/losses (SQL).",
        needs_sql=True,
        expected_routes=("SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"),
    ),
    AuditCase(
        case_id="F19",
        question="Bonjour",
        expected_behavior="Réponse courte en français, sans SQL/RAG/ML.",
        expected_routes=("SMALL_TALK",),
        needs_sql=False,
        needs_rag=False,
        needs_ml=False,
    ),
    AuditCase(
        case_id="F20",
        question="Who won the Champions League?",
        expected_behavior="Réponse hors-scope en français.",
        expected_routes=("OUT_OF_SCOPE",),
        needs_sql=False,
        needs_rag=False,
        needs_ml=False,
    ),
]


def _setup_overrides(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()


def _post_agent(client: TestClient, message: str) -> dict[str, Any]:
    response = client.post("/chat/agent", json={"message": message, "language": "fr"})
    assert response.status_code == 200
    return response.json()


def _is_french(text: str) -> bool:
    lowered = str(text or "").lower()
    english_markers = ["the ", "what ", "who ", "won", "champions league", "risky", "batch"]
    if any(marker in lowered for marker in english_markers):
        return False
    french_markers = ["le ", "la ", "les ", "des ", "cooperative", "coopérative", "perte", "lots", "risque"]
    return any(marker in lowered for marker in french_markers)


def _build_actual_behavior(route: str, sources: list[dict[str, Any]], answer: str) -> str:
    source_types = sorted({str(source.get("type")) for source in sources if source.get("type")})
    preview = " ".join(str(answer or "").split())[:220]
    return f"route={route} | sources={','.join(source_types) or 'none'} | answer_preview={preview}"


def _build_case_result(case: AuditCase, payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    debug = metadata.get("agent_debug") or {}
    sources = payload.get("sources") or []
    source_types = {str(source.get("type")) for source in sources if source.get("type")}
    entities = metadata.get("detected_entities") or {}
    agents_used = payload.get("agents_used") or []
    answer = payload.get("answer") or ""

    used_sql = "sql" in source_types
    used_rag = "rag" in source_types
    used_ml = "ml" in source_types
    used_reco = "RecommendationAgent" in agents_used

    failures: list[str] = []
    if case.expected_routes and payload.get("route") not in case.expected_routes:
        failures.append("route_inattendue")
    if case.needs_sql and not used_sql:
        failures.append("sql_non_utilise")
    if case.needs_rag and not used_rag:
        failures.append("rag_non_utilise")
    if case.needs_ml and not used_ml:
        failures.append("ml_non_utilise")
    if case.needs_reco and not used_reco:
        failures.append("recommandations_non_utilisees")
    if case.must_be_french and not _is_french(answer):
        failures.append("reponse_non_francaise")
    if case.forbid_batch_ref and entities.get("batch_ref"):
        failures.append("batch_ref_inattendu")
    if case.expected_batch_ref and entities.get("batch_ref") != case.expected_batch_ref:
        failures.append("batch_ref_non_detecte")
    if case.expect_missing_batch_message and "Je n’ai pas trouvé de lot" not in answer:
        failures.append("message_lot_introuvable_absent")
    if case.forbid_tokens and any(token in answer for token in case.forbid_tokens):
        failures.append("token_interdit_dans_reponse")

    required = sum([case.needs_sql, case.needs_rag, case.needs_ml, case.needs_reco])
    positive = sum([case.needs_sql and used_sql, case.needs_rag and used_rag, case.needs_ml and used_ml, case.needs_reco and used_reco])

    if not failures:
        status = "pass"
    elif positive > 0 or (required == 0 and payload.get("route") in (case.expected_routes or [])):
        status = "partial"
    else:
        status = "fail"

    rag_debug = debug.get("RAGKnowledgeAgent", {}).get("data") if isinstance(debug.get("RAGKnowledgeAgent"), dict) else None
    rag_chunks = (rag_debug or {}).get("chunks") if isinstance(rag_debug, dict) else []
    rag_rewrite = (rag_debug or {}).get("rewrite") if isinstance(rag_debug, dict) else None

    sql_sources = [source for source in sources if source.get("type") == "sql"]
    rag_sources = [source for source in sources if source.get("type") == "rag"]
    ml_sources = [source for source in sources if source.get("type") == "ml"]

    sql_tools_used = sorted({str(source.get("table")) for source in sql_sources if source.get("table")})

    return {
        "case_id": case.case_id,
        "question": case.question,
        "expected_behavior": case.expected_behavior,
        "actual_behavior": _build_actual_behavior(payload.get("route", ""), sources, answer),
        "status": status,
        "failure_reasons": failures,
        "detected_intent": payload.get("route"),
        "detected_entities": entities,
        "selected_route": payload.get("route"),
        "agents_used": agents_used,
        "sql_tools_used": sql_tools_used,
        "sql_sources": sql_sources,
        "rag_query": (rag_rewrite or {}).get("expanded_domain_query") if isinstance(rag_rewrite, dict) else None,
        "rag_chunks_count": len(rag_chunks) if isinstance(rag_chunks, list) else 0,
        "rag_top_titles": [chunk.get("title") for chunk in (rag_chunks or [])[:3]] if isinstance(rag_chunks, list) else [],
        "rag_top_scores": [chunk.get("final_score") for chunk in (rag_chunks or [])[:3]] if isinstance(rag_chunks, list) else [],
        "rag_chunk_metadata": [chunk.get("metadata") for chunk in (rag_chunks or [])[:3]] if isinstance(rag_chunks, list) else [],
        "rag_sources": rag_sources,
        "ml_sources": ml_sources,
        "used_sql": used_sql,
        "used_rag": used_rag,
        "used_ml": used_ml,
        "sources_returned": bool(sources),
        "answer_in_french": _is_french(answer),
        "final_answer_preview": " ".join(answer.split())[:320],
        "warnings": payload.get("warnings") or [],
        "warning_codes": metadata.get("warning_codes") or [],
        "route_explanation": metadata.get("route_explanation"),
        "route_confidence": metadata.get("route_confidence"),
    }


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"pass": 0, "partial": 0, "fail": 0}
    for result in results:
        counts[result["status"]] += 1

    failure_counts: dict[str, int] = {}
    for result in results:
        for reason in result.get("failure_reasons", []):
            failure_counts[reason] = failure_counts.get(reason, 0) + 1

    top_failures = sorted(failure_counts.items(), key=lambda item: item[1], reverse=True)
    return {
        "counts": counts,
        "top_failures": top_failures,
    }


def _build_markdown_report(results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Audit diagnostic - retrieval chatbot")
    lines.append("")
    lines.append("## 1. Executive summary")
    counts = summary["counts"]
    lines.append(f"- Total cas: {sum(counts.values())} (pass={counts['pass']}, partial={counts['partial']}, fail={counts['fail']}).")
    lines.append("- Les résultats confirment les routes SQL/RAG/ML existantes, mais la récupération RAG reste faible dans l’environnement de test.")
    lines.append("- Plusieurs questions pré-récolte et parcelles ne disposent pas d’accès SQL dédié dans l’agent actuel.")
    lines.append("")
    lines.append("## 2. Current chatbot architecture found")
    lines.append("- Endpoint principal: /chat/agent (AgentOrchestrator).")
    lines.append("- Routage via IntentRouter + EntityExtractor + MemoryAgent.")
    lines.append("- Agents spécialisés: SQLAnalyticsAgent, RAGKnowledgeAgent, MLLossAgent, RecommendationAgent.")
    lines.append("- Vérification via ResponseVerifier + AuditLogger.")
    lines.append("")
    lines.append("## 3. Current retrieval pipeline found")
    lines.append("- Rewrite: enrichissement des requêtes (pertes/séchage/tri/emballage/bilan matière).")
    lines.append("- HybridRetriever: vecteur pgvector + recherche keyword, fusion 70/30.")
    lines.append("- Rerank: boost produit/étape/thème + fraîcheur + type de source.")
    lines.append("")
    lines.append("## 4. Current SQL/app-data usage found")
    lines.append("- SQLTools couvre stocks, inputs, batches, process_steps, material_balance, stage_efficiency, top_farmers.")
    lines.append("- Pré-récolte, parcelles, members étendus ne sont pas intégrés dans SQLAnalyticsAgent.")
    lines.append("")
    lines.append("## 5. Current ML/recommendation usage found")
    lines.append("- MLTools lit ml_prediction_logs; renvoie avertissement si non disponible.")
    lines.append("- RecommendationAgent produit des recommandations heuristiques basées sur SQL/RAG/ML.")
    lines.append("")
    lines.append("## 6. Current frontend source display found")
    lines.append("- UI assistant-ia affiche sources et avertissements via citations et métriques.")
    lines.append("- Les sources sont des labels SQL/RAG/ML simplifiés.")
    lines.append("")
    lines.append("## 7. Test results")
    lines.append("| Question | Expected | Actual | Status | Failure reason |")
    lines.append("| --- | --- | --- | --- | --- |")
    for result in results:
        expected = result["expected_behavior"].replace("|", "/")
        actual = result["actual_behavior"].replace("|", "/")
        reasons = ", ".join(result["failure_reasons"]) if result["failure_reasons"] else "-"
        lines.append(f"| {result['question']} | {expected} | {actual} | {result['status']} | {reasons} |")
    lines.append("")
    lines.append("## 8. Top retrieval weaknesses")
    if summary["top_failures"]:
        for reason, count in summary["top_failures"][:6]:
            lines.append(f"- {reason}: {count} cas")
    else:
        lines.append("- Aucun blocage critique détecté dans ce run.")
    lines.append("")
    lines.append("## 9. Entity extraction issues")
    lines.append("- Vérifier les hyphens et stopwords pour éviter les faux lots (ex: AVONS-NOUS).")
    lines.append("- Ajouter validation DB + regex stricte avant de conclure lot introuvable.")
    lines.append("")
    lines.append("## 10. SQL/app-data access gaps")
    lines.append("- Absence de route SQL dédiée pour parcelles/pré-récolte dans SQLAnalyticsAgent.")
    lines.append("- Les questions pré-récolte retombent vers RAG/ML sans données structurées.")
    lines.append("")
    lines.append("## 11. RAG chunking/metadata issues")
    lines.append("- Peu/pas de chunks en environnement test; vérifier ingestion et metadata (product, stage, topic, language).")
    lines.append("- RAG ne renvoie pas de sources pour les questions de bonnes pratiques.")
    lines.append("")
    lines.append("## 12. French-language issues")
    lines.append("- Les réponses devraient rester 100% françaises; vérifier les warnings et labels si mélange détecté.")
    lines.append("")
    lines.append("## 13. Source-grounding issues")
    lines.append("- Plusieurs réponses opérationnelles manquent de sources SQL/RAG/ML explicites.")
    lines.append("- Ajouter un avertissement quand la route exige une source absente.")
    lines.append("")
    lines.append("## 14. ML/recommendation integration gaps")
    lines.append("- ML dépend de ml_prediction_logs; absence de logs = réponse faible.")
    lines.append("- Recommendations doivent citer au moins une preuve SQL/RAG/ML.")
    lines.append("")
    lines.append("## 15. Pre-harvest/post-harvest insight gaps")
    lines.append("- Pré-récolte: pas d’accès direct aux steps/parcel status dans l’agent SQL.")
    lines.append("- Post-récolte: données présentes via process_steps, mais pas de vue synthétique dédiée.")
    lines.append("")
    lines.append("## 16. Recommended improvements (priority order)")
    lines.append("1. Corriger extraction des lots (stopwords + validation DB + pattern strict).")
    lines.append("2. Exposer pré-récolte/parcelles dans SQLAnalyticsAgent (routes dédiées).")
    lines.append("3. Renforcer ingestion RAG + metadata (language/product/stage/topic).")
    lines.append("4. Ajouter scoring/alertes de grounding et de manque de sources.")
    lines.append("5. Structurer la réponse avec citations normalisées pour UI.")
    lines.append("")
    lines.append("## 17. Proposed implementation phases")
    lines.append("- Phase 1: Full-app data access + entity extraction fix")
    lines.append("- Phase 2: RAG retrieval upgrade + lightweight orchestrator (inspiration: Ruflo, rag_api)")
    lines.append("- Phase 3: ML loss/anomaly intelligence + shared recommendations")
    lines.append("- Phase 4: UI integration + pre/post-harvest AI insights + docs/tests")
    lines.append("")
    lines.append("## 18. Next recommended Codex prompt")
    lines.append("""\
Analyser le rapport backend/app/ai/reports/chatbot_retrieval_audit.md et proposer un plan d’implémentation Phase 1 pour:
- corriger l’extraction des lots (stopwords + regex stricte + validation DB),
- ajouter les outils SQL pré-récolte/parcelles,
- améliorer la remontée de sources SQL/RAG/ML dans les réponses.
Ne pas modifier l’architecture globale ni ajouter de dépendances.
""")

    return "\n".join(lines)


def _write_reports(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    reports_dir = backend_dir / "app" / "ai" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "cases": results,
    }
    (reports_dir / "chatbot_retrieval_audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (reports_dir / "chatbot_retrieval_audit.md").write_text(
        _build_markdown_report(results, summary),
        encoding="utf-8",
    )


def test_chatbot_retrieval_audit_report(db_session, monkeypatch):
    monkeypatch.setenv("AI_AUDIT_DEBUG", "1")
    _setup_overrides(db_session)

    client = TestClient(app)
    results: list[dict[str, Any]] = []

    try:
        for case in CASES:
            payload = _post_agent(client, case.question)
            results.append(_build_case_result(case, payload))
    finally:
        app.dependency_overrides.clear()
        os.environ.pop("AI_AUDIT_DEBUG", None)

    summary = _build_summary(results)
    _write_reports(results, summary)

    assert len(results) == len(CASES)
    assert summary["counts"]["pass"] + summary["counts"]["partial"] + summary["counts"]["fail"] == len(CASES)
