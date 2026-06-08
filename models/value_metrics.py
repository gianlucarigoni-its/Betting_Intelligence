"""Value metrics for betting decisions.

This module converts model probabilities and bookmaker odds into betting
metrics: edge, expected value and Kelly fraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BetSide(str, Enum):
    """Supported bet sides for 1X2 markets."""

    HOME = "home"
    DRAW = "draw"
    AWAY = "away"


@dataclass(frozen=True, slots=True)
class ValueMetricsInput:
    """Input required to compute value metrics."""

    model_probability: float
    bookmaker_odds: float


@dataclass(frozen=True, slots=True)
class ValueMetricsResult:
    """Output metrics for a single market selection."""

    model_probability: float
    bookmaker_probability: float
    bookmaker_odds: float
    edge_pct: float
    ev: float
    kelly_fraction: float
    quarter_kelly_fraction: float


class ValueMetricsCalculator:
    """Calculate edge, EV and Kelly from probability and odds."""

    def __init__(self, quarter_kelly_cap: float = 0.05) -> None:
        if quarter_kelly_cap <= 0:
            raise ValueError("quarter_kelly_cap must be positive")
        self._quarter_kelly_cap = quarter_kelly_cap

    def calculate(self, metrics_input: ValueMetricsInput) -> ValueMetricsResult:
        """Return betting value metrics for a selection."""

        self._validate_probability(metrics_input.model_probability)
        self._validate_odds(metrics_input.bookmaker_odds)

        bookmaker_probability = 1.0 / metrics_input.bookmaker_odds
        edge_pct = (metrics_input.model_probability - bookmaker_probability) * 100.0
        ev = (metrics_input.model_probability * metrics_input.bookmaker_odds) - 1.0
        kelly_fraction = self._kelly_fraction(
            metrics_input.model_probability,
            metrics_input.bookmaker_odds,
        )
        quarter_kelly_fraction = min(kelly_fraction / 4.0, self._quarter_kelly_cap)
        quarter_kelly_fraction = max(quarter_kelly_fraction, 0.0)

        return ValueMetricsResult(
            model_probability=metrics_input.model_probability,
            bookmaker_probability=bookmaker_probability,
            bookmaker_odds=metrics_input.bookmaker_odds,
            edge_pct=edge_pct,
            ev=ev,
            kelly_fraction=kelly_fraction,
            quarter_kelly_fraction=quarter_kelly_fraction,
        )

    @staticmethod
    def _validate_probability(probability: float) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("model_probability must be between 0 and 1")

    @staticmethod
    def _validate_odds(odds: float) -> None:
        if odds <= 1.0:
            raise ValueError("bookmaker_odds must be greater than 1")

    @staticmethod
    def _kelly_fraction(probability: float, odds: float) -> float:
        raw_kelly = (probability * odds - 1.0) / (odds - 1.0)
        return max(raw_kelly, 0.0)