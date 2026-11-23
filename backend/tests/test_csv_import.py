from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Fixture
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_csv_import_creates_fixture(client):
    csv_data = (
        "date,league,season,home_team,away_team,home_goals,away_goals\n"
        "2025-08-15,Premier League,2025-2026,Liverpool,Bournemouth,4,2\n"
    )
    response = client.post(
        "/api/v1/imports/fixtures/csv",
        files={"file": ("matches.csv", csv_data, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["duplicates_skipped"] == 0


def test_csv_import_skips_duplicate_rows_in_same_file(client):
    line = "2025-08-15,Premier League,2025-2026,Liverpool,Bournemouth,4,2"
    response = client.post(
        "/api/v1/imports/fixtures/csv",
        files={"file": ("matches.csv", f"date,league,season,home_team,away_team,home_goals,away_goals\n{line}\n{line}\n", "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["duplicates_skipped"] == 1


def test_csv_validation_is_atomic(client):
    csv_data = (
        "date,league,season,home_team,away_team,home_goals,away_goals\n"
        "2025-08-15,Premier League,2025-2026,Liverpool,Bournemouth,4,2\n"
        "bad-date,Premier League,2025-2026,Arsenal,Chelsea,-1,0\n"
    )
    response = client.post(
        "/api/v1/imports/fixtures/csv",
        files={"file": ("matches.csv", csv_data, "text/csv")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["invalid_rows"][0]["row"] == 3
