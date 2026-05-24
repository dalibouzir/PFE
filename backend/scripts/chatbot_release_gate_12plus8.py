#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


DEFAULT_EMAIL = "manager@weefarm.local"
DEFAULT_PASSWORD = "Manager123!"
DEFAULT_BASE_URL_ENV = "CHATBOT_GATE_BASE_URL"


@dataclass(frozen=True)
class GateCase:
    case_id: str
    group: str
    question: str
    expected_route: str
    expected_sql_operation: str | None = None


ANTI_OVERFIT_CASES: list[GateCase] = [
    GateCase("A01", "anti_overfit", "Il reste combien de kg disponibles pour la mangue ?", "SQL_ONLY", "get_current_stock"),
    GateCase("A02", "anti_overfit", "Quels produits sont presque en rupture ou sous seuil ?", "SQL_ONLY"),
    GateCase("A03", "anti_overfit", "Affiche-moi les dernières sorties de stock uniquement.", "SQL_ONLY", "get_stock_movements_journal"),
    GateCase("A04", "anti_overfit", "Quel producteur a livré le plus récemment ?", "SQL_ONLY", "clarification_required"),
    GateCase("A05", "anti_overfit", "Avant d’entreposer les produits, quels points vérifier ?", "RAG_ONLY"),
    GateCase("A06", "anti_overfit", "Comment limiter les pertes pendant le séchage ?", "RAG_ONLY"),
    GateCase("A07", "anti_overfit", "Donne-moi les critères de tri pour les mangues abîmées.", "RAG_ONLY"),
    GateCase("A08", "anti_overfit", "Je veux une action fiable pour LOT-MILX-001 - Mil", "HYBRID_FULL"),
    GateCase("A09", "anti_overfit", "Changeons de sujet, ne garde pas le lot précédent. Et celui-ci ?", "SQL_ONLY", "clarification_required"),
    GateCase("A10", "anti_overfit", "Quels signaux de risque le modèle détecte ?", "HYBRID_SQL_ML"),
    GateCase("A11", "anti_overfit", "Classe les étapes par pertes mesurées.", "SQL_ONLY", "get_stage_loss_analysis"),
    GateCase("A12", "anti_overfit", "Explique simplement pourquoi un mauvais séchage augmente les pertes.", "RAG_ONLY"),
]

NON_REG_CASES: list[GateCase] = [
    GateCase("N01", "non_regression", "Combien de mangue avons-nous en stock actuellement ?", "SQL_ONLY", "get_current_stock"),
    GateCase("N02", "non_regression", "Liste les membres de la coopérative.", "SQL_ONLY"),
    GateCase("N03", "non_regression", "Montre uniquement les mouvements sortants de stock.", "SQL_ONLY", "get_stock_movements_journal"),
    GateCase("N04", "non_regression", "Checklist avant emballage.", "RAG_ONLY"),
    GateCase("N05", "non_regression", "Avant mise en stock, que contrôler en priorité ?", "RAG_ONLY"),
    GateCase("N06", "non_regression", "Recommandations fiables LOT-ABC sinon invalide.", "HYBRID_FULL"),
    GateCase("N07", "non_regression", "Quels signaux ML sont à risque élevé ?", "HYBRID_SQL_ML"),
    GateCase("N08", "non_regression", "Oublie ce lot. Et pour celui-ci ?", "SQL_ONLY", "clarification_required"),
]

# Allowed sql op variants for HYBRID_FULL lot-action style questions.
HYBRID_FULL_ALLOWED_SQL_OPS = {"get_batch_summary", "get_process_step_losses"}


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="WeeFarm chatbot 12+8 release gate")
    p.add_argument(
        "--base-url",
        default=os.getenv(DEFAULT_BASE_URL_ENV, ""),
        help=f"Backend base URL, e.g. http://127.0.0.1:8000 (or env {DEFAULT_BASE_URL_ENV})",
    )
    p.add_argument("--auth-email", default=os.getenv("CHATBOT_GATE_EMAIL", DEFAULT_EMAIL))
    p.add_argument("--auth-password", default=os.getenv("CHATBOT_GATE_PASSWORD", DEFAULT_PASSWORD))
    p.add_argument("--timeout-s", type=float, default=90.0)
    p.add_argument("--output-json", default="")
    p.add_argument("--strict", action="store_true", help="Strict SQL operation checks where expected_sql_operation is provided")
    args = p.parse_args()
    if not str(args.base_url).strip():
        p.error(f"--base-url is required (or set {DEFAULT_BASE_URL_ENV})")
    return args


