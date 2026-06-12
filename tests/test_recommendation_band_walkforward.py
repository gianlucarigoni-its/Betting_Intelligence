"""Tests for walk-forward recommendation band helpers."""

from backtesting.run_recommendation_band_walkforward import confidence_from_probability
from recommendation.profile_engine import ConfidenceLevel


def test_confidence_from_probability_uses_strict_bands() -> None:
    assert confidence_from_probability(0.53) == ConfidenceLevel.LOW
    assert confidence_from_probability(0.54) == ConfidenceLevel.MEDIUM
    assert confidence_from_probability(0.61) == ConfidenceLevel.MEDIUM
    assert confidence_from_probability(0.62) == ConfidenceLevel.HIGH
