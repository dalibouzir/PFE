from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.rag import RAGChunk, RAGDocument


MISSING_THRESHOLD = 0.25


def _safe_dict(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def run_healthcheck() -> dict:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(
                RAGChunk.id,
                RAGChunk.metadata_json,
                RAGDocument.metadata_json,
                RAGDocument.source_table,
            ).join(RAGDocument, RAGDocument.id == RAGChunk.document_id)
        ).all()

        total_chunks = len(rows)
        with_chunk_type = 0
        with_freshness = 0
        source_distribution: Counter[str] = Counter()
        chunk_type_distribution: Counter[str] = Counter()

        for _, chunk_md_raw, doc_md_raw, source_table in rows:
            chunk_md = _safe_dict(chunk_md_raw)
            doc_md = _safe_dict(doc_md_raw)
            source_distribution[str(source_table or "unknown")] += 1

            chunk_type = chunk_md.get("chunk_type") or doc_md.get("chunk_type") or chunk_md.get("entity") or doc_md.get("entity")
            if _has_value(chunk_type):
                with_chunk_type += 1
                chunk_type_distribution[str(chunk_type)] += 1
            else:
                chunk_type_distribution["missing"] += 1

            freshness = chunk_md.get("freshness_timestamp") or doc_md.get("freshness_timestamp")
            if _has_value(freshness):
                with_freshness += 1

        missing_chunk_type = max(0, total_chunks - with_chunk_type)
        missing_freshness = max(0, total_chunks - with_freshness)
        missing_chunk_ratio = (missing_chunk_type / total_chunks) if total_chunks else 0.0
        missing_freshness_ratio = (missing_freshness / total_chunks) if total_chunks else 0.0

        should_reindex = (
            total_chunks > 0
            and (missing_chunk_ratio > MISSING_THRESHOLD or missing_freshness_ratio > MISSING_THRESHOLD)
        )

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_chunks": total_chunks,
            "chunks_with_chunk_type": with_chunk_type,
            "chunks_missing_chunk_type": missing_chunk_type,
            "chunks_with_freshness_timestamp": with_freshness,
            "chunks_missing_freshness_timestamp": missing_freshness,
            "chunk_type_coverage_ratio": round((with_chunk_type / total_chunks), 4) if total_chunks else 0.0,
            "freshness_coverage_ratio": round((with_freshness / total_chunks), 4) if total_chunks else 0.0,
            "source_table_distribution": dict(sorted(source_distribution.items(), key=lambda item: item[0])),
            "chunk_type_distribution": dict(chunk_type_distribution),
            "recommendation": {
                "force_reindex_recommended": should_reindex,
                "missing_ratio_threshold": MISSING_THRESHOLD,
                "reason": (
                    "Missing metadata ratio exceeds threshold; run targeted semantic reindex."
                    if should_reindex
                    else "Metadata coverage acceptable; reindex not strictly required."
                ),
            },
        }
        return report
    finally:
        db.close()


def main() -> None:
    report = run_healthcheck()
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
