"""Add bookmaker registry and timestamped odds quotes."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_historical_odds"
down_revision: Union[str, None] = "0002_import_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bookmakers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("provider_key", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bookmakers_name", "bookmakers", ["name"])
    op.create_index("ix_bookmakers_provider_key", "bookmakers", ["provider_key"])
    op.create_table(
        "odds_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), sa.ForeignKey("fixtures.id"), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), sa.ForeignKey("bookmakers.id"), nullable=False),
        sa.Column("market", sa.String(length=40), nullable=False),
        sa.Column("selection", sa.String(length=80), nullable=False),
        sa.Column("line", sa.Numeric(8, 3), nullable=True),
        sa.Column("decimal_odds", sa.Numeric(10, 4), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_type", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fixture_id", "bookmaker_id", "market", "selection", "line", "captured_at", name="uq_odds_quote_snapshot"),
    )
    for column in ("fixture_id", "bookmaker_id", "market", "captured_at", "quote_type"):
        op.create_index(f"ix_odds_quotes_{column}", "odds_quotes", [column])
    op.create_index("ix_odds_fixture_market_time", "odds_quotes", ["fixture_id", "market", "captured_at"])


def downgrade() -> None:
    op.drop_table("odds_quotes")
    op.drop_table("bookmakers")
