"""set rag embedding dimension to 384 for local provider

Revision ID: c1a7e9f4d2b3
Revises: aa4f6c2d9e10
Create Date: 2026-05-18 10:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "c1a7e9f4d2b3"
down_revision: Union[str, Sequence[str], None] = "aa4f6c2d9e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Protect existing deployments with live chunk data from implicit truncation.
    chunk_count = bind.execute(text("SELECT COUNT(*) FROM rag_chunks")).scalar()
    if int(chunk_count or 0) > 0:
        raise RuntimeError(
            "Cannot auto-migrate rag_chunks embedding dimension to 384 while rows exist. "
            "Delete/reindex rag_chunks explicitly before applying this migration."
        )

    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_ivfflat")
    op.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_ivfflat
        ON rag_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    chunk_count = bind.execute(text("SELECT COUNT(*) FROM rag_chunks")).scalar()
    if int(chunk_count or 0) > 0:
        raise RuntimeError(
            "Cannot auto-downgrade rag_chunks embedding dimension to 1536 while rows exist."
        )

    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_ivfflat")
    op.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_ivfflat
        ON rag_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )
