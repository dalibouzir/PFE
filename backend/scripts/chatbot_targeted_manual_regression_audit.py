from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

REPORT_DIR = ROOT / "reports" / "chatbot"
JSON_REPORT = REPORT_DIR / "targeted_manual_regression_audit.json"
MD_REPORT = REPORT_DIR / "targeted_manual_regression_audit.md"
COOP_ID = "4cbc6020-def9-4d24-bb75-9d40bc031466"


CASES: list[tuple[str, str]] = [
    ("t01", "Top pertes par lot, et pour chaque lot indique seulement : lot, produit, perte %, efficacité %, signal ML disponible ou indisponible."),
    ("t02", "Compare LOT-BANA-001 et LOT-BISS-002 : perte, efficacité, signal ML et recommandation pour chaque lot."),
    ("t03", "Analyse uniquement le lot LOT-BANA-001 : perte SQL, efficacité, signal ML exact, et recommandation liée uniquement à ce lot."),
    ("t04", "Selon nos données, où perd-on le plus : par lot ou par étape ?"),
    ("t05", "Pour un lot pré-récolte, donne quantité estimée, charge estimée, dates et étapes."),
]


def _norm(v: Any) -> str:
    return " ".join(str(v or "").lower().split())


def _score(case_id: str, route: str, answer: str) -> tuple[str, list[str]]:
    t = _norm(answer)
    reasons: list[str] = []
    if case_id in {"t01", "t02", "t03", "t04"}:
        forbidden = ("semis", "suivi floraison", "entretien")
        if any(x in t for x in forbidden):
            reasons.append("preharvest_stage_leak")
        if "160.6%" in answer or "efficacité 160" in t:
            reasons.append("invalid_efficiency_presented")
    if case_id in {"t02", "t03"} and "batch inconnu" in t:
        reasons.append("batch_inconnu_used_for_specific_lot")
    if case_id == "t01" and ("traçabilité collectes" in t or "bl" in t and "justificatif" in t):
        reasons.append("collecte_traceability_returned_for_top_loss")
    if case_id == "t05":
        if any(x in t for x in ("perte %", "efficacité", "signal ml")):
            reasons.append("postharvest_metrics_leak_in_preharvest_query")
    if route == "OUT_OF_SCOPE":
        reasons.append("wrong_route")
    if reasons:
        return "FAIL", reasons
    return "PASS", []


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    db: Session = SessionLocal()
    manager = db.scalar(
        select(User).where(and_(User.cooperative_id == COOP_ID, User.role.in_(["manager", "owner", "admin"]))).limit(1)
    )
    if manager is None:
        raise RuntimeError("No manager found for cooperative.")

    def _override_db():
        try:
            yield db
        finally:
            return

    def _override_user():
        return manager

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    rows: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for cid, question in CASES:
            conv = str(uuid.uuid4())
            resp = client.post("/chat/agent", json={"message": question, "conversation_id": conv}, timeout=40)
            payload = resp.json()
            route = str(payload.get("route") or "")
            answer = str(payload.get("answer") or "")
            score, reasons = _score(cid, route, answer)
            rows.append({"id": cid, "question": question, "route": route, "score": score, "reasons": reasons, "answer": answer})

    counts = {"PASS": 0, "FAIL": 0}
    for row in rows:
        counts[row["score"]] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cooperative_id": COOP_ID,
        "total_cases": len(rows),
        "score_counts": counts,
        "rows": rows,
    }
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Targeted Manual Regression Audit",
        "",
        f"- Date: {report['generated_at']}",
        f"- Cooperative: {COOP_ID}",
        f"- PASS/FAIL: {counts['PASS']}/{counts['FAIL']}",
        "",
        "|id|route|score|reasons|",
        "|---|---|---|---|",
    ]
    for row in rows:
        md.append(f"|{row['id']}|{row['route']}|{row['score']}|{','.join(row['reasons'])}|")
    MD_REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {JSON_REPORT}")
    print(f"Wrote {MD_REPORT}")


if __name__ == "__main__":
    main()
