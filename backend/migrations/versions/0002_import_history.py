"""Add auditable import batch history."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_import_history"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_batches_file_format", "import_batches", ["file_format"])
    op.create_index("ix_import_batches_status", "import_batches", ["status"])
    op.create_index("ix_import_batches_created_at", "import_batches", ["created_at"])


def downgrade() -> None:
    op.drop_table("import_batches")
