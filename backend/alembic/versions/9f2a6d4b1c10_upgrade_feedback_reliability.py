"""upgrade feedback reliability schema

Revision ID: 9f2a6d4b1c10
Revises: 578e8a300e78
Create Date: 2026-04-17 14:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f2a6d4b1c10'
down_revision: Union[str, None] = '578e8a300e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recommendation_feedback_logs', sa.Column('batch_id', sa.Uuid(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('stage', sa.String(length=120), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('context_snapshot', sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column('recommendation_feedback_logs', sa.Column('recommendation_snapshot', sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column('recommendation_feedback_logs', sa.Column('shown_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column('recommendation_feedback_logs', sa.Column('accepted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('recommendation_feedback_logs', sa.Column('executed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('recommendation_feedback_logs', sa.Column('outcome_window_hours', sa.Integer(), nullable=False, server_default='48'))
    op.add_column('recommendation_feedback_logs', sa.Column('outcome_recorded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('loss_before', sa.Float(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('loss_after', sa.Float(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('delta_loss', sa.Float(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('operator_reason', sa.Text(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('outcome_label', sa.String(length=24), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('confidence_bucket', sa.String(length=12), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('harmful_probability', sa.Float(), nullable=True))
    op.add_column('recommendation_feedback_logs', sa.Column('manual_review_required', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('recommendation_feedback_logs', sa.Column('is_holdout', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('recommendation_feedback_logs', sa.Column('model_version', sa.String(length=80), nullable=True))
    op.create_index(op.f('ix_recommendation_feedback_logs_batch_id'), 'recommendation_feedback_logs', ['batch_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recommendation_feedback_logs_batch_id'), table_name='recommendation_feedback_logs')
    op.drop_column('recommendation_feedback_logs', 'model_version')
    op.drop_column('recommendation_feedback_logs', 'is_holdout')
    op.drop_column('recommendation_feedback_logs', 'manual_review_required')
    op.drop_column('recommendation_feedback_logs', 'harmful_probability')
    op.drop_column('recommendation_feedback_logs', 'confidence_bucket')
    op.drop_column('recommendation_feedback_logs', 'confidence_score')
    op.drop_column('recommendation_feedback_logs', 'outcome_label')
    op.drop_column('recommendation_feedback_logs', 'operator_reason')
    op.drop_column('recommendation_feedback_logs', 'delta_loss')
    op.drop_column('recommendation_feedback_logs', 'loss_after')
    op.drop_column('recommendation_feedback_logs', 'loss_before')
    op.drop_column('recommendation_feedback_logs', 'outcome_recorded_at')
    op.drop_column('recommendation_feedback_logs', 'outcome_window_hours')
    op.drop_column('recommendation_feedback_logs', 'executed')
    op.drop_column('recommendation_feedback_logs', 'accepted')
    op.drop_column('recommendation_feedback_logs', 'shown_at')
    op.drop_column('recommendation_feedback_logs', 'recommendation_snapshot')
    op.drop_column('recommendation_feedback_logs', 'context_snapshot')
    op.drop_column('recommendation_feedback_logs', 'stage')
    op.drop_column('recommendation_feedback_logs', 'batch_id')
