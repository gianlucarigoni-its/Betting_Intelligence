"""Tests for Poisson-derived football market probabilities."""

from __future__ import annotations

import pytest

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
