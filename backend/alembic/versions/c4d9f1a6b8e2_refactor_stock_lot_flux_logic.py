"""refactor stock lot and flux quantity logic

Revision ID: c4d9f1a6b8e2
Revises: e2d7a41c9a6f
Create Date: 2026-04-21 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d9f1a6b8e2"
down_revision: Union[str, None] = "e2d7a41c9a6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("total_stock_kg", sa.Float(), nullable=False, server_default="0"))
    op.add_column("stocks", sa.Column("reserved_in_lots_kg", sa.Float(), nullable=False, server_default="0"))
    op.add_column("stocks", sa.Column("processed_output_kg", sa.Float(), nullable=False, server_default="0"))
    op.execute("UPDATE stocks SET total_stock_kg = quantity")

    op.add_column("batches", sa.Column("unit", sa.String(length=16), nullable=False, server_default="kg"))
    op.add_column(
        "batches",
        sa.Column("ordered_process_steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    op.add_column("process_steps", sa.Column("sequence_order", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("process_steps", sa.Column("loss_value", sa.Float(), nullable=False, server_default="0"))
    op.add_column("process_steps", sa.Column("loss_unit", sa.String(length=16), nullable=False, server_default="kg"))
    op.add_column("process_steps", sa.Column("normalized_loss_value", sa.Float(), nullable=False, server_default="0"))
    op.add_column("process_steps", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, batch_id, status, created_at, waste_qty
            FROM process_steps
            ORDER BY batch_id, date, created_at, id
            """
        )
    ).mappings().all()

    sequence_by_batch = {}
    for row in rows:
        batch_id = row["batch_id"]
        sequence_by_batch[batch_id] = sequence_by_batch.get(batch_id, 0) + 1
        seq = sequence_by_batch[batch_id]
        status = (row["status"] or "").lower()
        executed_at = row["created_at"] if status in ("completed", "flagged") else None
        waste = float(row["waste_qty"] or 0.0)
        conn.execute(
            sa.text(
                """
                UPDATE process_steps
                SET sequence_order = :seq,
                    loss_value = :loss_value,
                    loss_unit = 'kg',
                    normalized_loss_value = :normalized_loss,
                    executed_at = :executed_at
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "seq": seq,
                "loss_value": waste,
                "normalized_loss": waste,
                "executed_at": executed_at,
            },
        )


def downgrade() -> None:
    op.drop_column("process_steps", "executed_at")
    op.drop_column("process_steps", "normalized_loss_value")
    op.drop_column("process_steps", "loss_unit")
    op.drop_column("process_steps", "loss_value")
    op.drop_column("process_steps", "sequence_order")

    op.drop_column("batches", "ordered_process_steps")
    op.drop_column("batches", "unit")

    op.drop_column("stocks", "processed_output_kg")
    op.drop_column("stocks", "reserved_in_lots_kg")
    op.drop_column("stocks", "total_stock_kg")
