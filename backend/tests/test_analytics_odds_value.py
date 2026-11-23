import pytest

from app.services.analytics.odds_value import evaluate_odds_value


def test_removes_proportional_margin_and_finds_value():
    result = evaluate_odds_value([
        {"name": "Home", "model_probability": 0.50, "decimal_odds": 2.10},
        {"name": "Draw", "model_probability": 0.25, "decimal_odds": 3.50},
        {"name": "Away", "model_probability": 0.25, "decimal_odds": 4.00},
    ])
    assert result["bookmaker_overround"] == pytest.approx(0.0595238095)
    assert sum(item["no_vig_probability"] for item in result["selections"]) == pytest.approx(1.0)
    assert result["selections"][0]["decision"] == "VALUE"
    assert result["selections"][0]["recommended_stake_fraction"] > 0


def test_no_bet_when_ev_below_threshold():
    result = evaluate_odds_value([
        {"name": "Yes", "model_probability": 0.50, "decimal_odds": 1.90},
        {"name": "No", "model_probability": 0.50, "decimal_odds": 1.90},
    ])
    assert all(item["decision"] == "NO_BET" for item in result["selections"])
    assert all(item["recommended_stake_fraction"] == 0 for item in result["selections"])


def test_rejects_invalid_probability_and_odds():
    with pytest.raises(ValueError):
        evaluate_odds_value([{"name":"A","model_probability":0,"decimal_odds":2},
                             {"name":"B","model_probability":0.5,"decimal_odds":2}])
    with pytest.raises(ValueError):
        evaluate_odds_value([{"name":"A","model_probability":0.5,"decimal_odds":1},
                             {"name":"B","model_probability":0.5,"decimal_odds":2}])


def test_kelly_fraction_is_capped_and_no_negative_stake():
    result = evaluate_odds_value([
        {"name":"A","model_probability":0.4,"decimal_odds":2.2},
        {"name":"B","model_probability":0.6,"decimal_odds":1.7},
    ], fractional_kelly=0.25, min_ev=0)
    for item in result["selections"]:
        assert 0 <= item["recommended_stake_fraction"] <= item["full_kelly_fraction"]
