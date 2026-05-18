from __future__ import annotations

import json
import statistics
import time
import uuid
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
from app.models.user import User


CASES = [
    "Combien de membres sont enregistrés ?",
    "Combien de parcelles avons-nous ?",
    "Donne le stock disponible par produit.",
    "Donne les derniers mouvements de stock avec type et quantité.",
    "Combien de collectes avec BL et justificatif ?",
    "Combien d’avances avec devis et sync trésorerie ?",
    "Combien de transactions ENREGISTRE_COMPLET et sans justificatif ?",
    "Commande payée -> facture -> trésorerie: donne les comptes.",
    "Quel lot a le plus grand anomaly_score ?",
    "Combien de signaux ML HIGH ?",
    "Selon nos données, où perd-on le plus et comment améliorer ?",
    "Lot critique selon SQL, ML, RAG et recommandations: que faire ?",
    "Quelles précautions avant emballage pour limiter la casse ?",
    "Donne une mini check-list tri + stockage pour limiter les pertes.",
    "Affiche un graphique des pertes par étape.",
    "Affiche un graphique stock total/réservé/disponible.",
    "Donne les 3 lots critiques.",
    "Le premier: détaille risque ML et action.",
    "Oublie ce lot, donne seulement le stock global.",
    "Dois-je licencier un membre ?",
]


def main() -> None:
    db = SessionLocal()
    manager = db.scalar(select(User).where(User.email == "manager@weefarm.local").limit(1))
    if manager is None:
        raise RuntimeError("manager@weefarm.local not found")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: manager
    client = TestClient(app)

    mem_conv = str(uuid.uuid4())
    mem_idx = {16, 17, 18}  # preserve follow-up flow
    rows = []

    for idx, q in enumerate(CASES):
        conv_id = mem_conv if idx in mem_idx else str(uuid.uuid4())
        t0 = time.perf_counter()
        status = 0
        payload: dict = {}
        err = ""
        try:
            resp = client.post("/chat/agent", json={"message": q, "conversation_id": conv_id})
            status = resp.status_code
            payload = resp.json() if status == 200 else {}
        except Exception as exc:
            err = f"{type(exc).__name__}"
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        meta = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        timing = meta.get("timing_ms", {}) if isinstance(meta, dict) else {}
        rows.append(
            {
                "idx": idx + 1,
                "status": status,
                "error": err,
                "route": payload.get("route"),
                "latency_ms": latency_ms,
                "total_ms_meta": timing.get("total"),
                "timing_ms": timing,
                "persistence_ms": meta.get("persistence_ms"),
            }
        )
        print(f"[{idx+1:02d}/{len(CASES)}] status={status or 'TIMEOUT'} route={payload.get('route')} latency_ms={latency_ms}", flush=True)

    app.dependency_overrides.clear()
    db.close()

    lat = [float(r["latency_ms"]) for r in rows if r["status"] == 200]
    non_200 = sum(1 for r in rows if r["status"] != 200)
    hangs = sum(1 for r in rows if (r["status"] == 0) or r["error"])
    p95 = round(sorted(lat)[int(0.95 * (len(lat) - 1))], 2) if lat else 0.0
    summary = {
        "total_requests": len(rows),
        "http_non_200": non_200,
        "hang_or_exception_count": hangs,
        "latency_ms": {
            "avg": round(sum(lat) / len(lat), 2) if lat else 0.0,
            "p50": round(statistics.median(lat), 2) if lat else 0.0,
            "p95": p95,
            "max": round(max(lat), 2) if lat else 0.0,
        },
        "slowest_layers_observed": _top_slow_layers(rows),
        "rows": rows,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _top_slow_layers(rows: list[dict]) -> list[dict]:
    layer_totals: dict[str, list[float]] = {}
    for row in rows:
        timing = row.get("timing_ms") or {}
        if not isinstance(timing, dict):
            continue
        for key in ("route_planning", "context_build", "memory", "plan_answer", "evidence_pack", "evidence_verify", "compose_answer", "response_verify", "confidence", "source_contract"):
            val = timing.get(key)
            if isinstance(val, (int, float)):
                layer_totals.setdefault(key, []).append(float(val))
        agents = timing.get("agents") or []
        if isinstance(agents, list):
            for item in agents:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("agent") or "agent")
                ms = item.get("execution_ms")
                if isinstance(ms, (int, float)):
                    layer_totals.setdefault(f"agent:{name}", []).append(float(ms))
    stats = []
    for name, vals in layer_totals.items():
        stats.append({"layer": name, "avg_ms": round(sum(vals) / len(vals), 2), "max_ms": round(max(vals), 2)})
    stats.sort(key=lambda x: x["avg_ms"], reverse=True)
    return stats[:8]


if __name__ == "__main__":
    main()
