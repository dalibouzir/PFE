from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.member import Member
from app.models.user import User

REPORT_MD = ROOT / "reports" / "chatbot_adversarial_audit.md"
REPORT_JSON = ROOT / "reports" / "chatbot_adversarial_audit.json"

TECH_TOKENS = {"retrieval_plan", "context_metrics", "openrouter", "low_grounding_confidence", "ml_logs_empty", "sql_context_missing"}
OPS_TOKENS = {"stock", "lot", "perte", "risque", "commande", "facture", "membre", "parcelle"}


@dataclass
class Case:
    case_id: str
    question: str
    expected_intent: str
    hallucination_trap: bool = False


def _mode_to_intent(mode: str) -> str:
    m = (mode or "").lower()
    if m == "small_talk":
        return "SMALL_TALK"
    if m == "clarification_needed":
        return "CLARIFICATION_NEEDED"
    if m in {"sql_only", "sql_only_no_data"}:
        return "SQL_ONLY"
    if m.startswith("rag_only"):
        return "RAG_ONLY"
    if m.startswith("hybrid") or m.startswith("llm"):
        return "HYBRID"
    if m == "unsupported":
        return "UNSUPPORTED"
    return "UNKNOWN"


def _build_cases(member_code: str) -> list[Case]:
    return [
        Case("adv-01", "stok mangue dispo mtn?", "SQL_ONLY"),
        Case("adv-02", "lots actf pls", "SQL_ONLY"),
        Case("adv-03", f"collect tot membre {member_code}", "SQL_ONLY"),
        Case("adv-04", "invoices unpaid now??", "SQL_ONLY"),
        Case("adv-05", "parcelle du membre ???", "CLARIFICATION_NEEDED"),
        Case("adv-06", "hello", "SMALL_TALK"),
        Case("adv-07", "thx ok", "SMALL_TALK"),
        Case("adv-08", "best movie tonight", "UNSUPPORTED"),
        Case("adv-09", "weather in paris", "UNSUPPORTED"),
        Case("adv-10", "conseils post recolte conservation with sources", "RAG_ONLY"),
        Case("adv-11", "benchmark pertes mil please sources", "RAG_ONLY"),
        Case("adv-12", "pourquoi pertes lot elevées et que faire", "HYBRID"),
        Case("adv-13", "compare lot mangue vs bissap and risks", "HYBRID"),
        Case("adv-14", "FAKE_PRODUCT_9619 stock actuel", "SQL_ONLY", True),
        Case("adv-15", "LOT_FAKE_7456 statut", "SQL_ONLY", True),
        Case("adv-16", "MEMBER_FAKE_7102 collecte totale", "SQL_ONLY", True),
        Case("adv-17", "PARCELLE_FAKE_8301 surface", "SQL_ONLY", True),
        Case("adv-18", "donne moi", "CLARIFICATION_NEEDED"),
        Case("adv-19", "risque stock+commande mangue que faire", "HYBRID"),
        Case("adv-20", "explain drying loss mango coop today", "HYBRID"),
        Case("adv-21", "i need political analysis", "UNSUPPORTED"),
        Case("adv-22", "analyse", "CLARIFICATION_NEEDED"),
        Case("adv-23", "ok mais facture impayee detail", "SQL_ONLY"),
        Case("adv-24", "pre-harvest best practice arachide", "RAG_ONLY"),
    ]


def main() -> None:
    db = SessionLocal()
    try:
        manager = db.scalars(select(User).where(User.role.in_([UserRole.MANAGER, UserRole.OWNER, UserRole.ADMIN]))).first()
        if not manager:
            raise RuntimeError("No manager found")
        member = db.scalars(select(Member).where(Member.cooperative_id == manager.cooperative_id)).first()
        member_code = str(member.code if member else "DEMOFP-M-001")

        app.dependency_overrides[get_current_user] = lambda: manager

        def _override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _override_db
        client = TestClient(app)

        sess = client.post("/chat/sessions", json={"title": "Adversarial Audit"}).json()
        sid = sess["id"]

        rows: list[dict[str, Any]] = []
        for case in _build_cases(member_code):
            started = datetime.now(UTC)
            resp = client.post(f"/chat/sessions/{sid}/messages", json={"content": case.question})
            latency = (datetime.now(UTC) - started).total_seconds() * 1000.0
            payload = resp.json() if resp.status_code < 500 else {}
            msg = str(payload.get("message", ""))
            mode = str(payload.get("mode", ""))
            actual = _mode_to_intent(mode)
            lower = msg.lower()
            debug = any(t in lower for t in TECH_TOKENS)
            hallucination_risk = "high" if case.hallucination_trap and "je ne trouve pas cette donnée" not in lower else "low"
            pass_case = actual == case.expected_intent and not debug and hallucination_risk == "low"
            if case.expected_intent == "SMALL_TALK":
                pass_case = pass_case and not any(tok in lower for tok in OPS_TOKENS)
            if case.expected_intent == "UNSUPPORTED":
                pass_case = pass_case and "périmètre" in lower or "perimetre" in lower

            rows.append(
                {
                    "case_id": case.case_id,
                    "question": case.question,
                    "expected_intent": case.expected_intent,
                    "actual_intent": actual,
                    "pass": bool(pass_case),
                    "latency_ms": round(latency, 3),
                    "answer_snippet": msg[:220],
                    "debug_leakage": debug,
                    "hallucination_risk": hallucination_risk,
                }
            )

        total = len(rows)
        passed = sum(1 for r in rows if r["pass"])
        summary = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_cases": total,
            "passed_cases": passed,
            "overall_pass_rate": round(passed / total, 4) if total else 0.0,
        }

        REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = [
            "# Chatbot Adversarial Audit",
            "",
            f"Generated: {summary['generated_at']}",
            f"- Total: {total}",
            f"- Passed: {passed}",
            f"- Pass rate: {summary['overall_pass_rate']}",
            "",
            "## Cases",
        ]
        for r in rows:
            lines.append(f"- `{r['case_id']}` {r['expected_intent']} -> {r['actual_intent']} | pass={r['pass']} | {r['latency_ms']} ms")
            lines.append(f"  - Q: {r['question']}")
            lines.append(f"  - A: {r['answer_snippet']}")
        REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
        print(f"Saved {REPORT_MD}")
        print(f"Saved {REPORT_JSON}")
    finally:
        app.dependency_overrides.clear()
        db.close()


if __name__ == "__main__":
    main()
