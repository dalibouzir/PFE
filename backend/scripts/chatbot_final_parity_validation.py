from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


@dataclass
class ParityCase:
    cid: str
    question: str
    kind: str = "single"  # single|sequence
    steps: list[str] | None = None


def build_cases() -> list[ParityCase]:
    return [
        ParityCase("P01", "Quels produits sont sous le seuil critique de stock ?"),
        ParityCase("P02", "Montre les derniers mouvements de stock avec type, produit, quantité, source et date."),
        ParityCase("P03", "Total collecté par produit sur la période disponible."),
        ParityCase("P04", "Liste les membres producteurs actifs."),
        ParityCase("P05", "Quel producteur a livré le plus grand volume ?"),
        ParityCase("P06", "Quels lots sont prêts pour la post-récolte ?"),
        ParityCase("P07", "Range les lots par perte matière en kilogrammes."),
        ParityCase("P08", "Quelle étape provoque la perte la plus élevée ?"),
        ParityCase("P09", "Regroupe les commandes commerciales par statut avec nombre et montant total."),
        ParityCase("P10", "Regroupe les factures par statut de paiement avec nombre et montant total."),
        ParityCase("P11", "Existe-t-il des commandes payées sans facture associée ?"),
        ParityCase("P12", "Combien de transactions de trésorerie sont sans justificatif ?"),
        ParityCase("P13", "Donne une seule action fiable pour LOT-MILX-001 avec preuve."),
        ParityCase("P14", "Top 3 actions fiables pour LOT-MILX-001, avec preuves."),
        ParityCase("P15", "Moyenne des factures payées ce trimestre ; si aucune, dis-le explicitement."),
        ParityCase("P16", "Combien de signaux ML HIGH sur 30 jours ?"),
        ParityCase("P17", "Bonnes pratiques de séchage pour réduire les pertes."),
        ParityCase("P18", "Stock disponible total actuel de la coopérative ?"),
        ParityCase("P19", "Recommandations disponibles pour ce lot sans inventer.", kind="sequence", steps=["Quel lot a la perte la plus élevée ?", "Recommandations disponibles pour ce lot sans inventer."]),
        ParityCase("P20", "Ce lot ?", kind="sequence", steps=["Oublie ce lot", "Ce lot ?"]),
    ]


def _extract(body: dict[str, Any]) -> dict[str, Any]:
    md = body.get("metadata") or {}
    status = md.get("evidence_status") or {}
    blocks = [str((b or {}).get("type") or "") for b in (body.get("response_blocks") or []) if isinstance(b, dict)]
    sql_trace = md.get("sql_dispatch_trace") or {}
    warnings = [str(w) for w in (body.get("warnings") or [])]
    src_roles = [str((s or {}).get("type") or "") for s in (body.get("sources") or []) if isinstance(s, dict)]
    answer = str(body.get("answer") or "")
    return {
        "route": body.get("route"),
        "intent_family": md.get("intent_family") or (md.get("detected_entities") or {}).get("intent_family"),
        "sql_operation": sql_trace.get("sql_operation"),
        "evidence_status": status,
        "evidence_rows": sql_trace.get("row_count"),
        "response_blocks": blocks,
        "summary_text": answer.splitlines()[0][:220] if answer else "",
        "warning_codes": md.get("warning_codes") or warnings,
        "source_display": src_roles,
        "ml_block_present": any("ml" in b.lower() for b in blocks),
        "latency_ms": md.get("total_duration_ms") or body.get("latency_ms"),
        "raw_answer": answer,
    }


def _compare(local: dict[str, Any], dep: dict[str, Any]) -> tuple[bool, str]:
    keys = ["route", "intent_family", "sql_operation", "evidence_rows"]
    for k in keys:
        if (local.get(k) or "") != (dep.get(k) or ""):
            return False, f"mismatch_{k}"
    if set(local.get("response_blocks") or []) != set(dep.get("response_blocks") or []):
        return False, "mismatch_response_blocks"
    if bool(local.get("ml_block_present")) != bool(dep.get("ml_block_present")):
        return False, "mismatch_ml_block_presence"
    return True, "match"


