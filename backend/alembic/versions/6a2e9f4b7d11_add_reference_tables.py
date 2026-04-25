"""add reference metric and knowledge chunk tables

Revision ID: 6a2e9f4b7d11
Revises: 9f2a6d4b1c10
Create Date: 2026-04-18 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a2e9f4b7d11'
down_revision: Union[str, None] = '9f2a6d4b1c10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reference_metrics',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_id', sa.String(length=120), nullable=False),
        sa.Column('country', sa.String(length=80), nullable=False),
        sa.Column('region', sa.String(length=120), nullable=False),
        sa.Column('crop', sa.String(length=120), nullable=False),
        sa.Column('metric', sa.String(length=160), nullable=False),
        sa.Column('period', sa.String(length=40), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=40), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reference_metrics')),
    )
    op.create_index(op.f('ix_reference_metrics_source_id'), 'reference_metrics', ['source_id'], unique=False)
    op.create_index(op.f('ix_reference_metrics_country'), 'reference_metrics', ['country'], unique=False)
    op.create_index(op.f('ix_reference_metrics_region'), 'reference_metrics', ['region'], unique=False)
    op.create_index(op.f('ix_reference_metrics_crop'), 'reference_metrics', ['crop'], unique=False)
    op.create_index(op.f('ix_reference_metrics_metric'), 'reference_metrics', ['metric'], unique=False)

    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_id', sa.String(length=120), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('country', sa.String(length=80), nullable=False),
        sa.Column('region', sa.String(length=120), nullable=False),
        sa.Column('crop', sa.String(length=120), nullable=False),
        sa.Column('topic', sa.String(length=120), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_chunks')),
    )
    op.create_index(op.f('ix_knowledge_chunks_source_id'), 'knowledge_chunks', ['source_id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_country'), 'knowledge_chunks', ['country'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_region'), 'knowledge_chunks', ['region'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_crop'), 'knowledge_chunks', ['crop'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_topic'), 'knowledge_chunks', ['topic'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_knowledge_chunks_topic'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_crop'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_region'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_country'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_source_id'), table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')

    op.drop_index(op.f('ix_reference_metrics_metric'), table_name='reference_metrics')
    op.drop_index(op.f('ix_reference_metrics_crop'), table_name='reference_metrics')
    op.drop_index(op.f('ix_reference_metrics_region'), table_name='reference_metrics')
    op.drop_index(op.f('ix_reference_metrics_country'), table_name='reference_metrics')
    op.drop_index(op.f('ix_reference_metrics_source_id'), table_name='reference_metrics')
    op.drop_table('reference_metrics')
