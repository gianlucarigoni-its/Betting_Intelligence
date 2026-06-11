"""Tests for Poisson-derived football market probabilities."""

from __future__ import annotations

import pytest
from scipy.stats import poisson

from models.poisson_markets import calculate_poisson_market_probabilities


def test_poisson_market_probabilities_are_bounded() -> None:
    probabilities = calculate_poisson_market_probabilities(1.5, 1.1)

    assert probabilities.home + probabilities.draw + probabilities.away == pytest.approx(1.0)
    for value in (
        probabilities.over_25,
        probabilities.under_25,
        probabilities.btts_yes,
        probabilities.btts_no,
    ):
        assert 0.0 <= value <= 1.0
    assert probabilities.over_25 + probabilities.under_25 == pytest.approx(1.0)
    assert probabilities.btts_yes + probabilities.btts_no == pytest.approx(1.0)


def test_poisson_market_probabilities_reject_invalid_lambdas() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        calculate_poisson_market_probabilities(0.0, 1.0)


def test_natural_market_probabilities_do_not_depend_on_score_grid_truncation() -> None:
    small_grid = calculate_poisson_market_probabilities(4.0, 3.0, max_goals=3)
    large_grid = calculate_poisson_market_probabilities(4.0, 3.0, max_goals=15)

    assert small_grid.over_25 == pytest.approx(large_grid.over_25)
    assert small_grid.under_25 == pytest.approx(large_grid.under_25)
    assert small_grid.btts_yes == pytest.approx(large_grid.btts_yes)
    assert small_grid.btts_no == pytest.approx(large_grid.btts_no)


def test_over_25_matches_total_goals_poisson_distribution() -> None:
    probabilities = calculate_poisson_market_probabilities(1.7, 1.2, max_goals=3)
    expected_under = sum(
        float(poisson.pmf(goals, 2.9))
        for goals in range(3)
    )

    assert probabilities.under_25 == pytest.approx(expected_under)
    assert probabilities.over_25 == pytest.approx(1.0 - expected_under)
