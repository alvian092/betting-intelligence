from __future__ import annotations

import math

from app.services.analytics.poisson import score_matrix


def correction_factor(home_goals: int, away_goals: int, home_lambda: float, away_lambda: float, rho: float) -> float:
    """Dixon-Coles low-score adjustment factor."""
    if home_goals == 0 and away_goals == 0:
        return 1.0 - home_lambda * away_lambda * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + home_lambda * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + away_lambda * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def dixon_coles_score_matrix(
    home_lambda: float, away_lambda: float, rho: float = 0.0, max_goals: int = 10
) -> list[list[float]]:
    """Apply Dixon-Coles adjustment to low scores and renormalize the grid."""
    if not all(math.isfinite(value) for value in (home_lambda, away_lambda, rho)):
        raise ValueError("lambdas and rho must be finite")
    if home_lambda <= 0 or away_lambda <= 0:
        raise ValueError("lambdas must be positive")
    matrix = score_matrix(home_lambda, away_lambda, max_goals)
    for home_goals in (0, 1):
        for away_goals in (0, 1):
            factor = correction_factor(home_goals, away_goals, home_lambda, away_lambda, rho)
            if factor < 0:
                raise ValueError("rho produces a negative low-score probability")
            matrix[home_goals][away_goals] *= factor
    total = sum(sum(row) for row in matrix)
    if total <= 0:
        raise ArithmeticError("corrected score probabilities have no mass")
    return [[value / total for value in row] for row in matrix]
