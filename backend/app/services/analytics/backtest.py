from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Fixture, Season\nfrom app.services.analytics.financial_backtest import calculate_financial_backtest
from app.services.analytics.lambda_model import InsufficientHistoryError, estimate_match_lambdas
from app.services.analytics.match_analysis import analyze_pre_match


def run_chronological_backtest(
    db: Session,
    league_id: int,
    *,
    min_league_matches: int = 10,
    min_team_matches: int = 3,
    prior_matches: float = 5.0,
    rho: float = 0.0,
    max_goals: int = 10,
) -> dict:
    """Replay finished fixtures in kickoff order using only strictly earlier results."""
    fixtures = list(db.scalars(
        select(Fixture)
        .join(Season, Fixture.season_id == Season.id)
        .where(Season.league_id == league_id, Fixture.status == "finished")
        .order_by(Fixture.kickoff_at, Fixture.id)
    ))
    predictions = []
    skipped = 0
    for fixture in fixtures:
        if fixture.home_goals is None or fixture.away_goals is None:
            skipped += 1
            continue
        try:
            estimate = estimate_match_lambdas(
                db,
                league_id,
                fixture.home_team_id,
                fixture.away_team_id,
                before=fixture.kickoff_at,
                prior_matches=prior_matches,
                min_league_matches=min_league_matches,
                min_team_matches=min_team_matches,
            )
        except InsufficientHistoryError:
            skipped += 1
            continue
        analysis = analyze_pre_match(estimate, rho=rho, max_goals=max_goals)
        probabilities = analysis["markets"]["1x2"]
        actual = (
            "home" if fixture.home_goals > fixture.away_goals
            else "away" if fixture.home_goals < fixture.away_goals
            else "draw"
        )
        predicted = max(probabilities, key=probabilities.get)
        eps = 1e-15
        log_loss = -math.log(max(eps, probabilities[actual]))
        brier = sum(
            (probabilities[outcome] - (1.0 if outcome == actual else 0.0)) ** 2
            for outcome in ("home", "draw", "away")
        )
        top_score = analysis["markets"]["top_correct_scores"][0]["score"]
        actual_score = f"{fixture.home_goals}-{fixture.away_goals}"
        predictions.append({
            "fixture_id": fixture.id,
            "kickoff_at": fixture.kickoff_at.isoformat(),
            "actual": actual,
            "predicted": predicted,
            "correct": predicted == actual,
            "actual_score": actual_score,
            "top_score_prediction": top_score,
            "top_score_correct": top_score == actual_score,
            "brier_score": brier,
            "log_loss": log_loss,
            "probabilities": probabilities,
            "training_matches": estimate["matches_used"],
        })

    count = len(predictions)
    if count:
        accuracy = sum(item["correct"] for item in predictions) / count
        mean_brier = sum(item["brier_score"] for item in predictions) / count
        mean_log_loss = sum(item["log_loss"] for item in predictions) / count
        top_score_hit_rate = sum(item["top_score_correct"] for item in predictions) / count
        start_date = predictions[0]["kickoff_at"]
        end_date = predictions[-1]["kickoff_at"]
    else:
        accuracy = mean_brier = mean_log_loss = top_score_hit_rate = None
        start_date = end_date = None

    return {
        "model": "poisson_dixon_coles_v1",
        "method": "strict_chronological_walk_forward",
        "league_id": league_id,
        "fixtures_considered": len(fixtures),
        "predictions_evaluated": count,
        "fixtures_skipped_insufficient_history": skipped,
        "period": {"from": start_date, "to": end_date},
        "metrics": {
            "accuracy_1x2": accuracy,
            "brier_score_1x2": mean_brier,
            "log_loss_1x2": mean_log_loss,
            "top_correct_score_hit_rate": top_score_hit_rate,
        },
        "financial_metrics": {
            "roi": None,
            "yield": None,
            "max_drawdown": None,
            "clv": None,
            "unavailable_reason": "Historical bookmaker odds and closing prices are not stored for these fixtures. Financial metrics are intentionally not fabricated.",
        },
        "predictions": predictions,
        "warning": "Historical evaluation is not a guarantee of future performance. Results are provisional and depend on data quality.",
    }
