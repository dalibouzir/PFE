from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid
from collections import Counter
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import and_, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

COOP_ID = "4cbc6020-def9-4d24-bb75-9d40bc031466"
REPORT_DIR = ROOT / "reports" / "chatbot"
JSON_REPORT = REPORT_DIR / "manager_style_audit.json"
MD_REPORT = REPORT_DIR / "manager_style_audit.md"


def _norm(v: Any) -> str:
    return " ".join(str(v or "").lower().split())


def _cases() -> list[tuple[str, str]]:
    return [
        ("sql1", "Combien de mouvements de stock et les 5 derniers (type, produit, quantité, source) ?"),
        ("sql2", "Quels lots ont les pertes les plus élevées ?"),
        ("sql3", "Donne les charges globales et dépenses trésorerie."),
        ("sql4", "Pour les commandes payées, quelles factures sont liées ?"),
        ("sql5", "Quelles collectes ont BL ou justificatif ?"),
        ("sql6", "Stock disponible par produit."),
        ("sql7", "Quel est le bilan matière des lots ?"),
        ("sql8", "Top producteurs par volume."),
        ("ml1", "Pour le lot DEMOFP-LOT-MANG-013, perte SQL et signal ML."),
        ("ml2", "Quel lot a le signal ML le plus critique ?"),
        ("ml3", "Pour ce lot, y a-t-il anomalie ML ?"),
        ("ml4", "Donne le risque ML et la perte observée du même lot."),
        ("ml5", "Signal ML indisponible: dis-le clairement pour ce lot."),
        ("rag1", "Selon nos données, où perd-on le plus et comment améliorer ?"),
        ("rag2", "Précautions avant emballage."),
        ("rag3", "Bonnes pratiques de séchage."),
        ("rag4", "Conseil opérationnel pour réduire les pertes au tri."),
        ("rag5", "Checklist post-récolte concise."),
        ("full1", "Quel lot a la plus forte perte SQL, son signal ML, et la recommandation liée ?"),
        ("full2", "Analyse lot critique avec SQL, ML, recommandation et conseil pratique."),
        ("full3", "Pour ce lot, données SQL + risque ML + action recommandée."),
        ("full4", "Synthèse complète lot/perte/ML/recommandation."),
        ("ro1", "Quelles précautions prendre avant l’emballage ?"),
        ("ro2", "Checklist rapide tri/séchage/nettoyage."),
        ("ro3", "Point de vigilance avant conditionnement."),
        ("reco1", "Et le premier, quelle action recommandes-tu ?"),
        ("reco2", "Action prioritaire pour ce lot."),
        ("reco3", "Quelle recommandation liée à ce lot ?"),
        ("o1", "Connecte-toi et vérifie le dashboard."),
        ("o2", "Dois-je licencier des membres ?"),
    ]


def _score(answer: str, route: str) -> tuple[str, list[str]]:
    t = _norm(answer)
    reasons: list[str] = []
    if route == "OUT_OF_SCOPE":
        if any(x in t for x in ("sql", "lot", "perte", "tableau")):
            reasons.append("out_of_scope_leak")
    else:
        if not any(h in t for h in ("réponse directe", "conclusion", "ce que montrent", "action prioritaire", "résumé")):
            reasons.append("missing_structure_header")
        if "limites" not in t:
            reasons.append("missing_limit_section")
        if "avertissement technique" in t:
            reasons.append("technical_warning_spam")
        if "structured_recommendation" in t:
            reasons.append("raw_chunk_or_debug")
    if not reasons:
        return "PASS", []
    critical = {"out_of_scope_leak", "raw_chunk_or_debug"}
    if any(r in critical for r in reasons):
        return "FAIL", reasons
    return "PARTIAL", reasons


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    manager = db.scalar(select(User).where(and_(User.cooperative_id == COOP_ID, User.role.in_(["manager", "owner", "admin"]))).limit(1))
    if manager is None:
        raise RuntimeError("No manager found.")

    def _odb():
        yield db

    app.dependency_overrides[get_db] = _odb
    app.dependency_overrides[get_current_user] = lambda: manager
    client = TestClient(app)

    rows: list[dict[str, Any]] = []
    for cid, q in _cases():
        resp = client.post("/chat/agent", json={"message": q, "conversation_id": str(uuid.uuid4())}, timeout=40)
        p = resp.json()
        score, reasons = _score(str(p.get("answer") or ""), str(p.get("route") or ""))
        rows.append({"id": cid, "route": p.get("route"), "score": score, "reasons": reasons, "question": q})

    counts = Counter(r["score"] for r in rows)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "cooperative_id": COOP_ID, "total": len(rows), "counts": dict(counts), "rows": rows}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# Manager Style Audit",
        "",
        f"- Date: {report['generated_at']}",
        f"- Total: {len(rows)}",
        f"- PASS/PARTIAL/FAIL: {counts.get('PASS',0)}/{counts.get('PARTIAL',0)}/{counts.get('FAIL',0)}",
        "",
        "|id|route|score|reasons|",
        "|---|---|---|---|",
    ]
    for r in rows:
        md.append(f"|{r['id']}|{r['route']}|{r['score']}|{','.join(r['reasons'])}|")
    MD_REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {JSON_REPORT}")
    print(f"Wrote {MD_REPORT}")


if __name__ == "__main__":
    main()
