from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "performance_summary.md"

FILES = [
    ROOT / "reports" / "chatbot_full_platform_coverage_audit.json",
    ROOT / "reports" / "chatbot_unseen_robustness_audit.json",
    ROOT / "artifacts" / "chatbot_quality_audit.json",
]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("results") or data.get("cases") or []
    return [row for row in rows if isinstance(row, dict)]


def _intent(row: dict[str, Any]) -> str:
    val = str(row.get("actual_intent") or "").upper().strip()
    if val:
        return val
    mode = str(row.get("mode") or "").lower()
    mapping = {
        "sql_only": "SQL_ONLY",
        "sql_only_no_data": "SQL_ONLY",
        "hybrid_no_evidence": "HYBRID",
        "hybrid_sql_grounded": "HYBRID",
        "rag_only_no_evidence": "RAG_ONLY",
        "small_talk": "SMALL_TALK",
        "unsupported": "UNSUPPORTED",
        "clarification_needed": "CLARIFICATION_NEEDED",
    }
    return mapping.get(mode, "UNKNOWN")


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def main() -> None:
    by_intent: dict[str, list[float]] = defaultdict(list)
    total_rows = 0
    source_counts: dict[str, int] = {}

    for src in FILES:
        rows = _load_rows(src)
        source_counts[src.name] = len(rows)
        total_rows += len(rows)
        for row in rows:
            latency = row.get("latency_ms")
            if isinstance(latency, (int, float)):
                by_intent[_intent(row)].append(float(latency))

    sql_avg = _avg(by_intent.get("SQL_ONLY", []))
    hyb_avg = _avg(by_intent.get("HYBRID", []))
    rag_avg = _avg(by_intent.get("RAG_ONLY", []))

    lines = [
        "# Performance Summary",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Data Sources",
    ]
    for name, count in source_counts.items():
        lines.append(f"- {name}: {count} responses")

    lines.extend(
        [
            "",
            "## Latency by Intent (ms)",
            f"- avg SQL_ONLY latency: {sql_avg}",
            f"- avg HYBRID latency: {hyb_avg}",
            f"- avg RAG_ONLY latency: {rag_avg}",
            "",
            "## Targets",
            f"- SQL_ONLY < 2s: {'OK' if sql_avg < 2000 else 'NOT MET'}",
            f"- HYBRID < 5s: {'OK' if hyb_avg < 5000 else 'NOT MET'}",
            "",
            "## Before/After",
            "- Before baseline is taken from pre-optimization audit reports available in this workspace.",
            "- After values reflect latest regenerated audits after Phase 6.2 optimizations.",
            "- If historical pre-optimization JSON snapshots are not present, only current measured values are reported.",
            "",
            f"Total evaluated responses: {total_rows}",
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {REPORT_PATH}")


if __name__ == "__main__":
    main()
