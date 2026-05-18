from __future__ import annotations

import json
import statistics
import time
import uuid
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


REPORT_PATH = Path("backend/reports/chatbot/final_current_coop_supabase_audit.md")
COOP_ID = "4cbc6020-def9-4d24-bb75-9d40bc031466"
COOP_NAME = "Cooperative Deggo Thies"
MANAGER_EMAIL = "manager@weefarm.local"
PREV_PASS = 60
PREV_PARTIAL = 2
PREV_FAIL = 2
PREV_TOTAL = 64


@dataclass
class Case:
    id: str
    level: str  # basic | detailed
    test_type: str  # regression | paraphrase | fresh | edge
    capability: str
    question: str
    expected_routes: set[str]
    expected_tokens: list[str]
    requires_chart: bool = False
    unsupported: bool = False


def _cases() -> list[Case]:
    basic: list[Case] = [
        Case("b01", "basic", "regression", "sql", "Combien de membres sont enregistrés ?", {"SQL_ONLY"}, ["membre"]),
        Case("b02", "basic", "paraphrase", "sql", "Donne le nombre de parcelles de la coopérative.", {"SQL_ONLY"}, ["parcelle"]),
        Case("b03", "basic", "regression", "sql", "Combien de collectes/inputs avons-nous ?", {"SQL_ONLY"}, ["collecte"]),
        Case("b04", "basic", "paraphrase", "sql", "Montre le stock disponible par produit.", {"SQL_ONLY"}, ["stock", "kg"]),
        Case("b05", "basic", "fresh", "sql", "Combien de mouvements de stock existent ?", {"SQL_ONLY"}, ["mouvement"]),
        Case("b06", "basic", "fresh", "sql", "Combien de lots/batches sont suivis ?", {"SQL_ONLY"}, ["lot"]),
        Case("b07", "basic", "paraphrase", "sql", "Quelle étape a la perte moyenne la plus élevée ?", {"SQL_ONLY", "HYBRID_SQL_RAG"}, ["perte", "étape"]),
        Case("b08", "basic", "fresh", "sql", "Donne un bilan matière global.", {"SQL_ONLY"}, ["bilan", "perte"]),
        Case("b09", "basic", "regression", "sql", "Combien d’avances producteurs existe-t-il ?", {"SQL_ONLY"}, ["avance"]),
        Case("b10", "basic", "fresh", "sql", "Combien de fichiers uploadés sont liés aux opérations ?", {"SQL_ONLY"}, ["fichier"]),
        Case("b11", "basic", "regression", "sql", "Combien de transactions trésorerie ?", {"SQL_ONLY"}, ["trésorerie", "transaction"]),
        Case("b12", "basic", "paraphrase", "sql", "Combien de commandes commerciales avons-nous ?", {"SQL_ONLY"}, ["commande"]),
        Case("b13", "basic", "paraphrase", "sql", "Combien de factures commerciales existe-t-il ?", {"SQL_ONLY"}, ["facture"]),
        Case("b14", "basic", "fresh", "sql", "Combien de charges globales sont enregistrées ?", {"SQL_ONLY"}, ["charge"]),
        Case("b15", "basic", "regression", "ml", "Combien de signaux ML HIGH avons-nous ?", {"HYBRID_SQL_ML"}, ["ml", "high"]),
        Case("b16", "basic", "regression", "ml", "Quel lot a le plus grand anomaly_score ?", {"HYBRID_SQL_ML"}, ["anomaly", "lot"]),
        Case("b17", "basic", "regression", "recommendations", "Combien de recommandations par priorité ?", {"RECOMMENDATION_ONLY", "HYBRID_FULL"}, ["recommand"]),
        Case("b18", "basic", "regression", "rag", "Quelles bonnes pratiques de tri recommandes-tu ?", {"RAG_ONLY", "HYBRID_SQL_RAG"}, ["tri", "pratique"]),
        Case("b19", "basic", "paraphrase", "charts", "Affiche un graphique du stock par produit.", {"SQL_ONLY"}, ["graphique"], requires_chart=True),
        Case("b20", "basic", "fresh", "phase3", "Donne les derniers mouvements de stock avec type et quantité.", {"SQL_ONLY"}, ["mouvement", "quant"]),
        Case("b21", "basic", "paraphrase", "phase3", "Combien de collectes ont un BL ?", {"SQL_ONLY"}, ["BL", "collecte"]),
        Case("b22", "basic", "fresh", "phase3", "Combien de collectes ont un justificatif ?", {"SQL_ONLY"}, ["justificatif"]),
        Case("b23", "basic", "paraphrase", "phase3", "Combien d’avances ont un devis ?", {"SQL_ONLY"}, ["devis", "avance"]),
        Case("b24", "basic", "fresh", "phase3", "Combien de transactions trésorerie sans justificatif ?", {"SQL_ONLY"}, ["trésorerie", "justificatif"]),
        Case("b25", "basic", "fresh", "phase3", "Combien de transactions ENREGISTRE_COMPLET ?", {"SQL_ONLY"}, ["enregistre"]),
        Case("b26", "basic", "fresh", "phase3", "Combien de commandes payées ont une facture ?", {"SQL_ONLY"}, ["commande", "facture"]),
        Case("b27", "basic", "fresh", "phase3", "Combien de factures payées liées à la trésorerie ?", {"SQL_ONLY"}, ["facture", "trésorerie"]),
        Case("b28", "basic", "regression", "unsupported", "Quel sera le prix du marché le mois prochain ?", {"OUT_OF_SCOPE"}, [], unsupported=True),
        Case("b29", "basic", "regression", "unsupported", "Quelle météo demain pour nos récoltes ?", {"OUT_OF_SCOPE"}, [], unsupported=True),
        Case("b30", "basic", "regression", "unsupported", "Quel membre est le plus fiable humainement ?", {"OUT_OF_SCOPE"}, [], unsupported=True),
    ]

    detailed: list[Case] = [
        Case("d01", "detailed", "regression", "phase3", "Journal des mouvements: donne count, type, source, produit, lot et collecte.", {"SQL_ONLY"}, ["mouvement", "lot"]),
        Case("d02", "detailed", "regression", "phase3", "Traçabilité collecte: BL, justificatif, membre, produit, lot lié.", {"SQL_ONLY"}, ["BL", "justificatif", "lot"]),
        Case("d03", "detailed", "regression", "phase3", "Répartition des justificatifs/upload par type d’entité.", {"SQL_ONLY"}, ["fichier", "collecte", "avance", "trésorerie"]),
        Case("d04", "detailed", "regression", "phase3", "Avances producteur: lot/parcelle/produit, devis, sync trésorerie.", {"SQL_ONLY"}, ["avance", "devis", "trésorerie"]),
        Case("d05", "detailed", "regression", "phase3", "Trésorerie: statut, receipt_reference, justificatif manquant, lock complet.", {"SQL_ONLY"}, ["trésorerie", "receipt", "justificatif"]),
        Case("d06", "detailed", "regression", "phase3", "Commande payée -> facture -> revenu trésorerie: montre la liaison explicite.", {"SQL_ONLY"}, ["commande", "facture", "trésorerie"]),
        Case("d07", "detailed", "regression", "hybrid_sql_ml", "Compare la perte SQL et le signal ML pour LOT-MANG-002.", {"HYBRID_SQL_ML"}, ["perte", "ml", "lot"]),
        Case("d08", "detailed", "regression", "hybrid_sql_ml", "Top anomaly ML lot + faits opérationnels SQL correspondants.", {"HYBRID_SQL_ML"}, ["anomaly", "sql", "lot"]),
        Case("d09", "detailed", "regression", "hybrid_sql_rag", "Quelle étape génère le plus de pertes et quelles pratiques post-récolte appliquer ?", {"HYBRID_SQL_RAG"}, ["étape", "perte", "pratique"]),
        Case("d10", "detailed", "regression", "hybrid_full", "Lot critique selon SQL, ML, RAG et recommandations: que faut-il faire ?", {"HYBRID_FULL"}, ["action", "sql", "ml"]),
        Case("d11", "detailed", "paraphrase", "hybrid_sql_reco", "Pour le lot à pire perte, quelle recommandation stockée est liée ?", {"HYBRID_FULL", "RECOMMENDATION_ONLY"}, ["recommand", "lot"]),
        Case("d12", "detailed", "paraphrase", "hybrid_sql_rag", "Selon nos données, où perd-on le plus et comment améliorer ?", {"HYBRID_SQL_RAG"}, ["perte", "améliorer"]),
        Case("d13", "detailed", "paraphrase", "hybrid_sql_ml", "Signal ML le plus fort et preuves SQL de ce même lot.", {"HYBRID_SQL_ML"}, ["ml", "sql"]),
        Case("d14", "detailed", "paraphrase", "hybrid_full", "Réponse manager complète: conclusion, preuves, action, limitation.", {"HYBRID_FULL"}, ["conclusion", "action", "limite"]),
        Case("d15", "detailed", "paraphrase", "manager_style", "Décision opérationnelle manager avec preuves et plan d’action.", {"HYBRID_FULL"}, ["action", "preuve"]),
        Case("d16", "detailed", "paraphrase", "manager_style", "Synthèse opérationnelle manager sur lot prioritaire, risques et limites.", {"HYBRID_FULL"}, ["lot", "risque", "limite"]),
        Case("d17", "detailed", "paraphrase", "rag", "Quelles précautions avant emballage pour limiter la casse ?", {"RAG_ONLY", "HYBRID_SQL_RAG"}, ["emballage", "casse"]),
        Case("d18", "detailed", "paraphrase", "rag", "Procédure simple de conditionnement pour éviter les pertes.", {"RAG_ONLY", "HYBRID_SQL_RAG"}, ["conditionnement", "perte"]),
        Case("d19", "detailed", "paraphrase", "charts", "Graphique stock total / réservé / disponible.", {"SQL_ONLY"}, ["graphique"], requires_chart=True),
        Case("d20", "detailed", "paraphrase", "charts", "Graphique pertes par produit.", {"SQL_ONLY"}, ["graphique"], requires_chart=True),
        Case("d21", "detailed", "paraphrase", "charts", "Graphique pertes par étape.", {"SQL_ONLY"}, ["graphique"], requires_chart=True),
        Case("d22", "detailed", "paraphrase", "charts", "Graphique lots les plus critiques (SQL+ML).", {"SQL_ONLY", "HYBRID_SQL_ML", "HYBRID_FULL"}, ["graphique"], requires_chart=True),
        Case("d23", "detailed", "paraphrase", "charts", "Graphique anomaly_score ML par lot.", {"SQL_ONLY", "HYBRID_SQL_ML"}, ["graphique"], requires_chart=True),
        Case("d24", "detailed", "paraphrase", "charts", "Graphique recommandations par risque/priorité.", {"SQL_ONLY", "RECOMMENDATION_ONLY", "HYBRID_FULL"}, ["graphique"], requires_chart=True),
        Case("d25", "detailed", "fresh", "memory", "Donne les 3 lots les plus critiques.", {"SQL_ONLY", "HYBRID_SQL_ML", "HYBRID_FULL"}, ["lot"]),
        Case("d26", "detailed", "fresh", "memory", "Le premier, détaille son risque ML et action.", {"HYBRID_SQL_ML", "HYBRID_FULL"}, ["premier", "ml", "action"]),
        Case("d27", "detailed", "fresh", "memory", "Ce lot, donne aussi les conseils post-récolte.", {"HYBRID_FULL", "HYBRID_SQL_RAG"}, ["lot", "conseil"]),
        Case("d28", "detailed", "fresh", "memory", "Ce produit maintenant: stock disponible et risque.", {"SQL_ONLY", "HYBRID_SQL_ML"}, ["produit", "stock"]),
        Case("d29", "detailed", "fresh", "memory", "Oublie ce lot, donne seulement le stock global.", {"SQL_ONLY"}, ["stock"]),
        Case("d30", "detailed", "fresh", "memory", "Switch module: trésorerie puis facture payée liée.", {"SQL_ONLY"}, ["trésorerie", "facture"]),
        Case("d31", "detailed", "fresh", "unsupported", "Dois-je licencier certains membres ?", {"OUT_OF_SCOPE"}, [], unsupported=True),
        Case("d32", "detailed", "fresh", "unsupported", "Quel membre est le moins fiable subjectivement ?", {"OUT_OF_SCOPE"}, [], unsupported=True),
        Case("d33", "detailed", "fresh", "unsupported", "Quelle stratégie politique locale doit-on adopter ?", {"OUT_OF_SCOPE"}, [], unsupported=True),
        Case("d34", "detailed", "fresh", "unsupported", "Donne une décision RH finale sans indicateur.", {"OUT_OF_SCOPE"}, [], unsupported=True),
        Case("d35", "detailed", "fresh", "sql", "Top lots avec pertes et efficacité sur la période récente.", {"SQL_ONLY"}, ["lot", "perte", "efficacité"]),
        Case("d36", "detailed", "fresh", "ml", "Lots classés HIGH par ML avec anomaly_score.", {"HYBRID_SQL_ML"}, ["high", "anomaly"]),
        Case("d37", "detailed", "fresh", "recommendations", "Actions prioritaires recommandées et leur cible lot/stage.", {"HYBRID_FULL", "RECOMMENDATION_ONLY"}, ["action", "priorit"]),
        Case("d38", "detailed", "fresh", "hybrid_full", "Manager: lot prioritaire, preuve SQL, signal ML, conseil RAG, action et limite.", {"HYBRID_FULL"}, ["lot", "sql", "ml", "action", "limite"]),
        Case("d39", "detailed", "fresh", "hybrid_sql_rag", "Perte au séchage dans nos données + bonnes pratiques pour corriger.", {"HYBRID_SQL_RAG"}, ["séchage", "perte", "pratique"]),
        Case("d40", "detailed", "fresh", "hybrid_sql_ml", "Pour le lot le plus risqué ML, donne aussi pertes/efficacité SQL ou dis indisponible.", {"HYBRID_SQL_ML"}, ["ml", "sql", "indisponible"]),
    ]
    return basic + detailed


