"""add ai chat audit logs table

Revision ID: 1f3e5a7b9c21
Revises: 8ab1d3f4c9e7
Create Date: 2026-05-12 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f3e5a7b9c21"
down_revision: Union[str, None] = "8ab1d3f4c9e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.String(length=120), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("cooperative_id", sa.Uuid(), nullable=True),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=16), nullable=False),
        sa.Column("detected_entities", sa.JSON(), nullable=False),
        sa.Column("selected_route", sa.String(length=48), nullable=False),
        sa.Column("route_confidence", sa.Float(), nullable=False),
        sa.Column("agents_used", sa.JSON(), nullable=False),
        sa.Column("sql_sources", sa.JSON(), nullable=False),
        sa.Column("rag_sources", sa.JSON(), nullable=False),
        sa.Column("ml_sources", sa.JSON(), nullable=False),
        sa.Column("final_confidence", sa.Float(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("response_preview", sa.Text(), nullable=False),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_audit_logs_conversation_id"), "ai_chat_audit_logs", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_audit_logs_user_id"), "ai_chat_audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_audit_logs_cooperative_id"), "ai_chat_audit_logs", ["cooperative_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_chat_audit_logs_cooperative_id"), table_name="ai_chat_audit_logs")
    op.drop_index(op.f("ix_ai_chat_audit_logs_user_id"), table_name="ai_chat_audit_logs")
    op.drop_index(op.f("ix_ai_chat_audit_logs_conversation_id"), table_name="ai_chat_audit_logs")
    op.drop_table("ai_chat_audit_logs")
