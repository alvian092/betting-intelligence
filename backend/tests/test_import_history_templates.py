from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ImportBatch
from app.db.session import get_db
from app.main import app


def test_templates_and_import_history():
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
            csv_template = client.get("/api/v1/imports/templates/fixtures.csv")
            assert csv_template.status_code == 200
            assert csv_template.text.splitlines()[0] == "date,league,season,home_team,away_team,home_goals,away_goals"

            excel_template = client.get("/api/v1/imports/templates/fixtures.xlsx")
            assert excel_template.status_code == 200
            workbook = load_workbook(BytesIO(excel_template.content), read_only=True)
            assert list(workbook.active.values)[0] == ("date", "league", "season", "home_team", "away_team", "home_goals", "away_goals")
            workbook.close()

            csv_data = (
                "date,league,season,home_team,away_team,home_goals,away_goals\n"
                "2025-08-15,Premier League,2025-2026,Liverpool,Bournemouth,4,2\n"
            )
            uploaded = client.post("/api/v1/imports/fixtures/csv", files={"file": ("matches.csv", csv_data, "text/csv")})
            assert uploaded.status_code == 200

            invalid = client.post("/api/v1/imports/fixtures/csv", files={"file": ("broken.csv", "bad\n", "text/csv")})
            assert invalid.status_code == 422

            history = client.get("/api/v1/imports/history")
            assert history.status_code == 200
            items = history.json()["items"]
            assert len(items) == 2
            assert {item["status"] for item in items} == {"completed", "failed"}
            assert {item["filename"] for item in items} == {"matches.csv", "broken.csv"}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_cors_preflight_allows_vite_origin():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/imports/fixtures/csv",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_sqlite_export_and_reimport_round_trip():
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
            csv_data = (
                "date,league,season,home_team,away_team,home_goals,away_goals\n"
                "2025-08-15,Premier League,2025-2026,Liverpool,Bournemouth,4,2\n"
            )
            created = client.post("/api/v1/imports/fixtures/csv", files={"file": ("matches.csv", csv_data, "text/csv")})
            assert created.status_code == 200
            exported = client.get("/api/v1/imports/fixtures/export.sqlite")
            assert exported.status_code == 200
            assert exported.content[:16] == b"SQLite format 3\\x00"
            imported = client.post("/api/v1/imports/fixtures/sqlite", files={"file": ("backup.sqlite", exported.content, "application/vnd.sqlite3")})
            assert imported.status_code == 200
            assert imported.json()["imported"] == 0
            assert imported.json()["duplicates_skipped"] == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