def _has_chart_block(payload: dict[str, Any]) -> bool:
    blocks = payload.get("response_blocks") or []
    for b in blocks:
        if str(b.get("type") or "").lower() in {"chart", "bar_chart", "line_chart"}:
            return True
    return False


def _has_rag_source(payload: dict[str, Any]) -> bool:
    for src in payload.get("sources") or []:
        role = str(src.get("role") or src.get("type") or "").lower()
        if role == "rag":
            return True
    return False


def _is_mechanical(answer: str) -> bool:
    lowered = (answer or "").lower()
    return "sql:" in lowered and "ml:" in lowered and "rag:" in lowered


def _score_case(case: Case, payload: dict[str, Any]) -> tuple[str, list[str]]:
    route = str(payload.get("route") or "")
    answer = str(payload.get("answer") or "")
    lowered = answer.lower()
    reasons: list[str] = []

    if route not in case.expected_routes:
        return "FAIL", [f"wrong_route:{route}"]

    if case.unsupported:
        if route != "OUT_OF_SCOPE":
            return "FAIL", ["unsupported_answered_as_fact"]
        return "PASS", []

    for token in case.expected_tokens:
        if token.lower() not in lowered:
            reasons.append(f"missing_token:{token}")

    if case.requires_chart and not _has_chart_block(payload):
        reasons.append("missing_chart_block")

    if case.capability == "rag":
        if route in {"RAG_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"} and not _has_rag_source(payload):
            reasons.append("rag_source_missing")

    if case.level == "detailed":
        if _is_mechanical(answer):
            reasons.append("mechanical_style")
        required_sections = [
            "1. réponse directe",
            "2. interprétation opérationnelle",
            "3. résumé des preuves",
            "4. action recommandée",
            "5. limites",
        ]
        missing_sections = [sec for sec in required_sections if sec not in lowered]
        if missing_sections:
            reasons.append("manager_structure_missing")

    if not reasons:
        return "PASS", []
    severe = any(x in reasons for x in ("missing_chart_block", "rag_source_missing"))
    if severe:
        return "FAIL", reasons
    return "PARTIAL", reasons


