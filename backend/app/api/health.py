from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health", summary="Service health check")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "betting-intelligence-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
