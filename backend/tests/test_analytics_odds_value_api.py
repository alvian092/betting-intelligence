from fastapi.testclient import TestClient

from app.main import app


def test_odds_value_endpoint_returns_margin_ev_and_kelly():
    with TestClient(app) as client:
        response = client.post("/api/v1/analytics/value", json={
            "selections": [
                {"name": "Home", "model_probability": 0.5, "decimal_odds": 2.1},
                {"name": "Draw", "model_probability": 0.25, "decimal_odds": 3.5},
                {"name": "Away", "model_probability": 0.25, "decimal_odds": 4.0},
            ],
            "fractional_kelly": 0.25,
            "min_ev": 0.02,
        })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["bookmaker_margin_percent"] > 0
    assert len(payload["selections"]) == 3
    assert payload["selections"][0]["decision"] == "VALUE"
    assert payload["selections"][0]["recommended_stake_fraction"] > 0


def test_odds_value_endpoint_rejects_invalid_decimal_odds():
    with TestClient(app) as client:
        response = client.post("/api/v1/analytics/value", json={
            "selections": [
                {"name": "Home", "model_probability": 0.5, "decimal_odds": 1},
                {"name": "Draw", "model_probability": 0.25, "decimal_odds": 3.5},
            ]
        })
    assert response.status_code == 422
