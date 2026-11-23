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
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the OpenAPI documentation.

## Health check

`GET /api/v1/health`

The current endpoint verifies that the API process is running. Database readiness will be added with the persistence layer.

## Tests

From the repository root:

```bash
cd backend
pytest
```
