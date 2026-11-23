"""Create initial football data foundation tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=3), nullable=True),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_countries_name", "countries", ["name"], unique=False)

    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.UniqueConstraint("country_id", "name", name="uq_league_country_name"),
    )
    op.create_index("ix_leagues_name", "leagues", ["name"], unique=False)
    op.create_index("ix_leagues_external_id", "leagues", ["external_id"], unique=False)

    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.UniqueConstraint("league_id", "name", name="uq_season_league_name"),
    )
    op.create_index("ix_seasons_league_id", "seasons", ["league_id"], unique=False)

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=False)
    op.create_index("ix_teams_external_id", "teams", ["external_id"], unique=False)

    op.create_table(
        "fixtures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("home_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("away_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "season_id", "home_team_id", "away_team_id", "kickoff_at",
            name="uq_fixture_identity",
        ),
    )
    op.create_index("ix_fixtures_season_id", "fixtures", ["season_id"], unique=False)
    op.create_index("ix_fixtures_home_team_id", "fixtures", ["home_team_id"], unique=False)
    op.create_index("ix_fixtures_away_team_id", "fixtures", ["away_team_id"], unique=False)
    op.create_index("ix_fixtures_kickoff_at", "fixtures", ["kickoff_at"], unique=False)
    op.create_index("ix_fixtures_status", "fixtures", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("fixtures")
    op.drop_table("teams")
    op.drop_table("seasons")
    op.drop_table("leagues")
    op.drop_table("countries")
