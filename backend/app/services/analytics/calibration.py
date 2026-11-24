from __future__ import annotations

from collections import defaultdict
from math import isfinite

OUTCOMES = ("home", "draw", "away")


def evaluate_calibration(predictions: list[dict], *, bins: int = 10) -> dict:
    """Build one-vs-rest reliability bins and top-outcome confidence diagnostics.

    Every evaluated fixture contributes three one-vs-rest observations. Empty
    bins are omitted so consumers do not mistake missing data for zero accuracy.
    """
    if bins < 2 or bins > 20:
        raise ValueError("bins must be between 2 and 20")

    observations: dict[str, list[tuple[float, int]]] = {key: [] for key in OUTCOMES}
    top_groups = defaultdict(lambda: {"count": 0, "confidence": 0.0, "correct": 0})
    class_brier = {key: [] for key in OUTCOMES}

    for item in predictions:
        probabilities = item["probabilities"]
        actual = item["actual"]
        if actual not in OUTCOMES:
            raise ValueError("actual outcome must be home, draw, or away")
        if any(key not in probabilities for key in OUTCOMES):
            raise ValueError("all 1X2 probabilities are required")
        values = [float(probabilities[key]) for key in OUTCOMES]
        if any(not isfinite(value) or value < 0 or value > 1 for value in values):
            raise ValueError("probabilities must be finite values between 0 and 1")
        if abs(sum(values) - 1.0) > 1e-6:
            raise ValueError("1X2 probabilities must sum to 1")

        for outcome in OUTCOMES:
            probability = float(probabilities[outcome])
            observed = int(actual == outcome)
            observations[outcome].append((probability, observed))
            class_brier[outcome].append((probability - observed) ** 2)

        top = max(OUTCOMES, key=lambda key: probabilities[key])
        confidence = float(probabilities[top])
        bucket = min(bins - 1, int(confidence * bins))
        group = top_groups[bucket]
        group["count"] += 1
        group["confidence"] += confidence
        group["correct"] += int(top == actual)

    reliability = []
    weighted_gap = 0.0
    max_gap = 0.0
    total_binary = len(predictions) * len(OUTCOMES)
    for outcome in OUTCOMES:
        bucketed = defaultdict(list)
        for probability, observed in observations[outcome]:
            bucket = min(bins - 1, int(probability * bins))
            bucketed[bucket].append((probability, observed))
        for bucket, values in sorted(bucketed.items()):
            count = len(values)
            mean_probability = sum(value[0] for value in values) / count
            observed_frequency = sum(value[1] for value in values) / count
            gap = abs(mean_probability - observed_frequency)
            weighted_gap += count / total_binary * gap if total_binary else 0.0
            max_gap = max(max_gap, gap)
            reliability.append({
                "outcome": outcome,
                "bin": f"{bucket / bins:.1f}–{(bucket + 1) / bins:.1f}",
                "count": count,
                "mean_probability": mean_probability,
                "observed_frequency": observed_frequency,
                "absolute_gap": gap,
            })

    top_confidence = []
    for bucket, values in sorted(top_groups.items()):
        top_confidence.append({
            "bin": f"{bucket / bins:.1f}–{(bucket + 1) / bins:.1f}",
            "count": values["count"],
            "mean_confidence": values["confidence"] / values["count"],
            "accuracy": values["correct"] / values["count"],
        })

    return {
        "method": "multiclass_one_vs_rest_equal_width_bins",
        "predictions_evaluated": len(predictions),
        "bins": bins,
        "expected_calibration_error": weighted_gap if predictions else None,
        "maximum_calibration_error": max_gap if predictions else None,
        "classwise_brier_score": {
            outcome: sum(values) / len(values) if values else None
            for outcome, values in class_brier.items()
        },
        "reliability": reliability,
        "top_outcome_confidence": top_confidence,
        "warning": "Calibration estimates are descriptive and unstable with small samples. Use chronological out-of-sample predictions only.",
    }
