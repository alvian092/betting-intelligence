from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.models import League, Team
from app.db.session import get_db
from app.services.analytics.lambda_model import InsufficientHistoryError, estimate_match_lambdas
from app.services.analytics.match_analysis import analyze_pre_match

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


@router.get("/pre-match")
def get_pre_match_analysis(
    league_id: int = Query(ge=1),
    home_team_id: int = Query(ge=1),
    away_team_id: int = Query(ge=1),
    before: datetime | None = None,
    rho: float = Query(0.0, ge=-1.0, le=1.0),
    max_goals: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Generate a pre-match score grid and market probabilities from historical data."""
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="Liga tidak ditemukan")
    for team_id in (home_team_id, away_team_id):
        if db.get(Team, team_id) is None:
            raise HTTPException(status_code=404, detail=f"Tim {team_id} tidak ditemukan")
    try:
        estimate = estimate_match_lambdas(
            db, league_id, home_team_id, away_team_id, before=before
        )
        return analyze_pre_match(estimate, rho=rho, max_goals=max_goals)
    except (InsufficientHistoryError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from app.schemas.odds_value import OddsValueIn
from app.services.analytics.odds_value import evaluate_odds_value


@router.post("/value")
def post_odds_value(payload: OddsValueIn):
    """Compare bookmaker decimal odds with model probabilities."""
    try:
        return evaluate_odds_value(
            [item.model_dump() for item in payload.selections],
            fractional_kelly=payload.fractional_kelly,
            min_ev=payload.min_ev,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


from app.services.analytics.backtest import run_chronological_backtest


@router.get("/backtest")
def get_chronological_backtest(
    league_id: int = Query(ge=1),
    min_league_matches: int = Query(10, ge=1, le=10000),
    min_team_matches: int = Query(3, ge=1, le=1000),
    prior_matches: float = Query(5.0, gt=0, le=1000),
    rho: float = Query(0.0, ge=-1.0, le=1.0),
    max_goals: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Evaluate historical 1X2 predictions using strict walk-forward training."""
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="Liga tidak ditemukan")
    return run_chronological_backtest(
        db,
        league_id,
        min_league_matches=min_league_matches,
        min_team_matches=min_team_matches,
        prior_matches=prior_matches,
        rho=rho,
        max_goals=max_goals,
    )
