from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

QUESTIONS = [
    "current stock of mango",
    "what is the status of LOT-MANG-001?",
    "why are drying losses high this week for mango?",
    "compare current mango drying losses with benchmark references",
    "which lot is most risky and what should we do?",
]


def main() -> None:
    db = SessionLocal()
    manager = db.scalar(select(User).where(User.role == UserRole.MANAGER).limit(1))
    if manager is None:
        raise RuntimeError("Aucun manager trouvé pour la prévisualisation.")

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: manager
    client = TestClient(app)

    print("\n=== Prévisualisation des réponses Copilote IA (Phase 6) ===\n")
    for question in QUESTIONS:
        response = client.post("/chat", json={"message": question, "top_k": 4})
        payload = response.json()
        print(f"Question: {question}")
        print(f"Mode: {payload.get('mode')} | Grounded: {payload.get('grounded')}")
        blocks = payload.get("ui_blocks", [])
        summary = next((b for b in blocks if b.get("type") == "executive_summary"), None)
        if summary:
            print("Résumé exécutif:")
            print(f"- {summary.get('payload', {}).get('text')}")
        kpis = next((b for b in blocks if b.get("type") == "kpi_grid"), None)
        if kpis:
            print("KPI:")
            for item in kpis.get("payload", {}).get("items", [])[:5]:
                print(f"- {item.get('label')}: {item.get('value')} {item.get('unit')} ({item.get('severity')})")
        recos = next((b for b in blocks if b.get("type") == "recommendation_cards"), None)
        if recos:
            print("Actions recommandées:")
            for i, item in enumerate(recos.get("payload", {}).get("items", [])[:3], start=1):
                print(f"{i}. {item.get('action')} [{item.get('priorité')}]")
        evidence = next((b for b in blocks if b.get("type") == "evidence_drawer"), None)
        if evidence:
            items = evidence.get("payload", {}).get("items", [])
            print(f"Sources: {len(items)}")
        print("—" * 72)

    app.dependency_overrides.clear()
    db.close()


if __name__ == "__main__":
    main()
