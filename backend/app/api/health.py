from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["system"])


@router.get("/health", summary="Service health check")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "betting-intelligence-api", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready", summary="Database readiness check")
def readiness_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
