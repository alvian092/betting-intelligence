from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.models import League, Team
from app.db.session import get_db
from app.services.analytics.lambda_model import InsufficientHistoryError, estimate_match_lambdas

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/lambda")
def get_match_lambdas(league_id: int = Query(ge=1), home_team_id: int = Query(ge=1),
                      away_team_id: int = Query(ge=1), before: datetime | None = None,
                      db: Session = Depends(get_db)):
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="Liga tidak ditemukan")
    for team_id in (home_team_id, away_team_id):
        if db.get(Team, team_id) is None:
            raise HTTPException(status_code=404, detail=f"Tim {team_id} tidak ditemukan")
    try:
        return estimate_match_lambdas(db, league_id, home_team_id, away_team_id, before=before)
    except (InsufficientHistoryError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
