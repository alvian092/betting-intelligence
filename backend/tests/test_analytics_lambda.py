from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models import Country, Fixture, League, Season, Team
from app.services.analytics.lambda_model import InsufficientHistoryError, estimate_match_lambdas

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close(); Base.metadata.drop_all(engine); engine.dispose()

def seed_history(db):
    country = Country(name="England", code="ENG"); db.add(country); db.flush()
    league = League(name="Test League", country_id=country.id); db.add(league); db.flush()
    season = Season(league_id=league.id, name="2025"); db.add(season); db.flush()
    teams = [Team(name=f"Team {i}") for i in range(4)]; db.add_all(teams); db.flush()
    results = [(0,1,3,0),(2,0,1,1),(0,3,2,0),(1,0,0,2),(0,2,2,1),(3,0,1,1),
               (0,1,4,0),(2,0,0,1),(1,0,2,0),(0,3,3,1),(0,2,1,0),(3,0,0,2)]
    base = datetime(2025,1,1,tzinfo=timezone.utc)
    for i,(home,away,hg,ag) in enumerate(results):
        db.add(Fixture(season_id=season.id,home_team_id=teams[home].id,away_team_id=teams[away].id,
                       kickoff_at=base+timedelta(days=i),status="finished",home_goals=hg,away_goals=ag))
    db.commit()
    return league.id,[team.id for team in teams],base

def test_estimates_positive_lambdas_and_audit_metadata(db):
    league,teams,_ = seed_history(db)
    result = estimate_match_lambdas(db,league,teams[0],teams[1])
    assert result["home_lambda"] > 0 and result["away_lambda"] > 0
    assert result["matches_used"] == 12
    assert result["status"] == "provisional_not_backtested"

def test_cutoff_excludes_future_matches(db):
    league,teams,base = seed_history(db)
    with pytest.raises(InsufficientHistoryError):
        estimate_match_lambdas(db,league,teams[0],teams[1],before=base+timedelta(days=5),min_league_matches=10)

def test_rejects_same_team(db):
    league,teams,_ = seed_history(db)
    with pytest.raises(ValueError,match="different"):
        estimate_match_lambdas(db,league,teams[0],teams[0])

def test_rejects_small_team_sample(db):
    league,teams,_ = seed_history(db)
    with pytest.raises(InsufficientHistoryError,match="team requires"):
        estimate_match_lambdas(db,league,teams[0],teams[1],min_team_matches=99)
