import pytest
from app.services.analytics.match_analysis import analyze_pre_match

def sample_lambda():
    return {
        "league_id": 1, "home_team_id": 10, "away_team_id": 20,
        "matches_used": 120, "home_team_matches": 18, "away_team_matches": 18,
        "home_lambda": 1.65, "away_lambda": 1.12,
        "training_cutoff": "2025-08-01T00:00:00+00:00",
        "method": "league_baseline_venue_split_shrinkage_v1",
    }

def test_integrated_analysis_returns_score_grid_and_markets():
    result = analyze_pre_match(sample_lambda(), rho=-0.08, max_goals=10)
    assert result["model"] == "poisson_dixon_coles_v1"
    assert result["status"] == "provisional_not_backtested"
    assert len(result["score_matrix"]) == 11
    assert len(result["score_matrix"][0]) == 11
    assert sum(map(sum, result["score_matrix"])) == pytest.approx(1.0)
    assert sum(result["markets"]["1x2"].values()) == pytest.approx(1.0)
    assert result["markets"]["btts"]["yes"] + result["markets"]["btts"]["no"] == pytest.approx(1.0)

def test_integrated_analysis_defaults_to_neutral_rho():
    result = analyze_pre_match(sample_lambda())
    assert result["parameters"]["rho"] == 0.0
    assert "not implemented" in result["parameters"]["rho_note"]
