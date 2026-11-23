from app.services.analytics.dixon_coles import dixon_coles_score_matrix
from app.services.analytics.markets import market_probabilities

def analyze_pre_match(lambda_estimate: dict, rho: float = 0.0, max_goals: int = 10) -> dict:
    """Combine a historical lambda estimate with the score model and market aggregation."""
    home_lambda = float(lambda_estimate["home_lambda"])
    away_lambda = float(lambda_estimate["away_lambda"])
    matrix = dixon_coles_score_matrix(home_lambda, away_lambda, rho=rho, max_goals=max_goals)
    return {
        "model": "poisson_dixon_coles_v1",
        "status": "provisional_not_backtested",
        "parameters": {
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
            "rho": rho,
            "max_goals": max_goals,
            "rho_note": "rho is caller-supplied; league-specific rho fitting is not implemented",
        },
        "data": {
            "league_id": lambda_estimate["league_id"],
            "home_team_id": lambda_estimate["home_team_id"],
            "away_team_id": lambda_estimate["away_team_id"],
            "matches_used": lambda_estimate["matches_used"],
            "home_team_matches": lambda_estimate["home_team_matches"],
            "away_team_matches": lambda_estimate["away_team_matches"],
            "training_cutoff": lambda_estimate["training_cutoff"],
            "lambda_method": lambda_estimate["method"],
        },
        "score_matrix": matrix,
        "markets": market_probabilities(matrix),
    }
