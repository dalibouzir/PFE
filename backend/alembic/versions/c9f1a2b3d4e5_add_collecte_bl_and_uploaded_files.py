"""add collecte BL and uploaded files metadata

Revision ID: c9f1a2b3d4e5
Revises: f1b7c3d9e4a2
Create Date: 2026-05-16 19:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9f1a2b3d4e5"
down_revision: Union[str, None] = "f1b7c3d9e4a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["cooperative_id"],
            ["cooperatives.id"],
            name=op.f("fk_uploaded_files_cooperative_id_cooperatives"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_files")),
    )
    op.create_index(op.f("ix_uploaded_files_cooperative_id"), "uploaded_files", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_uploaded_files_entity_id"), "uploaded_files", ["entity_id"], unique=False)
    op.create_index(op.f("ix_uploaded_files_entity_type"), "uploaded_files", ["entity_type"], unique=False)

    op.add_column("inputs", sa.Column("bl_number", sa.String(length=80), nullable=True))
    op.add_column("inputs", sa.Column("justificatif_file_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_inputs_bl_number"), "inputs", ["bl_number"], unique=False)
    op.create_index(op.f("ix_inputs_justificatif_file_id"), "inputs", ["justificatif_file_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_inputs_justificatif_file_id_uploaded_files"),
        "inputs",
        "uploaded_files",
        ["justificatif_file_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_inputs_justificatif_file_id_uploaded_files"), "inputs", type_="foreignkey")
    op.drop_index(op.f("ix_inputs_justificatif_file_id"), table_name="inputs")
    op.drop_index(op.f("ix_inputs_bl_number"), table_name="inputs")
    op.drop_column("inputs", "justificatif_file_id")
    op.drop_column("inputs", "bl_number")

    op.drop_index(op.f("ix_uploaded_files_entity_type"), table_name="uploaded_files")
    op.drop_index(op.f("ix_uploaded_files_entity_id"), table_name="uploaded_files")
    op.drop_index(op.f("ix_uploaded_files_cooperative_id"), table_name="uploaded_files")
    op.drop_table("uploaded_files")