def _login_local() -> tuple[TestClient, str]:
    client = TestClient(app)
    login = client.post("/auth/login", json={"email": "manager@weefarm.local", "password": "Manager123!"})
    login.raise_for_status()
    return client, login.json()["access_token"]


def _login_deployed(base_url: str) -> str:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{base_url.rstrip('/')}/auth/login", json={"email": "manager@weefarm.local", "password": "Manager123!"})
        r.raise_for_status()
        return r.json()["access_token"]


def _ask_local(client: TestClient, token: str, message: str, conversation_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message, "language": "fr"}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    t0 = time.perf_counter()
    r = client.post("/chat/agent", headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=70)
    dt = (time.perf_counter() - t0) * 1000
    r.raise_for_status()
    b = r.json()
    (b.setdefault("metadata", {}))["total_duration_ms"] = b.get("metadata", {}).get("total_duration_ms") or round(dt, 2)
    return b


def _ask_dep(base_url: str, token: str, message: str, conversation_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message, "language": "fr"}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    t0 = time.perf_counter()
    with httpx.Client(timeout=70.0) as client:
        r = client.post(f"{base_url.rstrip('/')}/chat/agent", headers={"Authorization": f"Bearer {token}"}, json=payload)
        dt = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        b = r.json()
    (b.setdefault("metadata", {}))["total_duration_ms"] = b.get("metadata", {}).get("total_duration_ms") or round(dt, 2)
    return b


def run() -> dict[str, Any]:
    base_url = "https://weefarm-backend-app.prouddune-c85ebf6e.germanywestcentral.azurecontainerapps.io"
    cases = build_cases()

    local_client, local_token = _login_local()
    dep_token = _login_deployed(base_url)

    out: list[dict[str, Any]] = []
    for case in cases:
        local_conv = str(uuid.uuid4())
        dep_conv = str(uuid.uuid4())

        if case.kind == "single":
            lb = _ask_local(local_client, local_token, case.question, local_conv)
            db = _ask_dep(base_url, dep_token, case.question, dep_conv)
        else:
            steps = case.steps or []
            lb = {}
            db = {}
            for i, step in enumerate(steps):
                lb = _ask_local(local_client, local_token, step, local_conv if i > 0 else None)
                local_conv = (lb.get("metadata") or {}).get("conversation_id") or local_conv
                db = _ask_dep(base_url, dep_token, step, dep_conv if i > 0 else None)
                dep_conv = (db.get("metadata") or {}).get("conversation_id") or dep_conv

        le = _extract(lb)
        de = _extract(db)
        same, diagnosis = _compare(le, de)
        out.append({
            "case_id": case.cid,
            "question": case.question,
            "local": le,
            "deployed": de,
            "same": same,
            "diagnosis": diagnosis,
        })

    total = len(out)
    same_n = sum(1 for r in out if r["same"])
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deployed_base_url": base_url,
        "total_cases": total,
        "same_cases": same_n,
        "diff_cases": total - same_n,
        "results": out,
    }

    out_dir = Path("backend/artifacts/evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"chatbot_final_parity_validation_{ts}.json"
    md_path = out_dir / f"chatbot_final_parity_validation_{ts}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Final Chatbot Parity Validation",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Deployed backend: `{base_url}`",
        f"- Cases: `{total}`",
        f"- Same: `{same_n}` | Diff: `{total-same_n}`",
        "",
        "| Case | Same | Diagnosis | Local route | Deployed route | Local sql_op | Deployed sql_op | Local latency ms | Deployed latency ms |",
        "|---|---|---|---|---|---|---|---:|---:|",
    ]
    for r in out:
        l = r["local"]
        d = r["deployed"]
        lines.append(
            f"| {r['case_id']} | {'yes' if r['same'] else 'no'} | {r['diagnosis']} | {l.get('route') or ''} | {d.get('route') or ''} | {l.get('sql_operation') or ''} | {d.get('sql_operation') or ''} | {l.get('latency_ms') or 0} | {d.get('latency_ms') or 0} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result["json_report"] = str(json_path)
    result["md_report"] = str(md_path)
    return result


if __name__ == "__main__":
    r = run()
    print(r["json_report"])
    print(r["md_report"])
    print(json.dumps({"same_cases": r["same_cases"], "diff_cases": r["diff_cases"]}, ensure_ascii=False))
