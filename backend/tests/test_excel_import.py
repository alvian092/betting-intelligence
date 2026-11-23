from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Fixture
from app.db.session import get_db
from app.main import app

HEADERS = ["date", "league", "season", "home_team", "away_team", "home_goals", "away_goals"]


def make_xlsx(rows, headers=HEADERS):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


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


def upload(client, content, filename="matches.xlsx"):
    return client.post(
        "/api/v1/imports/fixtures/excel",
        files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_excel_import_creates_fixture(client):
    content = make_xlsx([["2025-08-15", "Premier League", "2025-2026", "Liverpool", "Bournemouth", 4, 2]])
    response = upload(client, content)
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["duplicates_skipped"] == 0


def test_excel_import_detects_duplicates_in_file(client):
    row = ["2025-08-15", "Premier League", "2025-2026", "Liverpool", "Bournemouth", 4, 2]
    response = upload(client, make_xlsx([row, row]))
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["duplicates_skipped"] == 1


def test_excel_validation_is_atomic(client):
    rows = [
        ["2025-08-15", "Premier League", "2025-2026", "Liverpool", "Bournemouth", 4, 2],
        ["bad-date", "Premier League", "2025-2026", "Arsenal", "Chelsea", -1, 0],
    ]
    response = upload(client, make_xlsx(rows))
    assert response.status_code == 422
    assert response.json()["detail"]["invalid_rows"][0]["row"] == 3


def test_excel_rejects_corrupt_file(client):
    response = upload(client, b"not an excel workbook")
    assert response.status_code == 422
