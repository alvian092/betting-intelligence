import csv
import io
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Bookmaker, Country, Fixture, ImportBatch, League, OddsQuote, Season, Team
from app.db.session import get_db
from app.main import app

COLUMNS = ["fixture_id", "bookmaker", "market", "selection", "line", "decimal_odds", "captured_at", "quote_type", "source", "source_ref"]


def make_csv(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def row(**changes):
    result = dict(fixture_id=1, bookmaker="Test Bookmaker", market="1x2", selection="home",
                  line="", decimal_odds="2.1500", captured_at="2026-11-30T18:00:00+07:00",
                  quote_type="opening", source="manual", source_ref="")
    result.update(changes)
    return result


def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    country = Country(name="Odds Import Country", code="OIC")
    db.add(country); db.flush()
    league = League(name="Odds Import League", country_id=country.id)
    db.add(league); db.flush()
    season = Season(league_id=league.id, name="2026")
    db.add(season); db.flush()
    home, away = Team(name="Import Home"), Team(name="Import Away")
    bookmaker = Bookmaker(name="Test Bookmaker")
    db.add_all([home, away, bookmaker]); db.flush()
    fixture = Fixture(season_id=season.id, home_team_id=home.id, away_team_id=away.id,
        kickoff_at=datetime(2026, 12, 1, 12, tzinfo=timezone.utc), status="scheduled")
    db.add(fixture); db.commit()
    fixture_id, bookmaker_id = fixture.id, bookmaker.id
    db.close()

    def override():
        session = Session()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = override
    test_client = TestClient(app)
    test_client.engine = engine
    test_client.Session = Session
    test_client.ids = fixture_id, bookmaker_id
    return test_client


def close_client(client):
    client.close()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(client.engine)
    client.engine.dispose()


def test_csv_odds_import_and_duplicate_count():
    client = client_fixture()
    try:
        payload = make_csv([row(), row()])
        response = client.post("/api/v1/odds/import/csv", files={"file": ("odds.csv", payload, "text/csv")})
        assert response.status_code == 200, response.text
        assert response.json()["imported"] == 1
        assert response.json()["duplicates_skipped"] == 1
        db = client.Session()
        assert len(db.scalars(select(OddsQuote)).all()) == 1
        batch = db.scalar(select(ImportBatch).where(ImportBatch.file_format == "odds_csv"))
        assert batch and batch.status == "completed"
        db.close()
    finally:
        close_client(client)


def test_invalid_row_rejects_entire_file_and_records_failed_batch():
    client = client_fixture()
    try:
        payload = make_csv([row(), row(decimal_odds="1.0")])
        response = client.post("/api/v1/odds/import/csv", files={"file": ("odds.csv", payload, "text/csv")})
        assert response.status_code == 422
        db = client.Session()
        assert db.scalars(select(OddsQuote)).all() == []
        batch = db.scalar(select(ImportBatch).where(ImportBatch.file_format == "odds_csv"))
        assert batch and batch.status == "failed"
        db.close()
    finally:
        close_client(client)


def test_csv_odds_import_rejects_unknown_bookmaker_and_after_kickoff():
    client = client_fixture()
    try:
        unknown = client.post("/api/v1/odds/import/csv", files={"file": ("odds.csv", make_csv([row(bookmaker="Unknown")]), "text/csv")})
        assert unknown.status_code == 422
        late = client.post("/api/v1/odds/import/csv", files={"file": ("odds.csv", make_csv([row(captured_at="2026-12-01T12:01:00+00:00")]), "text/csv")})
        assert late.status_code == 422
    finally:
        close_client(client)


def test_odds_import_template_and_excel_import():
    client = client_fixture()
    try:
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.append(COLUMNS)
        sheet.append([1, "Test Bookmaker", "totals", "over", 2.5, 1.95,
                      "2026-11-30T18:00:00+07:00", "opening", "manual", ""])
        output = io.BytesIO()
        book.save(output)
        template = client.get("/api/v1/odds/templates/csv")
        assert template.status_code == 200 and "fixture_id" in template.text
        response = client.post("/api/v1/odds/import/excel",
            files={"file": ("odds.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert response.status_code == 200, response.text
        assert response.json()["imported"] == 1
    finally:
        close_client(client)
