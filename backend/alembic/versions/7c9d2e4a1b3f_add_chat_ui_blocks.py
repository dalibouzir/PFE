"""add chat ui blocks

Revision ID: 7c9d2e4a1b3f
Revises: 3f4c2a1b9d7e
Create Date: 2026-04-28 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c9d2e4a1b3f"
down_revision: Union[str, None] = "3f4c2a1b9d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("ui_blocks_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "ui_blocks_json")
