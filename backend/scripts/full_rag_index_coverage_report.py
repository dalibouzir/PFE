from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.rag import RAGChunk, RAGDocument
from app.models.user import User
from app.services import rag_indexer as rag_indexer_service

REPORT_PATH = ROOT_DIR / "reports" / "full_rag_index_coverage_report.md"


MODULE_BY_TABLE = {
    "members": "members",
    "fields": "parcels",
    "parcels": "parcels",
    "pre_harvest_steps": "parcels",
    "inputs": "collections",
    "stocks": "stocks",
    "batches": "lots",
    "process_steps": "process",
    "recommendations": "recommendations",
    "recommendation_feedback_logs": "recommendations",
    "ml_prediction_logs": "ml",
    "ml_recommendation_logs": "ml",
    "ml_training_runs": "ml",
    "ml_model_registry": "ml",
    "commercial_catalog_products": "commercial",
    "commercial_orders": "commercial",
    "commercial_invoices": "invoices",
    "treasury_transactions": "finance",
    "global_charges": "finance",
    "farmer_advances": "finance",
    "knowledge_chunks": "reference",
    "reference_metrics": "reference",
}


def _coverage_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * float(numerator) / float(denominator), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate RAG index coverage report.")
    parser.add_argument(
        "--skip-reindex",
        action="store_true",
        help="Skip reindex execution and report current RAG tables only.",
    )
    args = parser.parse_args()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    session = SessionLocal()
    try:
        manager = session.scalars(
            select(User)
            .where(User.role.in_([UserRole.MANAGER, UserRole.OWNER, UserRole.ADMIN]))
            .order_by(User.created_at.asc())
        ).first()
        if manager is None:
            raise RuntimeError("No manager/owner/admin user found for reindex.")

        if args.skip_reindex:
            reindex_response = None
        else:
            reindex_response = rag_indexer_service.reindex_cooperative(
                session,
                current_user=manager,
                cooperative_id=manager.cooperative_id if manager.role == UserRole.ADMIN else None,
                force=False,
            )

        docs = session.scalars(
            select(RAGDocument).where(RAGDocument.cooperative_id == manager.cooperative_id)
        ).all()
        chunks = session.scalars(
            select(RAGChunk).where(RAGChunk.cooperative_id == manager.cooperative_id)
        ).all()

        docs_by_table = Counter()
        chunks_by_table = Counter()
        chunks_by_type = Counter()
        chunks_by_product = Counter()
        chunks_by_module = Counter()
        freshness_buckets = Counter()
        metadata_key_coverage = defaultdict(int)

        now = datetime.now(UTC)
        expected_meta_keys = [
            "source_table",
            "source_id",
            "chunk_type",
            "product_name",
            "member_name",
            "batch_code",
            "stage",
            "order_number",
            "invoice_number",
            "freshness_timestamp",
            "risk_level",
            "severity",
        ]

        for doc in docs:
            docs_by_table[str(doc.source_table)] += 1

        for chunk in chunks:
            meta: dict[str, Any] = chunk.metadata_json or {}
            source_table = str(meta.get("source_table") or "")
            chunk_type = str(meta.get("chunk_type") or "unknown")
            product = str(meta.get("product_name") or meta.get("product") or "unknown")
            freshness_ts = meta.get("freshness_timestamp")
            table_for_count = source_table or "unknown"

            chunks_by_table[table_for_count] += 1
            chunks_by_type[chunk_type] += 1
            chunks_by_product[product] += 1
            chunks_by_module[MODULE_BY_TABLE.get(table_for_count, "other")] += 1

            for key in expected_meta_keys:
                if key in meta and meta.get(key) not in (None, "", []):
                    metadata_key_coverage[key] += 1

            age_minutes = None
            if isinstance(freshness_ts, str):
                try:
                    parsed = datetime.fromisoformat(freshness_ts.replace("Z", "+00:00"))
                    age_minutes = (now - parsed).total_seconds() / 60.0
                except Exception:
                    age_minutes = None
            if age_minutes is None:
                freshness_buckets["missing"] += 1
            elif age_minutes <= 60:
                freshness_buckets["<=1h"] += 1
            elif age_minutes <= 24 * 60:
                freshness_buckets["<=24h"] += 1
            elif age_minutes <= 7 * 24 * 60:
                freshness_buckets["<=7d"] += 1
            else:
                freshness_buckets[">7d"] += 1

        total_chunks = len(chunks)
        lines: list[str] = [
            "# Full RAG Index Coverage Report",
            "",
            f"Generated: {datetime.now(UTC).isoformat()}",
            f"Cooperative ID: {manager.cooperative_id}",
            "",
            "## Reindex Summary",
            f"- executed: {'no (skip)' if reindex_response is None else 'yes'}",
            f"- documents_seen: {0 if reindex_response is None else reindex_response.documents_seen}",
            f"- documents_created: {0 if reindex_response is None else reindex_response.documents_created}",
            f"- documents_updated: {0 if reindex_response is None else reindex_response.documents_updated}",
            f"- documents_unchanged: {0 if reindex_response is None else reindex_response.documents_unchanged}",
            f"- documents_deleted: {0 if reindex_response is None else reindex_response.documents_deleted}",
            f"- chunks_created: {0 if reindex_response is None else reindex_response.chunks_created}",
            f"- chunks_deleted: {0 if reindex_response is None else reindex_response.chunks_deleted}",
            "",
            "## Totals",
            f"- total_documents: {len(docs)}",
            f"- total_chunks: {total_chunks}",
            "",
            "## Chunks By Module",
        ]
        for module, count in sorted(chunks_by_module.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {module}: {count}")

        lines.extend(["", "## Documents By Source Table"])
        for table, count in sorted(docs_by_table.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {table}: {count}")

        lines.extend(["", "## Chunks By Source Table"])
        for table, count in sorted(chunks_by_table.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {table}: {count}")

        lines.extend(["", "## Chunks By Chunk Type"])
        for chunk_type, count in sorted(chunks_by_type.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {chunk_type}: {count}")

        lines.extend(["", "## Chunks By Product (top 20)"])
        for product, count in sorted(chunks_by_product.items(), key=lambda x: (-x[1], x[0]))[:20]:
            lines.append(f"- {product}: {count}")

        lines.extend(["", "## Freshness Coverage"])
        for bucket in ["<=1h", "<=24h", "<=7d", ">7d", "missing"]:
            count = int(freshness_buckets.get(bucket, 0))
            lines.append(f"- {bucket}: {count} ({_coverage_pct(count, total_chunks)}%)")

        lines.extend(["", "## Metadata Coverage"])
        for key in expected_meta_keys:
            count = int(metadata_key_coverage.get(key, 0))
            lines.append(f"- {key}: {count}/{total_chunks} ({_coverage_pct(count, total_chunks)}%)")

        missing_modules = sorted(
            module
            for module in set(MODULE_BY_TABLE.values())
            if chunks_by_module.get(module, 0) == 0
        )
        lines.extend(["", "## Missing Modules Not Indexed"])
        if missing_modules:
            for module in missing_modules:
                lines.append(f"- {module}: no chunks found; verify source data availability and collectors.")
        else:
            lines.append("- None.")

        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"Saved {REPORT_PATH}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
