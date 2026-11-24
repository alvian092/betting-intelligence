import pytest

from app.services.analytics.calibration import evaluate_calibration


def test_calibration_reports_one_vs_rest_reliability_and_classwise_brier():
    predictions = [
        {"actual": "home", "probabilities": {"home": 0.8, "draw": 0.1, "away": 0.1}},
        {"actual": "away", "probabilities": {"home": 0.2, "draw": 0.1, "away": 0.7}},
        {"actual": "draw", "probabilities": {"home": 0.1, "draw": 0.7, "away": 0.2}},
        {"actual": "home", "probabilities": {"home": 0.7, "draw": 0.2, "away": 0.1}},
    ]

    result = evaluate_calibration(predictions)

    assert result["predictions_evaluated"] == 4
    assert result["method"] == "multiclass_one_vs_rest_equal_width_bins"
    assert result["expected_calibration_error"] >= 0
    assert result["maximum_calibration_error"] >= 0
    assert result["classwise_brier_score"]["home"] == pytest.approx(
        ((0.8 - 1) ** 2 + (0.2 - 0) ** 2 + (0.1 - 0) ** 2 + (0.7 - 1) ** 2) / 4
    )
    assert {row["outcome"] for row in result["reliability"]} == {"home", "draw", "away"}
    assert sum(row["count"] for row in result["top_outcome_confidence"]) == 4


def test_calibration_is_null_for_empty_prediction_set():
    result = evaluate_calibration([])
    assert result["predictions_evaluated"] == 0
    assert result["expected_calibration_error"] is None
    assert result["maximum_calibration_error"] is None
    assert result["reliability"] == []
    assert result["top_outcome_confidence"] == []


@pytest.mark.parametrize("bins", [1, 21])
def test_calibration_rejects_invalid_bin_count(bins):
    with pytest.raises(ValueError, match="bins must be between"):
        evaluate_calibration([], bins=bins)


def test_calibration_rejects_probabilities_that_do_not_sum_to_one():
    with pytest.raises(ValueError, match="must sum to 1"):
        evaluate_calibration([{
            "actual": "home",
            "probabilities": {"home": 0.5, "draw": 0.2, "away": 0.2},
        }])
