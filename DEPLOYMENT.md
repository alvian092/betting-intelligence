# Backend deployment

The Android client and web client require a reachable HTTPS backend. The API is packaged as a Docker service; deploy it to a container host and attach a managed PostgreSQL database.

## Required environment variables

- `DATABASE_URL`: SQLAlchemy URL using the psycopg 3 driver, for example `postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`.
- `CORS_ORIGINS`: comma-separated allowed browser origins. Add the exact production web origin; do not use a wildcard when credentials are enabled.
- `APP_ENV`: set to `production`.
- `PORT`: supplied by most container hosts; defaults to 8000.

Never commit production database credentials or provider API keys to Git.

## Container settings

- Dockerfile: `backend/Dockerfile`
- Docker build context: `backend/`
- Health check: `/api/v1/health/ready`
- Start command is defined in the Dockerfile. It applies Alembic migrations before starting Uvicorn.

## Deployment sequence (mobile browser)

1. Create a managed PostgreSQL database with your chosen hosting provider.
2. Create a Docker web service from this GitHub repository.
3. Set the Dockerfile path to `backend/Dockerfile` and build context to `backend`.
4. Add `DATABASE_URL` as a private environment variable using the provider's internal connection string and the `postgresql+psycopg://` driver.
5. Set `APP_ENV=production` and `CORS_ORIGINS` to the web app's exact HTTPS origin.
6. Deploy and wait until `/api/v1/health/ready` returns a successful response.
7. Copy the service's public HTTPS URL into the Android app's Backend URL field, then tap **Simpan & hubungkan**.

## Important

A debug APK is a native client, not a hosted backend. The APK cannot fetch shared league/team data or run the server-side analytics until a backend URL is configured. The backend and database must remain online for cross-device data persistence. Use PostgreSQL for deployment; the local SQLite default is intended for development only.
