"""restore missing revision anchor

Revision ID: 2b7e4d1c9a55
Revises: c4d9f1a6b8e2
Create Date: 2026-05-16 13:15:00.000000
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision = "2b7e4d1c9a55"
down_revision = "c4d9f1a6b8e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compatibility anchor: keeps migration history connected for databases
    # already stamped at this revision. No schema change is required here.
    pass


def downgrade() -> None:
    pass