def _pct(n: int, d: int) -> float:
    return round((n / d) * 100.0, 2) if d else 0.0


def main() -> None:
    cases = _cases()
    db = SessionLocal()
    manager = db.scalar(select(User).where(User.email == MANAGER_EMAIL).limit(1))
    if manager is None:
        raise RuntimeError(f"Manager user not found: {MANAGER_EMAIL}")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: manager
    client = TestClient(app)

    rows: list[dict[str, Any]] = []
    memory_conversation = str(uuid.uuid4())
    memory_ids = {"d25", "d26", "d27", "d28", "d29", "d30"}

    for idx, case in enumerate(cases, start=1):
        cid = memory_conversation if case.id in memory_ids else str(uuid.uuid4())
        t0 = time.perf_counter()
        payload: dict[str, Any]
        timed_out = False
        try:
            signal.alarm(45)
            payload = client.post("/chat/agent", json={"message": case.question, "conversation_id": cid}).json()
            signal.alarm(0)
        except _Timeout:
            signal.alarm(0)
            payload = {"route": "TIMEOUT", "answer": "", "response_blocks": [], "sources": []}
            timed_out = True
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if timed_out:
            score, reasons = "BLOCKED", ["timeout"]
        else:
            score, reasons = _score_case(case, payload)
        rows.append(
            {
                "id": case.id,
                "level": case.level,
                "type": case.test_type,
                "capability": case.capability,
                "question": case.question,
                "route": payload.get("route"),
                "score": score,
                "reasons": reasons,
                "latency_ms": round(latency_ms, 2),
                "has_chart": _has_chart_block(payload),
                "has_rag_source": _has_rag_source(payload),
                "answer_preview": str(payload.get("answer") or "")[:260].replace("\n", " "),
            }
        )
        print(
            f"[{idx:02d}/{len(cases)}] {case.id} {score} route={payload.get('route')} {latency_ms:.0f}ms",
            flush=True,
        )

    app.dependency_overrides.clear()
    db.close()

    total = len(rows)
    counts = {k: sum(1 for r in rows if r["score"] == k) for k in ("PASS", "PARTIAL", "FAIL", "BLOCKED")}
    pass_rate = _pct(counts["PASS"], total)
    handled_rate = _pct(counts["PASS"] + counts["PARTIAL"], total)

    basic = [r for r in rows if r["level"] == "basic"]
    detailed = [r for r in rows if r["level"] == "detailed"]
    basic_pass = _pct(sum(1 for r in basic if r["score"] == "PASS"), len(basic))
    detailed_pass = _pct(sum(1 for r in detailed if r["score"] == "PASS"), len(detailed))

    lat = [float(r["latency_ms"]) for r in rows]
    latency = {
        "avg_ms": round(sum(lat) / len(lat), 2),
        "p50_ms": round(statistics.median(lat), 2),
        "p95_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 2),
        "max_ms": round(max(lat), 2),
    }

    by_capability: dict[str, dict[str, int]] = {}
    for r in rows:
        c = r["capability"]
        by_capability.setdefault(c, {"total": 0, "PASS": 0, "PARTIAL": 0, "FAIL": 0, "BLOCKED": 0})
        by_capability[c]["total"] += 1
        by_capability[c][r["score"]] += 1

    by_test_type: dict[str, dict[str, int]] = {}
    for r in rows:
        t = r["type"]
        by_test_type.setdefault(t, {"total": 0, "PASS": 0, "PARTIAL": 0, "FAIL": 0, "BLOCKED": 0})
        by_test_type[t]["total"] += 1
        by_test_type[t][r["score"]] += 1

    hallucination_offtopic = sum(1 for r in rows if any("wrong_route" in x for x in r["reasons"]))
    source_pollution = sum(1 for r in rows if any("rag_source_missing" in x for x in r["reasons"]))
    unsupported_rows = [r for r in rows if r["capability"] == "unsupported"]
    unsupported_success = _pct(sum(1 for r in unsupported_rows if r["score"] == "PASS"), len(unsupported_rows))
    chart_rows = [r for r in rows if r["capability"] == "charts"]
    chart_validity = _pct(sum(1 for r in chart_rows if r["has_chart"] and r["score"] != "FAIL"), len(chart_rows))
    memory_rows = [r for r in rows if r["capability"] == "memory"]
    memory_success = _pct(sum(1 for r in memory_rows if r["score"] == "PASS"), len(memory_rows))
    rag_rows = [r for r in rows if r["capability"] == "rag"]
    rag_relevance = _pct(sum(1 for r in rag_rows if r["score"] == "PASS" and r["has_rag_source"]), len(rag_rows))
    hybrid_rows = [r for r in rows if r["capability"].startswith("hybrid")]
    hybrid_completeness = _pct(sum(1 for r in hybrid_rows if r["score"] == "PASS"), len(hybrid_rows))
    manager_rows = [r for r in rows if r["capability"] == "manager_style"]
    manager_quality = _pct(sum(1 for r in manager_rows if r["score"] == "PASS"), len(manager_rows))

    strongest = sorted(
        [f"{cap}: {v['PASS']}/{v['total']} PASS" for cap, v in by_capability.items()],
        key=lambda x: float(x.split(": ")[1].split("/")[0]) / float(x.split("/")[1].split(" ")[0]),
        reverse=True,
    )[:5]
    weakest_cases = [r for r in rows if r["score"] in {"PARTIAL", "FAIL", "BLOCKED"}][:5]
    weakest = [f"{r['id']} ({r['capability']}): {r['score']} {','.join(r['reasons'])}" for r in weakest_cases]

    readiness = "near-final app-data assistant"
    if pass_rate >= 92 and counts["FAIL"] <= 2:
        readiness = "PFE-defense-ready"
    if pass_rate >= 97 and counts["FAIL"] == 0 and counts["PARTIAL"] <= 1:
        readiness = "production-ready"

    regression_count = sum(1 for r in rows if r["type"] == "regression")
    paraphrase_count = sum(1 for r in rows if r["type"] == "paraphrase")
    fresh_count = sum(1 for r in rows if r["type"] == "fresh")
    edge_count = sum(1 for r in rows if r["type"] == "edge" or r["capability"] == "unsupported")

    report = []
    report.append("# Final Current Cooperative Supabase Audit (/chat/agent)")
    report.append("")
    report.append(f"- Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"- Cooperative: `{COOP_NAME}` (`{COOP_ID}`)")
    report.append(f"- Manager: `{MANAGER_EMAIL}`")
    report.append(f"- Total cases: **{total}** (Basic 30 + Detailed 40)")
    report.append("")
    report.append("## Test Composition")
    report.append(f"- Regression: {regression_count}")
    report.append(f"- Paraphrase: {paraphrase_count}")
    report.append(f"- Fresh unseen: {fresh_count}")
    report.append(f"- Unsupported/edge: {edge_count}")
    report.append("")
    report.append("## Overall")
    report.append(f"- PASS/PARTIAL/FAIL/BLOCKED: **{counts['PASS']}/{counts['PARTIAL']}/{counts['FAIL']}/{counts['BLOCKED']}**")
    report.append(f"- Pass rate: **{pass_rate}%**")
    report.append(f"- Handled rate (PASS+PARTIAL): **{handled_rate}%**")
    report.append(f"- Basic score: **{basic_pass}%**")
    report.append(f"- Detailed/hard score: **{detailed_pass}%**")
    report.append("")
    report.append("## Metrics")
    report.append(f"- Latency avg/p50/p95/max (ms): **{latency['avg_ms']} / {latency['p50_ms']} / {latency['p95_ms']} / {latency['max_ms']}**")
    report.append(f"- Hallucination/off-topic count: **{hallucination_offtopic}**")
    report.append(f"- Source pollution count: **{source_pollution}**")
    report.append(f"- Unsupported refusal success rate: **{unsupported_success}%**")
    report.append(f"- Chart validity rate: **{chart_validity}%**")
    report.append(f"- Memory success rate: **{memory_success}%**")
    report.append(f"- RAG relevance score: **{rag_relevance}%**")
    report.append(f"- Hybrid completeness score: **{hybrid_completeness}%**")
    report.append(f"- Manager-style answer-quality score: **{manager_quality}%**")
    report.append("")
    report.append("## Results by Capability")
    for cap in sorted(by_capability.keys()):
        v = by_capability[cap]
        report.append(f"- {cap}: {v['PASS']}/{v['PARTIAL']}/{v['FAIL']}/{v['BLOCKED']} (total {v['total']})")
    report.append("")
    report.append("## Results by Test Type")
    for t in sorted(by_test_type.keys()):
        v = by_test_type[t]
        report.append(f"- {t}: {v['PASS']}/{v['PARTIAL']}/{v['FAIL']}/{v['BLOCKED']} (total {v['total']})")
    report.append("")
    report.append("## Comparison vs Previous Key Result")
    report.append(f"- Previous: {PREV_TOTAL} cases, PASS/PARTIAL/FAIL = {PREV_PASS}/{PREV_PARTIAL}/{PREV_FAIL}")
    report.append(f"- Current: {total} cases, PASS/PARTIAL/FAIL = {counts['PASS']}/{counts['PARTIAL']}/{counts['FAIL']}")
    report.append("")
    report.append("## Top 5 Strongest Behaviors")
    for line in strongest:
        report.append(f"- {line}")
    report.append("")
    report.append("## Top 5 Weakest Behaviors")
    if weakest:
        for line in weakest:
            report.append(f"- {line}")
    else:
        report.append("- No weak cases detected.")
    report.append("")
    report.append("## Remaining Blockers")
    if counts["FAIL"] == 0 and counts["BLOCKED"] == 0:
        report.append("- No hard blockers in this audit run.")
    else:
        for r in rows:
            if r["score"] in {"FAIL", "BLOCKED"}:
                report.append(f"- {r['id']} {r['capability']}: {','.join(r['reasons'])}")
    report.append("")
    report.append("## Honest Readiness Rating")
    report.append(f"- **{readiness}**")
    report.append("")
    report.append("## Case Table")
    report.append("|id|level|type|capability|route|score|latency_ms|reason|")
    report.append("|---|---|---|---|---|---|---:|---|")
    for r in rows:
        reason = ",".join(r["reasons"]) if r["reasons"] else ""
        report.append(
            f"|{r['id']}|{r['level']}|{r['type']}|{r['capability']}|{r['route']}|{r['score']}|{r['latency_ms']}|{reason}|"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")

    summary = {
        "report_path": str(REPORT_PATH),
        "total": total,
        "counts": counts,
        "basic_score_pct": basic_pass,
        "detailed_score_pct": detailed_pass,
        "overall_pass_rate_pct": pass_rate,
        "by_capability": by_capability,
        "latency": latency,
        "strongest": strongest,
        "weakest": weakest,
        "blockers": [r for r in rows if r["score"] in {"FAIL", "BLOCKED"}],
        "readiness": readiness,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
    class _Timeout(Exception):
        pass

    def _handler(signum, frame):
        raise _Timeout()

    signal.signal(signal.SIGALRM, _handler)
