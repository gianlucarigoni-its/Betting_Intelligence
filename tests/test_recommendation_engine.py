"""Tests for recommendation engine profile classification."""

from __future__ import annotations

from recommendation.profile_engine import (
    ConfidenceLevel,
    RecommendationBand,
    RecommendationEngine,
    RecommendationInput,
    RecommendationProfile,
)
from models.value_metrics import ValueMetricsResult


def make_metrics(edge_pct: float) -> ValueMetricsResult:
    return ValueMetricsResult(
        model_probability=0.60,
        bookmaker_probability=0.50,
        bookmaker_odds=2.00,
        edge_pct=edge_pct,
        ev=0.0,
        kelly_fraction=0.0,
        quarter_kelly_fraction=0.0,
    )


class TestRecommendationEngine:
    def test_high_risk_profile(self) -> None:
        engine = RecommendationEngine()
        result = engine.classify(
            RecommendationInput(
                value_metrics=make_metrics(12.0),
                confidence_level=ConfidenceLevel.MEDIUM,
            )
        )

        assert result.profile == RecommendationProfile.HIGH_RISK
        assert result.band == RecommendationBand.AGGRESSIVE
        assert result.recommendation_score > 0

    def test_low_confidence_blocks_high_edge(self) -> None:
        engine = RecommendationEngine()
        result = engine.classify(
            RecommendationInput(
                value_metrics=make_metrics(15.0),
                confidence_level=ConfidenceLevel.LOW,
                market_dislocation_pct=6.0,
            )
        )

        assert result.profile == RecommendationProfile.NO_BET
        assert result.band == RecommendationBand.NO_BET
        assert result.stake_fraction == 0.0

    def test_market_error_profile(self) -> None:
        engine = RecommendationEngine()
        result = engine.classify(
            RecommendationInput(
                value_metrics=make_metrics(12.5),
                confidence_level=ConfidenceLevel.HIGH,
                market_dislocation_pct=4.5,
            )
        )

        assert result.profile == RecommendationProfile.HIGH_RISK
        assert result.band == RecommendationBand.MARKET_ERROR
        assert result.stake_fraction > 0

    def test_value_profile(self) -> None:
        engine = RecommendationEngine()
        result = engine.classify(
            RecommendationInput(
                value_metrics=make_metrics(6.0),
                confidence_level=ConfidenceLevel.MEDIUM,
            )
        )

        assert result.profile == RecommendationProfile.VALUE
        assert result.band == RecommendationBand.BALANCED

    def test_safe_profile(self) -> None:
        engine = RecommendationEngine()
        result = engine.classify(
            RecommendationInput(
                value_metrics=make_metrics(3.5),
                confidence_level=ConfidenceLevel.HIGH,
            )
        )

        assert result.profile == RecommendationProfile.SAFE
        assert result.band == RecommendationBand.CONSERVATIVE

    def test_no_bet_profile_for_low_edge(self) -> None:
        engine = RecommendationEngine()
        result = engine.classify(
            RecommendationInput(
                value_metrics=make_metrics(1.0),
                confidence_level=ConfidenceLevel.MEDIUM,
            )
        )

        assert result.profile == RecommendationProfile.NO_BET
        assert result.band == RecommendationBand.NO_BET
