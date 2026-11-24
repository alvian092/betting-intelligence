from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Bookmaker, Country, Fixture, League, OddsQuote, Season, Team
from app.services.analytics.financial_backtest import calculate_financial_backtest


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def seed_fixture(db):
    country = Country(name="Testland", code="TST")
    db.add(country)
    db.flush()
    league = League(name="Financial Test League", country_id=country.id)
    db.add(league)
    db.flush()
    season = Season(league_id=league.id, name="2026")
    home, away = Team(name="Home FC"), Team(name="Away FC")
    bookmaker = Bookmaker(name="Test Book")
    db.add_all([season, home, away, bookmaker])
    db.flush()
    kickoff = datetime(2026, 11, 24, 18, tzinfo=timezone.utc)
    fixture = Fixture(
        season_id=season.id, home_team_id=home.id, away_team_id=away.id,
        kickoff_at=kickoff, status="finished", home_goals=2, away_goals=0,
    )
    db.add(fixture)
    db.commit()
    return fixture, bookmaker


def add_snapshot(db, fixture, bookmaker, captured, quote_type, prices):
    for selection, odds in prices.items():
        db.add(OddsQuote(
            fixture_id=fixture.id, bookmaker_id=bookmaker.id, market="1x2",
            selection=selection, decimal_odds=odds, captured_at=captured,
            quote_type=quote_type, source="manual",
        ))
    db.commit()


def test_financial_backtest_places_best_value_and_calculates_clv(db):
    fixture, bookmaker = seed_fixture(db)
    add_snapshot(db, fixture, bookmaker, fixture.kickoff_at - timedelta(hours=2), "opening",
                 {"home": 2.0, "draw": 4.0, "away": 5.0})
    add_snapshot(db, fixture, bookmaker, fixture.kickoff_at, "closing",
                 {"home": 1.8, "draw": 4.0, "away": 5.0})
    prediction = {
        "fixture_id": fixture.id, "actual": "home",
        "probabilities": {"home": 0.7, "draw": 0.2, "away": 0.1},
    }
    result = calculate_financial_backtest(db, [prediction], {fixture.id: fixture})
    assert result["bets_placed"] == 1
    assert result["bets"][0]["selection"] == "home"
    assert result["bets"][0]["result"] == "won"
    assert result["profit_units"] == pytest.approx(1.0)
    assert result["roi"] == pytest.approx(1.0)
    assert result["closing_odds_coverage"] == 1
    assert result["clv_probability_points"] > 0


def test_financial_backtest_never_uses_quotes_captured_at_or_after_kickoff_for_decisions(db):
    fixture, bookmaker = seed_fixture(db)
    add_snapshot(db, fixture, bookmaker, fixture.kickoff_at, "current",
                 {"home": 2.0, "draw": 4.0, "away": 5.0})
    prediction = {
        "fixture_id": fixture.id, "actual": "home",
        "probabilities": {"home": 0.7, "draw": 0.2, "away": 0.1},
    }
    result = calculate_financial_backtest(db, [prediction], {fixture.id: fixture})
    assert result["bets_placed"] == 0
    assert result["fixtures_without_qualifying_odds"] == 1
    assert result["roi"] is None
    assert result["clv_probability_points"] is None


def test_financial_backtest_uses_latest_complete_snapshot_not_best_historical_price(db):
    fixture, bookmaker = seed_fixture(db)
    add_snapshot(db, fixture, bookmaker, fixture.kickoff_at - timedelta(hours=3), "opening",
                 {"home": 2.0, "draw": 4.0, "away": 5.0})
    add_snapshot(db, fixture, bookmaker, fixture.kickoff_at - timedelta(hours=1), "current",
                 {"home": 1.4, "draw": 4.0, "away": 5.0})
    prediction = {
        "fixture_id": fixture.id, "actual": "home",
        "probabilities": {"home": 0.7, "draw": 0.2, "away": 0.1},
    }
    result = calculate_financial_backtest(db, [prediction], {fixture.id: fixture})
    assert result["bets_placed"] == 0
    assert result["fixtures_without_qualifying_odds"] == 1
