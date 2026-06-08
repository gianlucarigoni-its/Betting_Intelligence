"""Persistence service for predictions.

This service stores model outputs in the database so dashboard and chatbot
can read a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from database.models import Prediction
from models.value_metrics import ValueMetricsResult
from recommendation.profile_engine import ConfidenceLevel, RecommendationProfile


@dataclass(frozen=True, slots=True)
class PredictionPersistenceInput:
    """Payload required to persist a prediction."""

    match_id: int
    model_version: str
    model_type: str
    market_level: int
    market_type: str
    market_category: str
    selection: str
    estimated_prob: float
    estimated_odd: float
    bookmaker_prob: float | None
    bookmaker_odd: float | None
    bookmaker_id: int | None
    edge_pct: float | None
    expected_value: float | None
    kelly_fraction_raw: float | None
    kelly_fraction: float | None
    kelly_fraction_capped: float | None
    profile_tag: str
    recommendation_score: int | None
    confidence_level: str | None
    reasoning: str | None
    is_correct: bool | None = None
    actual_result: str | None = None


class PredictionPersistenceService:
    """Persist predictions in the database."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_prediction(self, payload: PredictionPersistenceInput) -> Prediction:
        """Create and save a prediction row."""

        prediction = Prediction(
            match_id=payload.match_id,
            model_version=payload.model_version,
            model_type=payload.model_type,
            market_level=payload.market_level,
            market_type=payload.market_type,
            market_category=payload.market_category,
            selection=payload.selection,
            estimated_prob=payload.estimated_prob,
            estimated_odd=payload.estimated_odd,
            bookmaker_prob=payload.bookmaker_prob,
            bookmaker_odd=payload.bookmaker_odd,
            bookmaker_id=payload.bookmaker_id,
            edge_pct=payload.edge_pct,
            expected_value=payload.expected_value,
            kelly_fraction_raw=payload.kelly_fraction_raw,
            kelly_fraction=payload.kelly_fraction,
            kelly_fraction_capped=payload.kelly_fraction_capped,
            profile_tag=payload.profile_tag,
            recommendation_score=payload.recommendation_score,
            confidence_level=payload.confidence_level,
            reasoning=payload.reasoning,
            is_correct=payload.is_correct,
            actual_result=payload.actual_result,
        )
        self._session.add(prediction)
        self._session.commit()
        self._session.refresh(prediction)
        return prediction

    @staticmethod
    def from_value_metrics(
        *,
        match_id: int,
        model_version: str,
        model_type: str,
        market_level: int,
        market_type: str,
        market_category: str,
        selection: str,
        value_metrics: ValueMetricsResult,
        bookmaker_id: int | None,
        profile_tag: RecommendationProfile,
        confidence_level: ConfidenceLevel,
        reasoning: str,
        recommendation_score: int | None = None,
        is_correct: bool | None = None,
        actual_result: str | None = None,
    ) -> PredictionPersistenceInput:
        """Build a persistence payload from higher-level layer outputs."""

        return PredictionPersistenceInput(
            match_id=match_id,
            model_version=model_version,
            model_type=model_type,
            market_level=market_level,
            market_type=market_type,
            market_category=market_category,
            selection=selection,
            estimated_prob=value_metrics.model_probability,
            estimated_odd=value_metrics.bookmaker_odds,
            bookmaker_prob=value_metrics.bookmaker_probability,
            bookmaker_odd=value_metrics.bookmaker_odds,
            bookmaker_id=bookmaker_id,
            edge_pct=value_metrics.edge_pct,
            expected_value=value_metrics.ev,
            kelly_fraction_raw=value_metrics.kelly_fraction,
            kelly_fraction=value_metrics.kelly_fraction,
            kelly_fraction_capped=value_metrics.quarter_kelly_fraction,
            profile_tag=profile_tag.value,
            recommendation_score=recommendation_score,
            confidence_level=confidence_level.value,
            reasoning=reasoning,
            is_correct=is_correct,
            actual_result=actual_result,
        )