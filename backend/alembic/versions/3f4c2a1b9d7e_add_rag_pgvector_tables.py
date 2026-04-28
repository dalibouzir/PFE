"""add rag pgvector tables

Revision ID: 3f4c2a1b9d7e
Revises: b8c2a4f3d7e1
Create Date: 2026-04-28 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3f4c2a1b9d7e"
down_revision: Union[str, None] = "b8c2a4f3d7e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_documents (
            id uuid PRIMARY KEY,
            cooperative_id uuid NOT NULL REFERENCES cooperatives(id) ON DELETE CASCADE,
            source_type varchar(64) NOT NULL,
            source_table varchar(64) NOT NULL,
            source_record_id uuid,
            source_record_ref varchar(160),
            title varchar(255),
            content_hash varchar(64) NOT NULL,
            metadata_json jsonb,
            last_synced_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
            created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
            updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_documents_source_scope
        ON rag_documents (cooperative_id, source_type, source_table, source_record_ref)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_documents_cooperative_id
        ON rag_documents (cooperative_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_documents_source_type
        ON rag_documents (source_type)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_documents_source_table
        ON rag_documents (source_table)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_documents_last_synced_at
        ON rag_documents (last_synced_at)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
            cooperative_id uuid NOT NULL REFERENCES cooperatives(id) ON DELETE CASCADE,
            chunk_index integer NOT NULL,
            content text NOT NULL,
            embedding vector(1536) NOT NULL,
            metadata_json jsonb,
            created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
            updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_chunks_document_chunk_index
        ON rag_chunks (document_id, chunk_index)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_cooperative_id
        ON rag_chunks (cooperative_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_document_id
        ON rag_chunks (document_id)
        """
    )
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

    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_document_id")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_cooperative_id")
    op.execute("DROP INDEX IF EXISTS uq_rag_chunks_document_chunk_index")
    op.execute("DROP TABLE IF EXISTS rag_chunks")

    op.execute("DROP INDEX IF EXISTS ix_rag_documents_last_synced_at")
    op.execute("DROP INDEX IF EXISTS ix_rag_documents_source_table")
    op.execute("DROP INDEX IF EXISTS ix_rag_documents_source_type")
    op.execute("DROP INDEX IF EXISTS ix_rag_documents_cooperative_id")
    op.execute("DROP INDEX IF EXISTS uq_rag_documents_source_scope")
    op.execute("DROP TABLE IF EXISTS rag_documents")
