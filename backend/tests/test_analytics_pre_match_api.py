from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Country, Fixture, League, Season, Team
from app.db.session import get_db
from app.main import app


def test_pre_match_endpoint_combines_historical_lambdas_and_markets():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        db = TestingSession()
        country = Country(name="England", code="ENG")
        db.add(country); db.flush()
        league = League(name="Integration League", country_id=country.id)
        db.add(league); db.flush()
        season = Season(league_id=league.id, name="2025")
        db.add(season); db.flush()
        teams = [Team(name=f"Club {i}") for i in range(4)]
        db.add_all(teams); db.flush()
        results = [(0,1,3,0),(2,0,1,1),(0,3,2,0),(1,0,0,2),(0,2,2,1),(3,0,1,1),
                   (0,1,4,0),(2,0,0,1),(1,0,2,0),(0,3,3,1),(0,2,1,0),(3,0,0,2)]
        base = datetime(2025,1,1,tzinfo=timezone.utc)
        for i,(home,away,hg,ag) in enumerate(results):
            db.add(Fixture(season_id=season.id,home_team_id=teams[home].id,away_team_id=teams[away].id,
                           kickoff_at=base+timedelta(days=i),status="finished",home_goals=hg,away_goals=ag))
        db.commit()
        league_id, home_id, away_id = league.id, teams[0].id, teams[1].id
        db.close()

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/pre-match", params={
                "league_id": league_id, "home_team_id": home_id, "away_team_id": away_id,
                "rho": -0.08, "max_goals": 10,
            })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["model"] == "poisson_dixon_coles_v1"
        assert result["parameters"]["rho"] == -0.08
        assert len(result["score_matrix"]) == 11
        assert sum(result["markets"]["1x2"].values()) > 0.999
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
