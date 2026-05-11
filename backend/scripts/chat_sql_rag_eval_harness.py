from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import String, cast, func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.batch import Batch
from app.models.enums import UserRole
from app.models.member import Member
from app.models.product import Product
from app.models.reference import KnowledgeChunk
from app.models.user import User
from app.services import assistant as assistant_service
from app.schemas.chat import ChatCitation
from app.utils.exceptions import ValidationError


@dataclass
class HarnessCase:
    case_id: str
    prompt: str
    category: str


class UnavailableLLMClient:
    def chat(self, messages: list[dict[str, str]]) -> Any:
        raise ValidationError("LLM unavailable for deterministic harness")


def _metric_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("metric")): item
        for item in payload.get("context_metrics", [])
        if isinstance(item, dict) and item.get("metric")
    }


def _intent_from_payload(payload: dict[str, Any]) -> str:
    metric = _metric_map(payload).get("retrieval_plan.intent_type", {})
    return str(metric.get("unit", "")).upper()


def _table_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in payload.get("ui_blocks", []) if isinstance(item, dict) and item.get("type") == "table"]


def _extract_first_int(text_value: str) -> int | None:
    match = re.search(r"\b(\d+)\b", text_value or "")
    if not match:
        return None
    return int(match.group(1))


def _ensure_rag_reference_seed(db) -> None:
    existing = db.scalar(
        select(KnowledgeChunk.id).where(
            func.lower(KnowledgeChunk.crop) == "mango",
            func.lower(KnowledgeChunk.topic).in_(["sechage", "séchage", "drying"]),
        ).limit(1)
    )
    if existing:
        return
    db.add(
        KnowledgeChunk(
            source_id="HARNESS-SRC-KNOW-001",
            source_url="https://example.org/harness-knowledge-001",
            country="Senegal",
            region="Thies",
            crop="mango",
            topic="Séchage",
            content="Le séchage ventilé de la mangue réduit l'humidité résiduelle et limite les pertes de masse.",
        )
    )
    db.commit()