def _default_output_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / "artifacts" / "evals" / f"chatbot_release_gate_12plus8_{ts}.json"


def _login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    r = client.post(f"{base_url.rstrip('/')}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    token = (r.json() or {}).get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token in response")
    return str(token)


def _extract(body: dict[str, Any]) -> tuple[str | None, str | None, int, list[str], str, list[str]]:
    md = body.get("metadata") or {}
    route = body.get("route")
    sql_op = md.get("sql_operation") or ((md.get("sql_dispatch_trace") or {}).get("sql_operation"))
    sources = body.get("sources") or []
    source_types = sorted({str((s or {}).get("type") or "") for s in sources if isinstance(s, dict)})
    answer = " ".join(str(body.get("answer") or "").split())
    warning_codes = list(md.get("warning_codes") or [])
    return route, sql_op, len(sources), source_types, answer, warning_codes


def _is_in_scope_prompt(case: GateCase) -> bool:
    # All 20 cases are in-scope by design.
    return True


def _is_invalid_lot_prompt(question: str) -> bool:
    q = question.lower()
    return "lot-abc" in q and ("sinon invalide" in q or "invalide" in q)


def _detect_fake_reco_for_invalid_lot(case: GateCase, route: str | None, answer: str) -> bool:
    if not _is_invalid_lot_prompt(case.question):
        return False
    if route != "HYBRID_FULL":
        return False
    low = answer.lower()
    # Must acknowledge unknown lot / invalid reference, not emit concrete action list.
    invalid_markers = ["ne trouve pas de lot", "introuvable", "vérifiez la référence", "verifiez la reference", "invalide"]
    has_invalid = any(m in low for m in invalid_markers)
    has_action_list = any(m in low for m in ["- ", "1.", "2.", "action", "recommand"]) and not has_invalid
    return (not has_invalid) and has_action_list


def _assess(case: GateCase, *, route: str | None, sql_op: str | None, answer: str, source_types: list[str], http_status: int, strict: bool) -> tuple[str, str]:
    if http_status != 200:
        return "FAIL", f"HTTP {http_status}"

    if route != case.expected_route:
        return "FAIL", f"Expected route {case.expected_route}, got {route}."

    # In-scope prompts should never be OUT_OF_SCOPE.
    if _is_in_scope_prompt(case) and route == "OUT_OF_SCOPE":
        return "FAIL", "In-scope prompt routed to OUT_OF_SCOPE."

    # Follow-up reset case must clarify, not hallucinate carry-over.
    if case.case_id in {"A09", "N08"} and sql_op != "clarification_required":
        return "FAIL", f"Expected clarification_required for reset/follow-up, got {sql_op}."

    # Q12 can be PARTIAL for content coverage if route is RAG-centered.
    if case.case_id == "A12":
        low = answer.lower()
        weak_markers = ["pas assez de contexte", "contexte documentaire est limité", "contexte documentaire est limite", "donnée non disponible", "donnee non disponible", "aucune preuve"]
        if any(m in low for m in weak_markers):
            return "PARTIAL", "Q12 route is correct; weak RAG content evidence."

    # SQL operation strictness.
    if strict and case.expected_sql_operation:
        if case.case_id == "A08":
            if sql_op not in HYBRID_FULL_ALLOWED_SQL_OPS:
                return "PARTIAL", f"A08 expected one of {sorted(HYBRID_FULL_ALLOWED_SQL_OPS)}, got {sql_op}."
        elif sql_op != case.expected_sql_operation:
            return "PARTIAL", f"Expected sql_operation {case.expected_sql_operation}, got {sql_op}."

    # Critical semantic guard: fake recommendation on invalid lot.
    if _detect_fake_reco_for_invalid_lot(case, route, answer):
        return "FAIL", "Fake recommendation for invalid lot reference."

    # Minimal source pollution guard by route family.
    if route == "RAG_ONLY" and "sql" in source_types:
        return "FAIL", "SQL source pollution in RAG_ONLY response."
    if route == "SQL_ONLY" and "rag" in source_types:
        return "FAIL", "RAG source pollution in SQL_ONLY response."

    return "PASS", ""


