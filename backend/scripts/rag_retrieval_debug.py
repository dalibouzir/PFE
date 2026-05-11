from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.services.assistant import debug_retrieval_context


SAMPLE_QUESTIONS = [
    "why are drying losses high this week for mango?",
    "what happened to LOT-MANG-004?",
    "which lot is most risky and what should we do?",
]


def main() -> None:
    db = SessionLocal()
    try:
        current_user = db.scalar(select(User).where(User.role == UserRole.MANAGER).limit(1))
        if current_user is None:
            print("No manager user found. Aborting debug.")
            return

        for question in SAMPLE_QUESTIONS:
            result = debug_retrieval_context(db, current_user=current_user, message=question, top_k=6)
            print("\n" + "=" * 80)
            print("Question:", question)
            print("Retrieval plan:", result.get("retrieval_plan"))
            print("Filters:", result.get("filters"))
            print("Diagnostics:", result.get("retrieval_diagnostics"))
            print("Hits:")
            for hit in result.get("hits", []):
                print(
                    " -",
                    {
                        "chunk_type": hit.get("chunk_type"),
                        "source_table": hit.get("source_table"),
                        "freshness_age_minutes": hit.get("freshness_age_minutes"),
                        "retrieval_score": hit.get("retrieval_score"),
                        "retrieval_reason": hit.get("retrieval_reason"),
                        "source_record_ref": hit.get("source_record_ref"),
                    },
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
