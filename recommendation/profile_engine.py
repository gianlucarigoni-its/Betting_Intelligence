"""Recommendation engine for betting profiles.

This layer classifies opportunities into predefined profiles based on edge,
confidence and market-dislocation rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models.value_metrics import ValueMetricsResult


class RecommendationProfile(str, Enum):
    """Available betting profiles."""

    SAFE = "SAFE"
    VALUE = "VALUE"
    RISKY = "RISKY"
    HIGH_RISK = "HIGH_RISK"
    LOW_RISK = "LOW_RISK"
    NO_BET = "NO_BET"


class RecommendationBand(str, Enum):
    """Operational recommendation bands."""

    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"
    MARKET_ERROR = "MARKET_ERROR"
    UNDERVALUED = "UNDERVALUED"
    NO_BET = "NO_BET"


class ConfidenceLevel(str, Enum):
    """Confidence level attached to a recommendation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class RecommendationInput:
    """Input for the recommendation engine."""

    value_metrics: ValueMetricsResult
    confidence_level: ConfidenceLevel
    is_favorite: bool = False
    selection: str | None = None
    market_type: str | None = None
    opening_edge_pct: float | None = None
    closing_edge_pct: float | None = None
    market_dislocation_pct: float | None = None


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    """Classification output produced by the engine."""

    profile: RecommendationProfile
    band: RecommendationBand
    confidence_level: ConfidenceLevel
    recommendation_score: int
    stake_fraction: float
    reasoning: str


class RecommendationEngine:
    """Assign a betting profile from edge, confidence and market rules."""

    def classify(self, recommendation_input: RecommendationInput) -> RecommendationResult:
        """Classify a bet opportunity into one profile."""

        edge = recommendation_input.value_metrics.edge_pct
        confidence = recommendation_input.confidence_level
        is_favorite = recommendation_input.is_favorite
        market_dislocation = recommendation_input.market_dislocation_pct or 0.0
        opening_edge = recommendation_input.opening_edge_pct
        closing_edge = recommendation_input.closing_edge_pct

        score = self._score(edge, confidence, market_dislocation, is_favorite)
        stake_fraction = self._stake_fraction(edge, confidence, market_dislocation)

        if edge >= 12.0 and market_dislocation >= 4.0:
            profile = RecommendationProfile.HIGH_RISK
            band = RecommendationBand.MARKET_ERROR
            reasoning = "Edge molto alto con dislocazione di mercato: errore sfruttabile."
        elif edge >= 10.0:
            profile = RecommendationProfile.HIGH_RISK
            band = RecommendationBand.AGGRESSIVE
            reasoning = "Edge molto alto: profilo aggressivo."
        elif edge >= 8.0:
            profile = RecommendationProfile.RISKY
            band = RecommendationBand.AGGRESSIVE
            reasoning = "Edge alto: profilo aggressivo ma meno estremo."
        elif edge >= 5.0 and confidence != ConfidenceLevel.LOW:
            profile = RecommendationProfile.VALUE
            band = RecommendationBand.BALANCED
            reasoning = "Edge buono con confidenza sufficiente."
        elif edge >= 3.0 and confidence == ConfidenceLevel.HIGH and market_dislocation <= 2.0:
            profile = RecommendationProfile.SAFE
            band = RecommendationBand.CONSERVATIVE
            reasoning = "Edge moderato con alta confidenza e mercato stabile."
        elif edge >= 2.0 and confidence == ConfidenceLevel.HIGH and is_favorite:
            profile = RecommendationProfile.LOW_RISK
            band = RecommendationBand.UNDERVALUED
            reasoning = "Edge basso ma favorevole su una favorita ad alta confidenza."
        else:
            profile = RecommendationProfile.NO_BET
            band = RecommendationBand.NO_BET
            reasoning = "Edge o confidenza non sufficienti per consigliare la giocata."

        if opening_edge is not None and closing_edge is not None and opening_edge > closing_edge:
            reasoning = f"{reasoning} Apertura migliore della chiusura."

        return RecommendationResult(
            profile=profile,
            band=band,
            confidence_level=confidence,
            recommendation_score=score,
            stake_fraction=stake_fraction,
            reasoning=reasoning,
        )

    @staticmethod
    def _score(edge: float, confidence: ConfidenceLevel, market_dislocation_pct: float, is_favorite: bool) -> int:
        confidence_bonus = {
            ConfidenceLevel.LOW: 0,
            ConfidenceLevel.MEDIUM: 10,
            ConfidenceLevel.HIGH: 20,
        }[confidence]
        favorite_bonus = 5 if is_favorite else 0
        dislocation_bonus = min(max(int(round(market_dislocation_pct * 2.0)), 0), 15)
        raw_score = int(round(edge * 5.0)) + confidence_bonus + favorite_bonus + dislocation_bonus
        return max(0, min(raw_score, 100))

    @staticmethod
    def _stake_fraction(edge: float, confidence: ConfidenceLevel, market_dislocation_pct: float) -> float:
        if edge < 2.0 or confidence == ConfidenceLevel.LOW:
            return 0.0
        base = min(edge / 100.0, 0.12)
        confidence_multiplier = {ConfidenceLevel.LOW: 0.0, ConfidenceLevel.MEDIUM: 0.6, ConfidenceLevel.HIGH: 1.0}[confidence]
        dislocation_multiplier = 1.0 + min(max(market_dislocation_pct, 0.0), 6.0) / 20.0
        return round(min(base * confidence_multiplier * dislocation_multiplier, 0.10), 4)
