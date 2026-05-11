from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import re
import statistics
import sys
from typing import Any

from fastapi.testclient import TestClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

REPORT_MD = ROOT / "reports" / "final_ai_validation_report.md"
REPORT_JSON = ROOT / "reports" / "final_ai_validation_report.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\-']+", (text or "").lower(), flags=re.UNICODE)


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _bleu_n(ref: str, hyp: str, n: int) -> float:
    rt = _tokenize(ref)
    ht = _tokenize(hyp)
    if not ht:
        return 0.0
    ref_ngrams = Counter(_ngrams(rt, n))
    hyp_ngrams = Counter(_ngrams(ht, n))
    if not hyp_ngrams:
        return 0.0
    overlap = 0
    total = 0
    for ng, c in hyp_ngrams.items():
        overlap += min(c, ref_ngrams.get(ng, 0))
        total += c
    precision = overlap / total if total else 0.0
    bp = 1.0
    if len(ht) < len(rt) and len(ht) > 0:
        bp = math.exp(1 - (len(rt) / len(ht)))
    return bp * precision


def _lcs_len(a: list[str], b: list[str]) -> int:
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        ai = a[i - 1]
        for j in range(1, n + 1):
            if ai == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def _rouge_n(ref: str, hyp: str, n: int) -> float:
    rt = _tokenize(ref)
    ht = _tokenize(hyp)
    ref_ng = Counter(_ngrams(rt, n))
    hyp_ng = Counter(_ngrams(ht, n))
    if not ref_ng:
        return 0.0
    overlap = sum(min(c, hyp_ng.get(ng, 0)) for ng, c in ref_ng.items())
    recall = overlap / sum(ref_ng.values()) if ref_ng else 0.0
    precision = overlap / sum(hyp_ng.values()) if hyp_ng else 0.0
    if recall + precision == 0:
        return 0.0
    return 2 * recall * precision / (recall + precision)


def _rouge_l(ref: str, hyp: str) -> float:
    rt = _tokenize(ref)
    ht = _tokenize(hyp)
    if not rt or not ht:
        return 0.0
    lcs = _lcs_len(rt, ht)
    recall = lcs / len(rt)
    precision = lcs / len(ht)
    if recall + precision == 0:
        return 0.0
    return 2 * recall * precision / (recall + precision)


def _compute_nlp_metrics(references: list[str], hypotheses: list[str]) -> dict[str, float]:
    bleu1 = statistics.mean(_bleu_n(r, h, 1) for r, h in zip(references, hypotheses)) if references else 0.0
    bleu2 = statistics.mean(_bleu_n(r, h, 2) for r, h in zip(references, hypotheses)) if references else 0.0
    bleu4 = statistics.mean(_bleu_n(r, h, 4) for r, h in zip(references, hypotheses)) if references else 0.0

    rouge1 = statistics.mean(_rouge_n(r, h, 1) for r, h in zip(references, hypotheses)) if references else 0.0
    rouge2 = statistics.mean(_rouge_n(r, h, 2) for r, h in zip(references, hypotheses)) if references else 0.0
    rougel = statistics.mean(_rouge_l(r, h) for r, h in zip(references, hypotheses)) if references else 0.0

    docs = references + hypotheses
    if docs:
        vec = TfidfVectorizer(min_df=1)
        mat = vec.fit_transform(docs)
        ref_mat = mat[: len(references)]
        hyp_mat = mat[len(references) :]
        sims = [float(cosine_similarity(ref_mat[i], hyp_mat[i])[0][0]) for i in range(len(references))]
        cosine_avg = statistics.mean(sims) if sims else 0.0
    else:
        cosine_avg = 0.0

    return {
        "bleu_1": round(bleu1, 4),
        "bleu_2": round(bleu2, 4),
        "bleu_4": round(bleu4, 4),
        "rouge_1": round(rouge1, 4),
        "rouge_2": round(rouge2, 4),
        "rouge_l": round(rougel, 4),
        "semantic_cosine_similarity": round(cosine_avg, 4),
    }


def _run_lightweight_nlp_eval(validation_questions: list[dict[str, Any]]) -> tuple[dict[str, float], list[dict[str, str]]]:
    db = SessionLocal()
    try:
        manager = db.scalars(select(User).where(User.role.in_([UserRole.MANAGER, UserRole.OWNER, UserRole.ADMIN]))).first()
        if not manager:
            return ({k: 0.0 for k in ["bleu_1", "bleu_2", "bleu_4", "rouge_1", "rouge_2", "rouge_l", "semantic_cosine_similarity"]}, [])

        app.dependency_overrides[get_current_user] = lambda: manager

        def _override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _override_db
        client = TestClient(app)
        sid = client.post("/chat/sessions", json={"title": "NLP Eval Final Report"}).json()["id"]

        refs: list[str] = []
        hyps: list[str] = []
        samples: list[dict[str, str]] = []
        for row in validation_questions:
            q = str(row.get("question", ""))
            ref = str(row.get("answer_text", ""))
            if not q or not ref:
                continue
            payload = client.post(f"/chat/sessions/{sid}/messages", json={"content": q}).json()
            hyp = str(payload.get("message", ""))
            refs.append(ref)
            hyps.append(hyp)
            if len(samples) < 5:
                samples.append({"question": q, "reference": ref[:220], "hypothesis": hyp[:220]})

        metrics = _compute_nlp_metrics(refs, hyps)
        return metrics, samples
    finally:
        app.dependency_overrides.clear()
        db.close()


