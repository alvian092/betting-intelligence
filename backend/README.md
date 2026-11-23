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
