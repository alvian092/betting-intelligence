from datetime import timedelta

from app.db.models import Fixture
from app.services.analytics.backtest import run_chronological_backtest
from test_analytics_lambda import seed_history


def test_walk_forward_backtest_excludes_fixtures_without_prior_history(db):
    league_id, teams, base = seed_history(db)
    db.add(Fixture(
        season_id=1,
        home_team_id=teams[0],
        away_team_id=teams[1],
        kickoff_at=base + timedelta(days=13),
        status="finished",
        home_goals=2,
        away_goals=1,
    ))
    db.commit()

    result = run_chronological_backtest(db, league_id)

    assert result["method"] == "strict_chronological_walk_forward"
    assert result["fixtures_considered"] == 13
    assert result["predictions_evaluated"] >= 1
    assert result["fixtures_skipped_insufficient_history"] >= 1
    assert 0 <= result["metrics"]["accuracy_1x2"] <= 1
    assert result["metrics"]["brier_score_1x2"] >= 0
    assert result["metrics"]["log_loss_1x2"] >= 0
    assert result["financial_metrics"]["roi"] is None
    assert "not stored" in result["financial_metrics"]["unavailable_reason"]


def test_backtest_returns_null_metrics_when_no_fixture_has_enough_history(db):
    league_id, _, _ = seed_history(db)
    result = run_chronological_backtest(db, league_id, min_league_matches=100)
    assert result["predictions_evaluated"] == 0
    assert result["metrics"]["accuracy_1x2"] is None
    assert result["financial_metrics"]["clv"] is None
