from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Fixture, Season

class InsufficientHistoryError(ValueError):
    """Insufficient league/team sample for a stable estimate."""

def estimate_match_lambdas(db: Session, league_id: int, home_team_id: int, away_team_id: int,
                           before: datetime | None = None, prior_matches: float = 5.0,
                           min_league_matches: int = 10, min_team_matches: int = 3) -> dict:
    """Estimate expected goals from league baselines and venue-specific team strengths.

    Finished fixtures at or after the optional cutoff are excluded. Venue rates are
    shrunk toward league averages to reduce small-sample extremes.
    """
    if home_team_id == away_team_id:
        raise ValueError("home and away teams must be different")
    if prior_matches <= 0:
        raise ValueError("prior_matches must be positive")
    stmt = select(Fixture).join(Season, Fixture.season_id == Season.id).where(
        Season.league_id == league_id, Fixture.status == "finished")
    if before is not None:
        stmt = stmt.where(Fixture.kickoff_at < before)
    fixtures = list(db.scalars(stmt.order_by(Fixture.kickoff_at)))
    if len(fixtures) < min_league_matches:
        raise InsufficientHistoryError(
            f"League history requires at least {min_league_matches} finished matches; found {len(fixtures)}")
    league_home_avg = sum(int(f.home_goals or 0) for f in fixtures) / len(fixtures)
    league_away_avg = sum(int(f.away_goals or 0) for f in fixtures) / len(fixtures)
    if league_home_avg <= 0 or league_away_avg <= 0:
        raise InsufficientHistoryError("League goal baseline must be positive")
    stats = {}
    def blank():
        return {"played": 0, "home_played": 0, "away_played": 0,
                "home_scored": 0, "home_conceded": 0, "away_scored": 0, "away_conceded": 0}
    for f in fixtures:
        h = stats.setdefault(f.home_team_id, blank())
        a = stats.setdefault(f.away_team_id, blank())
        hg, ag = int(f.home_goals or 0), int(f.away_goals or 0)
        h["played"] += 1; h["home_played"] += 1
        h["home_scored"] += hg; h["home_conceded"] += ag
        a["played"] += 1; a["away_played"] += 1
        a["away_scored"] += ag; a["away_conceded"] += hg
    for team_id, label in ((home_team_id, "Home"), (away_team_id, "Away")):
        played = int(stats.get(team_id, {}).get("played", 0))
        if played < min_team_matches:
            raise InsufficientHistoryError(
                f"{label} team requires at least {min_team_matches} prior league matches; found {played}")
    def shrunk(goals, matches, baseline):
        return (goals + prior_matches * baseline) / (matches + prior_matches)
    h, a = stats[home_team_id], stats[away_team_id]
    home_attack = shrunk(h["home_scored"], h["home_played"], league_home_avg) / league_home_avg
    home_defence = shrunk(h["home_conceded"], h["home_played"], league_away_avg) / league_away_avg
    away_attack = shrunk(a["away_scored"], a["away_played"], league_away_avg) / league_away_avg
    away_defence = shrunk(a["away_conceded"], a["away_played"], league_home_avg) / league_home_avg
    return {
        "league_id": league_id, "home_team_id": home_team_id, "away_team_id": away_team_id,
        "matches_used": len(fixtures), "home_team_matches": int(h["played"]), "away_team_matches": int(a["played"]),
        "league_home_goals_avg": league_home_avg, "league_away_goals_avg": league_away_avg,
        "home_attack_strength": home_attack, "home_defence_strength": home_defence,
        "away_attack_strength": away_attack, "away_defence_strength": away_defence,
        "home_lambda": league_home_avg * home_attack * away_defence,
        "away_lambda": league_away_avg * away_attack * home_defence,
        "method": "league_baseline_venue_split_shrinkage_v1",
        "training_cutoff": before.isoformat() if before else None,
        "status": "provisional_not_backtested",
    }
