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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

COOP_ID = "4cbc6020-def9-4d24-bb75-9d40bc031466"
REPORT_DIR = ROOT / "reports" / "chatbot"
JSON_REPORT = REPORT_DIR / "t01_t05_variants_audit.json"
MD_REPORT = REPORT_DIR / "t01_t05_variants_audit.md"

T01 = [
    "Classe les lots par taux de perte.",
    "Quels lots ont la pire efficacité ?",
    "Donne les lots critiques selon le bilan matière.",
    "Où observe-t-on les plus gros écarts entrée/sortie ?",
    "Top lots post-récolte par perte avec disponibilité ML.",
    "Classement perte par lot avec produit et efficacité.",
    "Montre les 5 lots les plus pénalisés en post-récolte.",
    "Perte la plus élevée par lot et signal ML disponible ou non.",
    "Quels sont les pires lots en bilan matière ?",
    "Ranking des lots selon perte et efficacité.",
]

T01_EXPANDED = [
    "Classe les lots post-récolte du plus mauvais au meilleur rendement.",
    "Quels batches ont le plus grand écart entre entrée et sortie ?",
    "Montre les lots critiques selon le bilan matière.",
    "Où l’efficacité est-elle la plus faible par lot ?",
    "Donne le classement des batches par perte matière.",
    "Quels lots doivent être priorisés à cause des pertes ?",
    "Liste les lots post-récolte avec perte %, efficacité et statut ML.",
    "Quels lots ont le rendement le plus faible ?",
    "Fais un tableau des pertes par batch avec disponibilité ML.",
    "Quels lots présentent les pertes matière les plus fortes ?",
]

T05 = [
    "Pour les lots pré-récolte, donne les charges estimées et les dates.",
    "Montre les étapes pré-récolte d’un lot avec quantité prévue.",
    "Quel est le suivi pré-récolte sans calcul de perte ?",
    "Donne parcelle, culture, dates et charge estimée.",
    "Résumé pré-récolte du lot.",
    "Pré-récolte: quantité estimée, charge estimée, étapes et statut.",
    "Lot pré-récolte: planification et dates réelles si disponibles.",
    "Affiche seulement les infos estimées d’un lot pré-récolte.",
    "Parcelle/culture et étapes pré-récolte du lot.",
    "Suivi lifecycle pré-récolte d’un lot.",
]


def _norm(v: Any) -> str:
    return " ".join(str(v or "").lower().split())


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    t = _norm(text)
    return any(w in t for w in words)


def _score_t01(route: str, answer: str, table_titles: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    t = _norm(answer)
    if route not in {"SQL_ONLY", "HYBRID_SQL_ML", "HYBRID_FULL"}:
        reasons.append(f"wrong_route:{route}")
    bl_word = bool(re.search(r"\bbl\b", t))
    if _contains_any(t, ("traçabilité collectes", "justificatif", "facture", "trésorerie")) or bl_word:
        reasons.append("wrong_table_or_domain_leak")
    if not any("classement pertes post-récolte" in _norm(x) for x in table_titles):
        reasons.append("missing_strict_toploss_table")
    if reasons:
        return "FAIL", reasons
    return "PASS", []


def _score_t05(route: str, answer: str, table_titles: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    t = _norm(answer)
    if route not in {"SQL_ONLY"}:
        reasons.append(f"wrong_route:{route}")
    forbidden = (
        "perte %",
        "efficacité",
        "efficacite",
        "bilan matière",
        "bilan matiere",
        "signal ml",
        "nettoyage",
        "séchage",
        "sechage",
        "tri",
        "emballage",
        "conditionnement",
    )
    if _contains_any(t, forbidden):
        reasons.append("postharvest_leak")
    if reasons:
        return "FAIL", reasons
    return "PASS", []


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    manager = db.scalar(
        select(User).where(and_(User.cooperative_id == COOP_ID, User.role.in_(["manager", "owner", "admin"]))).limit(1)
    )
    if manager is None:
        raise RuntimeError("No manager found.")

    def _odb():
        yield db

    def _ou():
        return manager

    app.dependency_overrides[get_db] = _odb
    app.dependency_overrides[get_current_user] = _ou

    rows: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for i, q in enumerate(T01, 1):
            r = client.post("/chat/agent", json={"message": q, "conversation_id": str(uuid.uuid4())}, timeout=40)
            p = r.json()
            blocks = p.get("response_blocks") or []
            titles = [str(b.get("title") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "table"]
            score, reasons = _score_t01(str(p.get("route") or ""), str(p.get("answer") or ""), titles)
            rows.append({"id": f"t01v{i:02d}", "class": "t01", "question": q, "route": p.get("route"), "score": score, "reasons": reasons})
        for i, q in enumerate(T05, 1):
            r = client.post("/chat/agent", json={"message": q, "conversation_id": str(uuid.uuid4())}, timeout=40)
            p = r.json()
            blocks = p.get("response_blocks") or []
            titles = [str(b.get("title") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "table"]
            score, reasons = _score_t05(str(p.get("route") or ""), str(p.get("answer") or ""), titles)
            rows.append({"id": f"t05v{i:02d}", "class": "t05", "question": q, "route": p.get("route"), "score": score, "reasons": reasons})

    for i, q in enumerate(T01_EXPANDED, 1):
        r = client.post("/chat/agent", json={"message": q, "conversation_id": str(uuid.uuid4())}, timeout=40)
        p = r.json()
        blocks = p.get("response_blocks") or []
        titles = [str(b.get("title") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "table"]
        score, reasons = _score_t01(str(p.get("route") or ""), str(p.get("answer") or ""), titles)
        rows.append({"id": f"t01x{i:02d}", "class": "t01_expanded", "question": q, "route": p.get("route"), "score": score, "reasons": reasons})

    stats = {"t01": {"PASS": 0, "FAIL": 0}, "t01_expanded": {"PASS": 0, "FAIL": 0}, "t05": {"PASS": 0, "FAIL": 0}}
    for row in rows:
        stats[row["class"]][row["score"]] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cooperative_id": COOP_ID,
        "rows": rows,
        "stats": stats,
    }
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# T01/T05 Variants Audit",
        "",
        f"- Date: {report['generated_at']}",
        f"- t01 PASS/FAIL: {stats['t01']['PASS']}/{stats['t01']['FAIL']}",
        f"- t01 expanded PASS/FAIL: {stats['t01_expanded']['PASS']}/{stats['t01_expanded']['FAIL']}",
        f"- t05 PASS/FAIL: {stats['t05']['PASS']}/{stats['t05']['FAIL']}",
        "",
        "|id|class|route|score|reasons|",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        md.append(f"|{row['id']}|{row['class']}|{row['route']}|{row['score']}|{','.join(row['reasons'])}|")
    MD_REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {JSON_REPORT}")
    print(f"Wrote {MD_REPORT}")


if __name__ == "__main__":
    main()
