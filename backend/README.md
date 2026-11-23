# Backend foundation

Python/FastAPI service for Betting Intelligence.

## Local setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the OpenAPI documentation.

## Database

SQLAlchemy models define the initial reference-data schema:

- Countries
- Leagues
- Seasons
- Teams
- Fixtures

Alembic owns schema changes. After pulling updates, apply migrations from this directory with `alembic upgrade head`. The default local database is SQLite; PostgreSQL can be configured with `DATABASE_URL`.

## Health checks

- `GET /api/v1/health` checks that the API process is running.
- `GET /api/v1/health/ready` checks database connectivity.

## Tests

From the repository root:

```bash
cd backend
pytest -q
```

CI applies all Alembic migrations to a temporary SQLite database before running the test suite.

## CSV fixture import (v1.0)

Endpoint: `POST /api/v1/imports/fixtures/csv` (multipart form field: `file`).

Required CSV header:

```csv
date,league,season,home_team,away_team,home_goals,away_goals
2025-08-15,Premier League,2025-2026,Liverpool,Bournemouth,4,2
```

Dates must use `YYYY-MM-DD`; goals must be non-negative integers. Files are limited to 10 MB and 50,000 data rows. Duplicate fixtures are skipped and counted. If any row fails validation, the entire file is rejected with HTTP 422 and row-level details; no rows are committed. The endpoint creates missing league, season, and team reference records as needed.

Example response:

```json
{
  "status": "completed",
  "rows_received": 1,
  "imported": 1,
  "duplicates_skipped": 0,
  "invalid_rows": 0,
  "message": "CSV berhasil diproses"
}
```

## Excel fixture import

Endpoint: `POST /api/v1/imports/fixtures/excel` (multipart form field: `file`; accepted file extension: `.xlsx`).

Use the same required columns and validation rules as CSV. The importer reads the active worksheet, accepts Excel date cells or ISO date text, skips completely blank rows, and enforces the same 10 MB and 50,000-row limits. Duplicate fixtures are skipped. Any invalid row rejects the entire import with HTTP 422 and row-level details; no data is committed.


## Templates, history, and SQLite

- `GET /api/v1/imports/templates/fixtures.csv` downloads the CSV template.
- `GET /api/v1/imports/templates/fixtures.xlsx` downloads the Excel template.
- `GET /api/v1/imports/history?limit=50` returns the latest import batches (maximum 100).
- `GET /api/v1/imports/fixtures/export.sqlite` exports completed fixture results to a portable SQLite database.
- `POST /api/v1/imports/fixtures/sqlite` imports a SQLite export (multipart field: `file`).

SQLite import is intentionally restricted to the Betting Intelligence export schema version 1. It opens the uploaded database read-only, checks integrity and exact table/column structure, and limits imports to 50,000 rows. Arbitrary SQLite databases are rejected. CSV, XLSX, and SQLite imports are recorded in the import history, including validation failures.
