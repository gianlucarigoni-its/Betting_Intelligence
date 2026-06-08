"""Recommendation engine for betting profiles.

This layer classifies opportunities into predefined profiles based on edge,
confidence and risk rules.
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


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    """Classification output produced by the engine."""

    profile: RecommendationProfile
    confidence_level: ConfidenceLevel
    reasoning: str


class RecommendationEngine:
    """Assign a betting profile from edge and confidence rules."""

    def classify(self, recommendation_input: RecommendationInput) -> RecommendationResult:
        """Classify a bet opportunity into one profile."""

        edge = recommendation_input.value_metrics.edge_pct
        confidence = recommendation_input.confidence_level
        is_favorite = recommendation_input.is_favorite

        if edge >= 12.0:
            profile = RecommendationProfile.HIGH_RISK
            reasoning = "Edge molto alto: profilo aggressivo."
        elif edge >= 8.0:
            profile = RecommendationProfile.RISKY
            reasoning = "Edge alto: profilo aggressivo ma meno estremo."
        elif edge >= 5.0 and confidence != ConfidenceLevel.LOW:
            profile = RecommendationProfile.VALUE
            reasoning = "Edge buono con confidenza sufficiente."
        elif edge >= 3.0 and confidence == ConfidenceLevel.HIGH:
            profile = RecommendationProfile.SAFE
            reasoning = "Edge moderato con alta confidenza."
        elif edge >= 2.0 and confidence == ConfidenceLevel.HIGH and is_favorite:
            profile = RecommendationProfile.LOW_RISK
            reasoning = "Edge basso ma favorevole su una favorita ad alta confidenza."
        else:
            profile = RecommendationProfile.NO_BET
            reasoning = "Edge o confidenza non sufficienti per consigliare la giocata."

        return RecommendationResult(
            profile=profile,
            confidence_level=confidence,
            reasoning=reasoning,
        )