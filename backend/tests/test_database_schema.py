from app.db.base import Base
from app.db import models  # noqa: F401


def test_core_data_tables_are_registered() -> None:
    expected = {"countries", "leagues", "seasons", "teams", "fixtures"}
    assert expected.issubset(set(Base.metadata.tables))


def test_fixture_identity_has_duplicate_protection() -> None:
    constraints = Base.metadata.tables["fixtures"].constraints
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("season_id", "home_team_id", "away_team_id", "kickoff_at") in unique_columns
