import pytest

from app.services.analytics.poisson import poisson_pmf, poisson_probabilities, score_matrix
from app.services.analytics.dixon_coles import correction_factor, dixon_coles_score_matrix
from app.services.analytics.markets import market_probabilities


def test_poisson_pmf_and_distribution():
    assert poisson_pmf(0, 0) == 1.0
    assert poisson_pmf(0, 2) == 0.0
    assert poisson_pmf(2.0, 0) == pytest.approx(0.1353352832)
    probabilities = poisson_probabilities(1.7, 10)
    assert sum(probabilities) == pytest.approx(1.0)
    assert all(0 <= value <= 1 for value in probabilities)


def test_poisson_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        poisson_pmf(-1, 0)
    with pytest.raises(ValueError):
        poisson_pmf(1, -1)
    with pytest.raises(ValueError):
        poisson_probabilities(0)


def test_independent_score_matrix_is_normalized():
    matrix = score_matrix(1.5, 1.1, 10)
    assert sum(map(sum, matrix)) == pytest.approx(1.0)
    assert len(matrix) == 11 and len(matrix[0]) == 11


def test_dixon_coles_factors_only_low_scores():
    assert correction_factor(0, 0, 1.5, 1.1, -0.1) == pytest.approx(1.165)
    assert correction_factor(2, 1, 1.5, 1.1, -0.1) == 1.0


def test_dixon_coles_matrix_is_normalized_and_changes_low_scores():
    base = score_matrix(1.5, 1.1, 10)
    adjusted = dixon_coles_score_matrix(1.5, 1.1, rho=-0.08, max_goals=10)
    assert sum(map(sum, adjusted)) == pytest.approx(1.0)
    assert adjusted[0][0] != pytest.approx(base[0][0])


def test_dixon_coles_rejects_invalid_rho():
    with pytest.raises(ValueError):
        dixon_coles_score_matrix(1.5, 1.1, rho=-2.0)


def test_market_probabilities_are_consistent():
    markets = market_probabilities(score_matrix(1.6, 1.0, 10))
    assert sum(markets["1x2"].values()) == pytest.approx(1.0)
    assert markets["totals_2_5"]["over"] + markets["totals_2_5"]["under"] == pytest.approx(1.0)
    assert markets["btts"]["yes"] + markets["btts"]["no"] == pytest.approx(1.0)
    assert len(markets["top_correct_scores"]) == 10
