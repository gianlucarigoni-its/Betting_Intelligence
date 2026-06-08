"""Tests for value metrics calculations."""

from __future__ import annotations

import pytest

from models.value_metrics import ValueMetricsCalculator, ValueMetricsInput


class TestValueMetricsCalculator:
    def test_calculate_returns_expected_metrics(self) -> None:
        calculator = ValueMetricsCalculator()
        result = calculator.calculate(
            ValueMetricsInput(model_probability=0.60, bookmaker_odds=2.00)
        )

        assert result.bookmaker_probability == pytest.approx(0.50)
        assert result.edge_pct == pytest.approx(10.0)
        assert result.ev == pytest.approx(0.20)
        assert result.kelly_fraction == pytest.approx(0.20)
        assert result.quarter_kelly_fraction == pytest.approx(0.05)

    def test_negative_edge_is_clamped_for_kelly(self) -> None:
        calculator = ValueMetricsCalculator()
        result = calculator.calculate(
            ValueMetricsInput(model_probability=0.40, bookmaker_odds=2.00)
        )

        assert result.edge_pct == pytest.approx(-10.0)
        assert result.ev == pytest.approx(-0.20)
        assert result.kelly_fraction == 0.0
        assert result.quarter_kelly_fraction == 0.0

    def test_invalid_probability_raises_value_error(self) -> None:
        calculator = ValueMetricsCalculator()

        with pytest.raises(ValueError, match="model_probability"):
            calculator.calculate(
                ValueMetricsInput(model_probability=1.10, bookmaker_odds=2.00)
            )

    def test_invalid_odds_raises_value_error(self) -> None:
        calculator = ValueMetricsCalculator()

        with pytest.raises(ValueError, match="bookmaker_odds"):
            calculator.calculate(
                ValueMetricsInput(model_probability=0.50, bookmaker_odds=1.00)
            )