from __future__ import annotations

import math


def poisson_pmf(rate: float, goals: int) -> float:
    """Return P(X=goals) for a Poisson-distributed goal count."""
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("rate must be a finite non-negative number")
    if goals < 0:
        raise ValueError("goals must be non-negative")
    if rate == 0:
        return 1.0 if goals == 0 else 0.0
    return math.exp(-rate + goals * math.log(rate) - math.lgamma(goals + 1))


def poisson_probabilities(rate: float, max_goals: int = 10) -> list[float]:
    """Return probabilities for 0..max_goals, normalized to the truncated range."""
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("rate must be a finite positive number")
    if max_goals < 1 or max_goals > 30:
        raise ValueError("max_goals must be between 1 and 30")
    values = [poisson_pmf(rate, goals) for goals in range(max_goals + 1)]
    total = sum(values)
    if total <= 0:
        raise ArithmeticError("Poisson probability mass underflowed")
    return [value / total for value in values]


def score_matrix(home_lambda: float, away_lambda: float, max_goals: int = 10) -> list[list[float]]:
    """Build an independent-Poisson score matrix; rows are home goals."""
    home = poisson_probabilities(home_lambda, max_goals)
    away = poisson_probabilities(away_lambda, max_goals)
    return [[h * a for a in away] for h in home]