def _run_case(client: httpx.Client, base_url: str, token: str, case: GateCase, conversation_id: str, timeout_s: float, strict: bool) -> dict[str, Any]:
    payload = {"message": case.question, "language": "fr", "conversation_id": conversation_id}
    t0 = time.perf_counter()
    http_status = 0
    body: dict[str, Any] = {}
    err = ""
    try:
        resp = client.post(
            f"{base_url.rstrip('/')}/chat/agent",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=timeout_s,
        )
        http_status = resp.status_code
        if resp.headers.get("content-type", "").startswith("application/json"):
            body = resp.json()
    except Exception as exc:  # noqa: BLE001
        http_status = 599
        err = str(exc)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    route, sql_op, sources_count, source_types, answer, warnings = _extract(body)
    status, reason = _assess(
        case,
        route=route,
        sql_op=sql_op,
        answer=answer,
        source_types=source_types,
        http_status=http_status,
        strict=strict,
    )
    if err:
        reason = (reason + " " + err).strip()

    return {
        "case_id": case.case_id,
        "group": case.group,
        "question": case.question,
        "expected_route": case.expected_route,
        "actual_route": route,
        "expected_sql_operation": case.expected_sql_operation,
        "actual_sql_operation": sql_op,
        "status": status,
        "latency_ms": latency_ms,
        "sources_count": sources_count,
        "sources_types": source_types,
        "warning_codes": warnings,
        "failure_reason": reason,
    }


def _print_summary(rows: list[dict[str, Any]]) -> None:
    print("\nRelease Gate 12+8 Summary")
    print("case  status   route                       sql_op")
    for r in rows:
        print(f"{r['case_id']:4}  {r['status']:<7} {str(r['actual_route'] or ''):<26} {str(r['actual_sql_operation'] or '')}")


def main() -> int:
    args = _args()
    all_cases = [*ANTI_OVERFIT_CASES, *NON_REG_CASES]
    conv_id = str(uuid.uuid4())

    with httpx.Client(timeout=args.timeout_s) as client:
        token = _login(client, args.base_url, args.auth_email, args.auth_password)
        rows = [_run_case(client, args.base_url, token, c, conv_id, args.timeout_s, args.strict) for c in all_cases]

    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("PASS", "PARTIAL", "FAIL")}
    failed = [r for r in rows if r["status"] == "FAIL"]
    anti_counts = {k: sum(1 for r in rows if r["group"] == "anti_overfit" and r["status"] == k) for k in ("PASS", "PARTIAL", "FAIL")}
    non_counts = {k: sum(1 for r in rows if r["group"] == "non_regression" and r["status"] == k) for k in ("PASS", "PARTIAL", "FAIL")}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "strict": bool(args.strict),
        "summary": {
            "all": counts,
            "anti_overfit": anti_counts,
            "non_regression": non_counts,
            "total_cases": len(rows),
            "failed_cases": len(failed),
        },
        "rows": rows,
    }

    output_path = args.output_json.strip()
    out = Path(output_path) if output_path else _default_output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_summary(rows)
    print(f"\nCounts: {counts} | anti={anti_counts} | non={non_counts}")
    print(f"Artifact: {out}")

    # Gate fails only on real FAILs. PARTIAL is allowed for known Q12 content quality.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

# Usage examples:
# Local:
#   .venv311/bin/python scripts/chatbot_release_gate_12plus8.py --base-url http://127.0.0.1:8000
# Deployed:
#   .venv311/bin/python scripts/chatbot_release_gate_12plus8.py --base-url https://weefarm-backend-app.prouddune-c85ebf6e.germanywestcentral.azurecontainerapps.io