def main() -> None:
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    json_path = reports_dir / f"chat_sql_rag_eval_harness_{stamp}.json"
    md_path = reports_dir / f"chat_sql_rag_eval_harness_{stamp}.md"

    db = SessionLocal()
    manager = db.scalar(select(User).where(User.role == UserRole.MANAGER).limit(1))
    if manager is None:
        raise RuntimeError("Manager user not found for evaluation harness.")

    _ensure_rag_reference_seed(db)

    member_rows = db.execute(
        select(Member.code, Member.full_name, Member.main_product, Member.status, Member.parcel_count, Member.area_hectares)
        .where(Member.cooperative_id == manager.cooperative_id)
        .order_by(Member.full_name.asc())
        .limit(25)
    ).all()
    active_lots = int(
        db.scalar(
            select(func.count(Batch.id)).where(
                Batch.cooperative_id == manager.cooperative_id,
                func.lower(cast(Batch.status, String)) == "active",
            )
        )
        or 0
    )
    lot_rows = db.execute(
        select(Batch.code, Product.name, Batch.initial_qty, Batch.current_qty, Batch.status, Batch.updated_at)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == manager.cooperative_id)
        .order_by(Batch.updated_at.desc(), Batch.code.asc())
        .limit(10)
    ).all()

    # Deterministic no-LLM behavior for routing/SQL/RAG fallback validation.
    assistant_service.get_llm_client = lambda: UnavailableLLMClient()
    assistant_service._retrieve_reference_context = lambda *args, **kwargs: assistant_service.ReferenceContext(
        citations=[
            ChatCitation(
                source_id="HARNESS-SRC-KNOW-001",
                source_url="https://example.org/harness-knowledge-001",
                region="Thies",
                crop="mango",
                topic="Séchage",
                excerpt="Le séchage ventilé de la mangue réduit l'humidité résiduelle.",
            )
        ],
        metrics=[],
    )

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: manager
    client = TestClient(app)

    cases = [
        HarnessCase("sql_active_lots_exact", "combien de lots actifs avons-nous ?", "SQL_ONLY_EXACT"),
        HarnessCase("sql_members_table", "liste les membres actifs avec code et statut", "SQL_TABLE_MEMBERS"),
        HarnessCase(
            "sql_lots_table_latest",
            "Affiche-moi un tableau des 10 derniers lots avec code lot, produit, quantité entrée, quantité sortie, taux de perte, statut et date de mise à jour.",
            "SQL_TABLE_LOTS",
        ),
        HarnessCase("hybrid_operational_analysis", "Pourquoi les pertes de séchage sont élevées cette semaine ?", "HYBRID"),
        HarnessCase("rag_only_reference", "donne des références agronomiques sur le séchage de la mangue avec sources", "RAG_ONLY"),
    ]

    results: list[dict[str, Any]] = []
    passed = 0
    for case in cases:
        response = client.post("/chat", json={"message": case.prompt})
        payload = response.json()
        intent = _intent_from_payload(payload)
        tables = _table_blocks(payload)
        checks: list[dict[str, Any]] = []

        if case.case_id == "sql_active_lots_exact":
            count = _extract_first_int(str(payload.get("message", "")))
            checks = [
                {"name": "status_code_200", "ok": response.status_code == 200},
                {"name": "intent_sql_only", "ok": intent == "SQL_ONLY"},
                {"name": "active_lot_count_matches_db", "ok": count == active_lots, "expected": active_lots, "actual": count},
            ]
        elif case.case_id == "sql_members_table":
            expected_columns = ["code", "nom", "produit principal", "statut", "parcelles", "surface_ha"]
            first_table = tables[0] if tables else {}
            rows = (first_table.get("payload") or {}).get("rows", [])
            checks = [
                {"name": "status_code_200", "ok": response.status_code == 200},
                {"name": "intent_sql_only", "ok": intent == "SQL_ONLY"},
                {"name": "table_present", "ok": len(tables) >= 1},
                {"name": "member_columns_match_contract", "ok": (first_table.get("payload") or {}).get("columns") == expected_columns},
                {"name": "member_row_count_matches_db", "ok": len(rows) == len(member_rows)},
                {
                    "name": "member_first_row_matches_db",
                    "ok": (not rows and not member_rows)
                    or (rows and member_rows and rows[0][0] == str(member_rows[0][0]) and rows[0][1] == str(member_rows[0][1])),
                },
                {"name": "no_lot_loss_contamination", "ok": "pertes moyennes" not in str(payload.get("message", "")).lower()},
            ]
        elif case.case_id == "sql_lots_table_latest":
            expected_columns = ["lot_code", "produit", "qty_in", "qty_out", "loss_pct", "statut", "updated_at"]
            first_table = tables[0] if tables else {}
            rows = (first_table.get("payload") or {}).get("rows", [])
            checks = [
                {"name": "status_code_200", "ok": response.status_code == 200},
                {"name": "intent_sql_only", "ok": intent == "SQL_ONLY"},
                {"name": "table_present", "ok": len(tables) >= 1},
                {"name": "lot_columns_match_contract", "ok": (first_table.get("payload") or {}).get("columns") == expected_columns},
                {"name": "row_count_matches_requested_limit", "ok": len(rows) == len(lot_rows)},
            ]
        elif case.case_id == "hybrid_operational_analysis":
            checks = [
                {"name": "status_code_200", "ok": response.status_code == 200},
                {"name": "intent_hybrid", "ok": intent == "HYBRID"},
                {
                    "name": "hybrid_has_nonempty_message",
                    "ok": bool(str(payload.get("message", "")).strip()),
                },
            ]
        else:
            checks = [
                {"name": "status_code_200", "ok": response.status_code == 200},
                {"name": "intent_rag_only", "ok": intent == "RAG_ONLY"},
                {"name": "citations_present", "ok": len(payload.get("citations", [])) >= 1},
                {"name": "message_source_grounded", "ok": "harness-src-know-001" in str(payload.get("message", "")).lower()},
            ]

        case_pass = all(bool(item.get("ok")) for item in checks)
        if case_pass:
            passed += 1
        results.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "prompt": case.prompt,
                "pass": case_pass,
                "mode": payload.get("mode"),
                "intent": intent,
                "message_preview": str(payload.get("message", ""))[:220],
                "ui_block_types": [item.get("type") for item in payload.get("ui_blocks", []) if isinstance(item, dict)],
                "checks": checks,
            }
        )

    score = round((passed / len(cases)) * 100.0, 2) if cases else 0.0
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "manager_email": manager.email,
        "ground_truth": {
            "member_rows": len(member_rows),
            "active_lots": active_lots,
            "lot_rows_latest_10": len(lot_rows),
        },
        "summary": {
            "total_cases": len(cases),
            "passed_cases": passed,
            "score_pct": score,
        },
        "results": results,
    }

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# Chat SQL/RAG Eval Harness ({stamp})",
        "",
        f"- Manager: `{manager.email}`",
        f"- Score: **{score}%** ({passed}/{len(cases)} cases passed)",
        "",
        "## Ground Truth",
        f"- Members (max 25): **{len(member_rows)}**",
        f"- Active lots: **{active_lots}**",
        f"- Latest lots used for 10-row check: **{len(lot_rows)}**",
        "",
        "## Case Results",
    ]
    for item in results:
        lines.append(f"- `{item['case_id']}` intent=`{item['intent']}` mode=`{item['mode']}` pass=`{item['pass']}`")
        for check in item["checks"]:
            lines.append(f"  - {check['name']}: {'PASS' if check['ok'] else 'FAIL'}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    app.dependency_overrides.clear()
    db.close()
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Score: {score}% ({passed}/{len(cases)})")


if __name__ == "__main__":
    main()
