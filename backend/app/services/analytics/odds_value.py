from __future__ import annotations

from collections.abc import Sequence


def evaluate_odds_value(
    selections: Sequence[dict],
    fractional_kelly: float = 0.25,
    min_ev: float = 0.02,
) -> dict:
    """Evaluate decimal odds against model probabilities and remove proportional book margin."""
    if not selections:
        raise ValueError("At least one market selection is required")
    if not 0 < fractional_kelly <= 1:
        raise ValueError("fractional_kelly must be greater than 0 and at most 1")
    if not 0 <= min_ev < 1:
        raise ValueError("min_ev must be between 0 and 1")

    names = set()
    implied = []
    for item in selections:
        name = str(item["name"]).strip()
        probability = float(item["model_probability"])
        odds = float(item["decimal_odds"])
        if not name or name in names:
            raise ValueError("Selection names must be non-empty and unique")
        names.add(name)
        if not 0 < probability < 1:
            raise ValueError("Model probabilities must be between 0 and 1")
        if odds <= 1:
            raise ValueError("Decimal odds must be greater than 1.0")
        implied.append(1.0 / odds)

    implied_total = sum(implied)
    margin = implied_total - 1.0
    results = []
    for item, raw_implied in zip(selections, implied):
        probability = float(item["model_probability"])
        odds = float(item["decimal_odds"])
        fair_market_probability = raw_implied / implied_total
        fair_odds = 1.0 / probability
        ev = probability * odds - 1.0
        edge = probability - fair_market_probability
        full_kelly = max(0.0, (probability * odds - 1.0) / (odds - 1.0))
        qualifies = ev >= min_ev and edge > 0
        stake_fraction = full_kelly * fractional_kelly if qualifies else 0.0
        results.append({
            "name": str(item["name"]).strip(),
            "model_probability": probability,
            "bookmaker_implied_probability": raw_implied,
            "no_vig_probability": fair_market_probability,
            "decimal_odds": odds,
            "model_fair_odds": fair_odds,
            "ev": ev,
            "edge": edge,
            "full_kelly_fraction": full_kelly,
            "recommended_stake_fraction": stake_fraction,
            "decision": "VALUE" if qualifies else "NO_BET",
        })
    return {
        "method": "proportional_margin_removal",
        "bookmaker_overround": margin,
        "bookmaker_margin_percent": margin * 100.0,
        "fractional_kelly": fractional_kelly,
        "minimum_ev": min_ev,
        "selections": results,
        "warning": "Model probabilities are estimates, not guarantees. Stake sizing is informational; never treat it as guaranteed profit.",
    }
