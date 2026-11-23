from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Country, Fixture, League, Season, Team
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    country = Country(name="Test Country", code="TST")
    db.add(country); db.flush()
    league = League(name="Odds Test League", country_id=country.id)
    db.add(league); db.flush()
    season = Season(league_id=league.id, name="2026")
    db.add(season); db.flush()
    home, away = Team(name="Odds Home"), Team(name="Odds Away")
    db.add_all([home, away]); db.flush()
    fixture = Fixture(season_id=season.id, home_team_id=home.id, away_team_id=away.id,
                      kickoff_at=datetime(2026, 12, 1, 12, tzinfo=timezone.utc), status="scheduled")
    db.add(fixture); db.commit()
    fixture_id = fixture.id
    db.close()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.fixture_id = fixture_id
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_bookmaker(client):
    response = client.post("/api/v1/odds/bookmakers", json={"name": "Test Bookmaker", "provider_key": "test"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def quote_payload(client, bookmaker_id, **overrides):
    payload = {
        "fixture_id": client.fixture_id, "bookmaker_id": bookmaker_id,
        "market": "1x2", "selection": "home", "line": None, "decimal_odds": "2.1500",
        "captured_at": "2026-11-30T18:00:00+07:00", "quote_type": "opening",
        "source": "manual", "source_ref": None,
    }
    payload.update(overrides)
    return payload


def test_bookmaker_and_odds_snapshot_round_trip(client):
    bookmaker_id = create_bookmaker(client)
    response = client.post("/api/v1/odds/quotes", json=quote_payload(client, bookmaker_id))
    assert response.status_code == 201, response.text
    assert response.json()["decimal_odds"] == "2.1500"
    listed = client.get(f"/api/v1/odds/fixtures/{client.fixture_id}/quotes")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["bookmaker_name"] == "Test Bookmaker"


def test_duplicate_snapshot_is_rejected(client):
    bookmaker_id = create_bookmaker(client)
    payload = quote_payload(client, bookmaker_id)
    assert client.post("/api/v1/odds/quotes", json=payload).status_code == 201
    duplicate = client.post("/api/v1/odds/quotes", json=payload)
    assert duplicate.status_code == 409


def test_pre_match_quote_after_kickoff_is_rejected(client):
    bookmaker_id = create_bookmaker(client)
    payload = quote_payload(client, bookmaker_id, captured_at="2026-12-01T12:01:00+00:00")
    response = client.post("/api/v1/odds/quotes", json=payload)
    assert response.status_code == 422


def test_live_quote_before_kickoff_is_rejected(client):
    bookmaker_id = create_bookmaker(client)
    payload = quote_payload(client, bookmaker_id, quote_type="live")
    response = client.post("/api/v1/odds/quotes", json=payload)
    assert response.status_code == 422


def test_totals_market_requires_line_and_timezone(client):
    bookmaker_id = create_bookmaker(client)
    missing_line = quote_payload(client, bookmaker_id, market="totals", selection="over")
    assert client.post("/api/v1/odds/quotes", json=missing_line).status_code == 422
    no_timezone = quote_payload(client, bookmaker_id, captured_at="2026-11-30T18:00:00")
    assert client.post("/api/v1/odds/quotes", json=no_timezone).status_code == 422


def test_unknown_fixture_and_bookmaker_are_rejected(client):
    response = client.post("/api/v1/odds/quotes", json=quote_payload(client, 999))
    assert response.status_code == 404
