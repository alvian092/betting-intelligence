from __future__ import annotations

from collections.abc import Sequence


def market_probabilities(matrix: Sequence[Sequence[float]]) -> dict:
    """Aggregate a score grid into common pre-match markets."""
    if not matrix or not matrix[0] or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("score matrix must be a non-empty rectangle")
    total = sum(sum(row) for row in matrix)
    if total <= 0:
        raise ValueError("score matrix must have positive probability mass")
    home = draw = away = over_25 = under_25 = btts = 0.0
    home_goals = [0.0] * len(matrix)
    away_goals = [0.0] * len(matrix[0])
    correct_scores = []
    for h, row in enumerate(matrix):
        for a, probability in enumerate(row):
            if probability < 0:
                raise ValueError("probabilities cannot be negative")
            p = probability / total
            home_goals[h] += p
            away_goals[a] += p
            if h > a:
                home += p
            elif h == a:
                draw += p
            else:
                away += p
            if h + a >= 3:
                over_25 += p
            else:
                under_25 += p
            if h > 0 and a > 0:
                btts += p
            correct_scores.append({"score": f"{h}-{a}", "probability": p})
    correct_scores.sort(key=lambda item: item["probability"], reverse=True)
    return {
        "1x2": {"home": home, "draw": draw, "away": away},
        "double_chance": {"1x": home + draw, "x2": draw + away, "12": home + away},
        "totals_2_5": {"over": over_25, "under": under_25},
        "btts": {"yes": btts, "no": 1.0 - btts},
        "home_team_goals": home_goals,
        "away_team_goals": away_goals,
        "top_correct_scores": correct_scores[:10],
    }
