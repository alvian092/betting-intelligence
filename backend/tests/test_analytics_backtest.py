from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Country, Fixture, League, Season, Team
from app.services.analytics.backtest import run_chronological_backtest


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def seed_history(db):
    country = Country(name="England", code="ENG")
    db.add(country)
    db.flush()
    league = League(name="Backtest League", country_id=country.id)
    db.add(league)
    db.flush()
    season = Season(league_id=league.id, name="2025")
    db.add(season)
    db.flush()
    teams = [Team(name=f"Backtest Team {i}") for i in range(4)]
    db.add_all(teams)
    db.flush()
    results = [
        (0,1,3,0),(2,0,1,1),(0,3,2,0),(1,0,0,2),(0,2,2,1),(3,0,1,1),
        (0,1,4,0),(2,0,0,1),(1,0,2,0),(0,3,3,1),(0,2,1,0),(3,0,0,2),
    ]
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i, (home, away, hg, ag) in enumerate(results):
        db.add(Fixture(
            season_id=season.id, home_team_id=teams[home].id, away_team_id=teams[away].id,
            kickoff_at=base + timedelta(days=i), status="finished", home_goals=hg, away_goals=ag,
        ))
    db.commit()
    return league.id, season.id, [team.id for team in teams], base


def test_walk_forward_backtest_excludes_fixtures_without_prior_history(db):
    league_id, season_id, teams, base = seed_history(db)
    db.add(Fixture(
        season_id=season_id, home_team_id=teams[0], away_team_id=teams[1],
        kickoff_at=base + timedelta(days=13), status="finished", home_goals=2, away_goals=1,
    ))
    db.commit()

    result = run_chronological_backtest(db, league_id)

    assert result["method"] == "strict_chronological_walk_forward"
    assert result["fixtures_considered"] == 13
    assert result["predictions_evaluated"] >= 1
    assert result["fixtures_skipped_insufficient_history"] >= 1
    assert 0 <= result["metrics"]["accuracy_1x2"] <= 1
    assert result["metrics"]["brier_score_1x2"] >= 0
    assert result["metrics"]["log_loss_1x2"] >= 0
    assert result["financial_metrics"]["roi"] is None
    assert "not stored" in result["financial_metrics"]["unavailable_reason"]


def test_backtest_returns_null_metrics_when_no_fixture_has_enough_history(db):
    league_id, _, _, _ = seed_history(db)
    result = run_chronological_backtest(db, league_id, min_league_matches=100)
    assert result["predictions_evaluated"] == 0
    assert result["metrics"]["accuracy_1x2"] is None
    assert result["financial_metrics"]["clv"] is None