def main() -> None:
    full = _load_json(ROOT / "reports" / "chatbot_full_platform_coverage_audit.json")
    unseen = _load_json(ROOT / "reports" / "chatbot_unseen_robustness_audit.json")
    baseline = _load_json(ROOT / "artifacts" / "chatbot_quality_audit.json")
    rag_bench = _load_json(ROOT / "artifacts" / "rag_benchmark_report.json")
    chat_val = _load_json(ROOT / "artifacts" / "chatbot_validation_audit.json")
    ml = _load_json(ROOT / "reports" / "ml_model_validation_report.json")

    perf_md = (ROOT / "reports" / "performance_summary.md").read_text(encoding="utf-8")
    rag_cov_md = (ROOT / "reports" / "full_rag_index_coverage_report.md").read_text(encoding="utf-8")
    integrity_md = (ROOT / "reports" / "demo_data_integrity_report.md").read_text(encoding="utf-8")

    full_summary = full["summary"]
    full_intent = full_summary["pass_rate_by_intent"]

    routing_accuracy = round(
        sum(1 for r in full["results"] if str(r.get("actual_intent", "")) in set(r.get("expected_intent", [])))
        / max(len(full["results"]), 1),
        4,
    )

    sql_fact_acc = round(float(chat_val["aggregate_metrics"].get("avg_factual_accuracy", 0.0)), 4)
    citation_rel = round(float(chat_val["aggregate_metrics"].get("avg_citation_relevance", 0.0)), 4)

    rb = rag_bench["summary"]
    rag_metrics = {
        "retrieval_relevance_score": round(float(rb.get("avg_retrieval_relevance_score", 0.0)), 4),
        "grounding_score": round(float(rb.get("avg_grounding_score", 0.0)), 4),
        "citation_relevance_score": citation_rel,
        "expected_chunk_coverage": round(float(rb.get("avg_expected_chunk_coverage", 0.0)), 4),
        "scope_purity_score": round(float(rb.get("avg_scope_purity_score", 0.0)), 4),
        "contamination_rate": round(float(rb.get("avg_contamination_rate", 0.0)), 4),
        "operational_priority_score": round(float(rb.get("avg_operational_priority_score", 0.0)), 4),
    }

    lat_sql = float(re.search(r"avg SQL_ONLY latency: ([0-9.]+)", perf_md).group(1))
    lat_hyb = float(re.search(r"avg HYBRID latency: ([0-9.]+)", perf_md).group(1))
    lat_rag = float(re.search(r"avg RAG_ONLY latency: ([0-9.]+)", perf_md).group(1))

    docs = int(re.search(r"- total_documents: ([0-9]+)", rag_cov_md).group(1))
    chunks = int(re.search(r"- total_chunks: ([0-9]+)", rag_cov_md).group(1))

    integrity_score = float(re.search(r"Data integrity score: ([0-9.]+)/100", integrity_md).group(1))
    inconsistencies = int(re.search(r"Total inconsistencies: ([0-9]+)", integrity_md).group(1))

    nlp_metrics, nlp_samples = _run_lightweight_nlp_eval(chat_val.get("questions", []))

    final = {
        "generated_at": datetime.now(UTC).isoformat(),
        "positioning_statement": "An AI-first operational decision-support prototype validated on a synthetic full-platform cooperative dataset using hybrid SQL/RAG orchestration and reproducible evaluation pipelines.",
        "chatbot_metrics": {
            "baseline_overall_pass_rate": baseline["summary"]["overall_pass_rate"],
            "unseen_overall_pass_rate": unseen["summary"]["overall_pass_rate"],
            "full_platform_overall_pass_rate": full_summary["overall_pass_rate"],
            "sql_only_pass_rate": full_intent["SQL_ONLY"]["rate"],
            "rag_only_pass_rate": full_intent["RAG_ONLY"]["rate"],
            "hybrid_pass_rate": full_intent["HYBRID"]["rate"],
            "small_talk_pass_rate": full_intent["SMALL_TALK"]["rate"],
            "unsupported_pass_rate": full_intent["UNSUPPORTED"]["rate"],
            "routing_accuracy": routing_accuracy,
            "sql_factual_accuracy": sql_fact_acc,
            "module_coverage_rate": full_summary["module_coverage"]["coverage_rate"],
        },
        "grounding_safety_metrics": {
            "hallucination_high_risk_count": full_summary["fake_entity_high_risk_count"],
            "stale_response_count": full_summary["stale_response_issue_count"],
            "ui_debug_leakage_count": full_summary["debug_leakage_issue_count"],
            **rag_metrics,
        },
        "nlp_metrics": nlp_metrics,
        "performance_metrics": {
            "avg_sql_only_latency_ms": round(lat_sql, 2),
            "avg_hybrid_latency_ms": round(lat_hyb, 2),
            "avg_rag_only_latency_ms": round(lat_rag, 2),
            "sql_only_target_lt_2s": lat_sql < 2000,
            "hybrid_target_lt_5s": lat_hyb < 5000,
        },
        "rag_index_metrics": {"total_indexed_documents": docs, "total_indexed_chunks": chunks},
        "ml_metrics": {
            "dataset_size": ml["dataset"]["row_count"],
            "classification_accuracy": ml["metrics"]["classification"]["accuracy"],
            "classification_macro_f1": ml["metrics"]["classification"]["f1_macro"],
            "classification_precision_macro": ml["metrics"]["classification"]["precision_macro"],
            "classification_recall_macro": ml["metrics"]["classification"]["recall_macro"],
            "regression_mae": ml["metrics"]["regression"]["mae"],
            "regression_rmse": ml["metrics"]["regression"]["rmse"],
            "regression_r2": ml["metrics"]["regression"]["r2"],
            "anomaly_detection_limitations": ml["metrics"]["anomaly_detection"]["note"],
            "class_imbalance_notes": "Risk classes are imbalanced (low risk dominates), which depresses macro metrics for medium/high classes.",
        },
        "data_quality": {
            "integrity_score": integrity_score,
            "inconsistencies": inconsistencies,
            "seeded_module_coverage": full_summary["module_coverage"],
            "reproducibility_scripts": [
                "backend/scripts/seed_full_demo_dataset.py",
                "backend/scripts/validate_demo_data_integrity.py --fix",
                "backend/scripts/chatbot_quality_audit.py",
                "backend/scripts/chatbot_unseen_robustness_audit.py",
                "backend/scripts/chatbot_full_platform_coverage_audit.py",
                "backend/scripts/ml_full_demo_validation.py",
            ],
        },
        "nlp_evaluation_protocol": {
            "reference_source": "backend/artifacts/chatbot_validation_audit.json (historical validation answers)",
            "hypothesis_source": "Current chatbot answers generated on same prompt set",
            "sample_count": len(nlp_samples),
            "samples": nlp_samples,
            "limitations": [
                "BLEU/ROUGE are lexical-overlap metrics and do not fully capture factual correctness or managerial usefulness.",
                "Reference answers are historical system outputs, not expert gold annotations.",
                "Semantic cosine similarity is TF-IDF based and remains a lightweight proxy, not a deep semantic truth metric.",
            ],
        },
        "limitations": [
            "Validation is performed on a synthetic full-platform dataset; external validity on real cooperative operations remains limited.",
            "Hybrid/RAG latency remains above strict 5s target in current environment.",
            "RAG metadata completeness is uneven for some fields (e.g., source_id, severity).",
            "ML regression fit is weak (low R²), and anomaly validation lacks supervised labels.",
        ],
    }

    # markdown
    lines = [
        "# Final AI Validation Report",
        "",
        f"Generated: {final['generated_at']}",
        "",
        "## 1. Executive Summary",
        f"- Positioning: {final['positioning_statement']}",
        f"- Full-platform chatbot pass rate: {final['chatbot_metrics']['full_platform_overall_pass_rate']:.4f}",
        f"- High-risk hallucination count: {final['grounding_safety_metrics']['hallucination_high_risk_count']}",
        f"- Data integrity score: {final['data_quality']['integrity_score']}/100",
        "",
        "## 2. Chatbot/RAG Validation",
        "| Metric | Value |",
        "|---|---:|",
        f"| Baseline pass rate | {final['chatbot_metrics']['baseline_overall_pass_rate']:.4f} |",
        f"| Unseen pass rate | {final['chatbot_metrics']['unseen_overall_pass_rate']:.4f} |",
        f"| Full-platform pass rate | {final['chatbot_metrics']['full_platform_overall_pass_rate']:.4f} |",
        f"| SQL_ONLY pass rate | {final['chatbot_metrics']['sql_only_pass_rate']:.4f} |",
        f"| RAG_ONLY pass rate | {final['chatbot_metrics']['rag_only_pass_rate']:.4f} |",
        f"| HYBRID pass rate | {final['chatbot_metrics']['hybrid_pass_rate']:.4f} |",
        f"| SMALL_TALK pass rate | {final['chatbot_metrics']['small_talk_pass_rate']:.4f} |",
        f"| UNSUPPORTED pass rate | {final['chatbot_metrics']['unsupported_pass_rate']:.4f} |",
        f"| Routing accuracy | {final['chatbot_metrics']['routing_accuracy']:.4f} |",
        f"| SQL factual accuracy | {final['chatbot_metrics']['sql_factual_accuracy']:.4f} |",
        f"| Module coverage rate | {final['chatbot_metrics']['module_coverage_rate']:.4f} |",
        "",
        "## 3. NLP Similarity Metrics",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for k in ["bleu_1", "bleu_2", "bleu_4", "rouge_1", "rouge_2", "rouge_l", "semantic_cosine_similarity"]:
        lines.append(f"| {k.upper()} | {final['nlp_metrics'][k]:.4f} |")

    lines.extend(
        [
            "",
            "## 4. Grounding & Hallucination Control",
            "| Metric | Value |",
            "|---|---:|",
            f"| Hallucination high-risk count | {final['grounding_safety_metrics']['hallucination_high_risk_count']} |",
            f"| Stale response count | {final['grounding_safety_metrics']['stale_response_count']} |",
            f"| UI/debug leakage count | {final['grounding_safety_metrics']['ui_debug_leakage_count']} |",
            f"| Retrieval relevance score | {final['grounding_safety_metrics']['retrieval_relevance_score']:.4f} |",
            f"| Grounding score | {final['grounding_safety_metrics']['grounding_score']:.4f} |",
            f"| Citation relevance score | {final['grounding_safety_metrics']['citation_relevance_score']:.4f} |",
            f"| Expected chunk coverage | {final['grounding_safety_metrics']['expected_chunk_coverage']:.4f} |",
            f"| Scope purity score | {final['grounding_safety_metrics']['scope_purity_score']:.4f} |",
            f"| Contamination rate | {final['grounding_safety_metrics']['contamination_rate']:.4f} |",
            f"| Operational priority score | {final['grounding_safety_metrics']['operational_priority_score']:.4f} |",
            "",
            "## 5. ML Validation",
            "| Metric | Value |",
            "|---|---:|",
            f"| Dataset size | {final['ml_metrics']['dataset_size']} |",
            f"| Classification accuracy | {final['ml_metrics']['classification_accuracy']:.4f} |",
            f"| Classification macro-F1 | {final['ml_metrics']['classification_macro_f1']:.4f} |",
            f"| Classification precision (macro) | {final['ml_metrics']['classification_precision_macro']:.4f} |",
            f"| Classification recall (macro) | {final['ml_metrics']['classification_recall_macro']:.4f} |",
            f"| Regression MAE | {final['ml_metrics']['regression_mae']:.4f} |",
            f"| Regression RMSE | {final['ml_metrics']['regression_rmse']:.4f} |",
            f"| Regression R² | {final['ml_metrics']['regression_r2']:.4f} |",
            "",
            "## 6. Latency & Performance",
            "| Metric | Value |",
            "|---|---:|",
            f"| Avg SQL_ONLY latency (ms) | {final['performance_metrics']['avg_sql_only_latency_ms']:.2f} |",
            f"| Avg HYBRID latency (ms) | {final['performance_metrics']['avg_hybrid_latency_ms']:.2f} |",
            f"| Avg RAG_ONLY latency (ms) | {final['performance_metrics']['avg_rag_only_latency_ms']:.2f} |",
            "",
            "## 7. RAG Index Coverage",
            f"- Total indexed documents: {final['rag_index_metrics']['total_indexed_documents']}",
            f"- Total indexed chunks: {final['rag_index_metrics']['total_indexed_chunks']}",
            "",
            "## 8. Data Integrity & Reproducibility",
            f"- Integrity score: {final['data_quality']['integrity_score']}/100",
            f"- Inconsistencies: {final['data_quality']['inconsistencies']}",
            f"- Seeded module coverage rate: {final['data_quality']['seeded_module_coverage']['coverage_rate']:.4f}",
            "",
            "## 9. Key Limitations",
        ]
    )
    for item in final["limitations"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 10. Final Positioning Statement",
            f"{final['positioning_statement']}",
            "",
            "### Methodological Notes",
            "- Operational validation metrics and NLP lexical similarity metrics are complementary but not equivalent.",
            "- BLEU/ROUGE are reported as lightweight indicators only and should not be interpreted as standalone quality truth for LLM systems.",
            "- Real-world production validation remains distinct from this controlled synthetic-dataset evaluation.",
        ]
    )

    REPORT_JSON.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {REPORT_MD}")
    print(f"Saved {REPORT_JSON}")


if __name__ == "__main__":
    main()
