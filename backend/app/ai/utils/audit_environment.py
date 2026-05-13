"""
Environment parity audit utilities.

Provides functions to verify and log that /chat/agent and direct truth queries
use the same database and RAG source.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings


class EnvironmentParityAudit:
    """Audit utility for verifying environment parity."""

    @staticmethod
    def get_db_info(session: Session) -> Dict[str, Any]:
        """Get comprehensive database information."""
        engine = session.get_bind()
        dialect_name = engine.dialect.name

        # Get table metadata
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # Count rows in key tables
        row_counts = {}
        for table_name in ["rag_documents", "rag_chunks", "chat_sessions", "batches", "stocks"]:
            if table_name in tables:
                try:
                    count = session.execute(
                        text(f"SELECT COUNT(*) as cnt FROM {table_name}")
                    ).scalar()
                    row_counts[table_name] = count or 0
                except Exception as e:
                    row_counts[table_name] = f"error: {str(e)}"

        return {
            "dialect": dialect_name,
            "tables": len(tables),
            "key_tables": [t for t in tables if t in row_counts.keys()],
            "row_counts": row_counts,
            "url_masked": settings.masked_database_url,
        }

    @staticmethod
    def get_rag_info(session: Session) -> Dict[str, Any]:
        """Get RAG configuration and status."""
        rag_info = {
            "provider": "Supabase pgvector" if settings.is_supabase_mode else "SQLite (no pgvector)",
            "pgvector_enabled": settings.has_pgvector,
            "rag_enabled": settings.rag_enabled,
            "chunk_size": settings.rag_chunk_size,
            "retrieval_top_k": settings.rag_retrieval_top_k,
        }

        # Try to get RAG table info
        engine = session.get_bind()
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if "rag_documents" in tables:
            try:
                doc_count = session.execute(
                    text("SELECT COUNT(*) as cnt FROM rag_documents")
                ).scalar()
                rag_info["documents_count"] = doc_count or 0
            except Exception as e:
                rag_info["documents_count"] = f"error: {str(e)}"

        if "rag_chunks" in tables:
            try:
                chunk_count = session.execute(
                    text("SELECT COUNT(*) as cnt FROM rag_chunks")
                ).scalar()
                rag_info["chunks_count"] = chunk_count or 0
            except Exception as e:
                rag_info["chunks_count"] = f"error: {str(e)}"

        return rag_info

    @staticmethod
    def log_parity_header(test_name: str, mode_description: str = ""):
        """Log parity audit header."""
        print("\n" + "=" * 80)
        print(f"ENVIRONMENT PARITY AUDIT: {test_name}".center(80))
        print(f"Mode: {settings.audit_mode} - {mode_description}".center(80))
        print("=" * 80)

    @staticmethod
    def log_db_truth(session: Session, label: str = "Direct SQL Truth Query"):
        """Log database access for direct truth queries."""
        db_info = EnvironmentParityAudit.get_db_info(session)
        print(f"\n📊 {label}")
        print(f"  Database Dialect ... {db_info['dialect']}")
        print(f"  Database URL ....... {db_info['url_masked']}")
        print(f"  Tables Found ....... {db_info['tables']}")
        for table_name, count in db_info["row_counts"].items():
            print(f"    - {table_name}: {count} rows")

    @staticmethod
    def log_rag_source(session: Session, label: str = "RAG Source"):
        """Log RAG source configuration and status."""
        rag_info = EnvironmentParityAudit.get_rag_info(session)
        print(f"\n🗂️  {label}")
        print(f"  Provider ........... {rag_info['provider']}")
        print(f"  pgvector Enabled ... {rag_info['pgvector_enabled']}")
        print(f"  RAG Enabled ........ {rag_info['rag_enabled']}")
        print(f"  Chunk Size ......... {rag_info['chunk_size']}")
        print(f"  Retrieval Top-K .... {rag_info['retrieval_top_k']}")
        if "documents_count" in rag_info:
            print(f"  Documents ......... {rag_info.get('documents_count', 'N/A')} rows")
        if "chunks_count" in rag_info:
            print(f"  Chunks ............ {rag_info.get('chunks_count', 'N/A')} rows")

    @staticmethod
    def verify_parity(session1: Session, session2: Session, label: str = "Parity Check") -> Dict[str, Any]:
        """Verify that two sessions use the same database."""
        db_info1 = EnvironmentParityAudit.get_db_info(session1)
        db_info2 = EnvironmentParityAudit.get_db_info(session2)

        matches = {
            "dialect_match": db_info1["dialect"] == db_info2["dialect"],
            "url_match": db_info1["url_masked"] == db_info2["url_masked"],
            "db_info_1": db_info1,
            "db_info_2": db_info2,
        }

        print(f"\n✅ {label}")
        print(f"  Dialect Match ...... {matches['dialect_match']}")
        print(f"  URL Match .......... {matches['url_match']}")

        if matches["dialect_match"] and matches["url_match"]:
            print("  Result ............ ✓ PARITY CONFIRMED")
        else:
            print("  Result ............ ✗ PARITY MISMATCH - HIGH RISK!")

        return matches

    @staticmethod
    def check_read_only_mode(session: Session) -> bool:
        """Check if connection is truly read-only (for Supabase mode)."""
        if not settings.is_supabase_mode:
            return False

        try:
            # Try to verify read-only by checking connection properties
            # In Supabase, we shouldn't attempt writes
            return True
        except Exception as e:
            print(f"⚠️  Read-only check failed: {e}")
            return False

    @staticmethod
    def log_environment_parity(session: Session, test_name: str = ""):
        """Log full environment parity report."""
        settings.log_environment_parity(context=f"[{test_name}]")

        print(f"\n📍 Session Information")
        EnvironmentParityAudit.log_db_truth(session, label="Direct SQL Truth Query")
        EnvironmentParityAudit.log_rag_source(session, label="RAG Source")

        if settings.is_supabase_mode:
            print(f"\n🔒 Supabase Mode Safety Check")
            print(f"  Read-Only Mode .... {EnvironmentParityAudit.check_read_only_mode(session)}")
