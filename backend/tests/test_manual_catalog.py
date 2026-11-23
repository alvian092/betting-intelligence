from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


def test_manual_catalog_crud_and_validation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            country = client.post("/api/v1/catalog/countries", json={"name": "England", "code": "eng"})
            assert country.status_code == 201
            country_id = country.json()["id"]
            league = client.post("/api/v1/catalog/leagues", json={"name": "Premier League", "country_id": country_id})
            assert league.status_code == 201
            league_id = league.json()["id"]
            season = client.post("/api/v1/catalog/seasons", json={"league_id": league_id, "name": "2025-2026"})
            assert season.status_code == 201
            season_id = season.json()["id"]
            home = client.post("/api/v1/catalog/teams", json={"name": "Liverpool", "country_code": "eng"})
            away = client.post("/api/v1/catalog/teams", json={"name": "Bournemouth", "country_code": "ENG"})
            assert home.status_code == away.status_code == 201
            fixture_payload = {"season_id": season_id, "home_team_id": home.json()["id"], "away_team_id": away.json()["id"],
                               "kickoff_at": "2025-08-15T15:00:00Z", "status": "finished", "home_goals": 4, "away_goals": 2}
            fixture = client.post("/api/v1/catalog/fixtures", json=fixture_payload)
            assert fixture.status_code == 201
            assert client.get("/api/v1/catalog/teams?search=liv").json()[0]["name"] == "Liverpool"
            assert client.get("/api/v1/catalog/fixtures?team_id=" + str(home.json()["id"])).json()[0]["home_goals"] == 4
            bad = dict(fixture_payload, away_team_id=home.json()["id"])
            assert client.post("/api/v1/catalog/fixtures", json=bad).status_code == 422
            assert client.put("/api/v1/catalog/teams/999", json={"name": "Unknown"}).status_code == 404
            # Referenced master data must be protected from accidental deletion.
            assert client.delete(f"/api/v1/catalog/countries/{country_id}").status_code == 409
            assert client.delete(f"/api/v1/catalog/leagues/{league_id}").status_code == 409
            assert client.delete(f"/api/v1/catalog/seasons/{season_id}").status_code == 409
            assert client.delete(f"/api/v1/catalog/teams/{home.json()['id']}").status_code == 409
            # Delete leaf records first; then their now-unused parent records can be removed.
            assert client.delete(f"/api/v1/catalog/fixtures/{fixture.json()['id']}").status_code == 200
            assert client.delete(f"/api/v1/catalog/seasons/{season_id}").status_code == 200
            assert client.delete(f"/api/v1/catalog/leagues/{league_id}").status_code == 200
            assert client.delete(f"/api/v1/catalog/countries/{country_id}").status_code == 200
            assert client.delete(f"/api/v1/catalog/teams/{home.json()['id']}").status_code == 200
            assert client.delete(f"/api/v1/catalog/teams/{away.json()['id']}").status_code == 200
            assert client.delete("/api/v1/catalog/teams/999").status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
