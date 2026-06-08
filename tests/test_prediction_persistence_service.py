"""Tests for prediction persistence service."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Prediction
from models.value_metrics import ValueMetricsResult
from recommendation.profile_engine import ConfidenceLevel, RecommendationProfile
from services.prediction_persistence_service import (
    PredictionPersistenceService,
    PredictionPersistenceInput,
)


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestPredictionPersistenceService:
    def test_create_prediction_persists_row(self) -> None:
        session = build_session()
        service = PredictionPersistenceService(session)
        payload = PredictionPersistenceInput(
            match_id=1,
            model_version="1.0",
            model_type="poisson",
            market_level=1,
            market_type="1X2",
            market_category="match_result",
            selection="HOME",
            estimated_prob=0.60,
            estimated_odd=2.00,
            bookmaker_prob=0.50,
            bookmaker_odd=2.00,
            bookmaker_id=None,
            edge_pct=10.0,
            expected_value=0.20,
            kelly_fraction_raw=0.20,
            kelly_fraction=0.20,
            kelly_fraction_capped=0.05,
            profile_tag="VALUE",
            recommendation_score=80,
            confidence_level="HIGH",
            reasoning="test",
            is_correct=None,
            actual_result=None,
        )

        prediction = service.create_prediction(payload)

        assert prediction.id is not None
        stored = session.query(Prediction).one()
        assert stored.match_id == 1
        assert stored.model_version == "1.0"
        assert stored.model_type == "poisson"
        assert stored.profile_tag == "VALUE"
        assert stored.confidence_level == "HIGH"
        assert stored.reasoning == "test"

    def test_from_value_metrics_builds_payload(self) -> None:
        value_metrics = ValueMetricsResult(
            model_probability=0.60,
            bookmaker_probability=0.50,
            bookmaker_odds=2.00,
            edge_pct=10.0,
            ev=0.20,
            kelly_fraction=0.20,
            quarter_kelly_fraction=0.05,
        )

        payload = PredictionPersistenceService.from_value_metrics(
            match_id=2,
            model_version="1.0",
            model_type="poisson",
            market_level=1,
            market_type="1X2",
            market_category="match_result",
            selection="AWAY",
            value_metrics=value_metrics,
            bookmaker_id=None,
            profile_tag=RecommendationProfile.SAFE,
            confidence_level=ConfidenceLevel.HIGH,
            reasoning="ok",
        )

        assert payload.match_id == 2
        assert payload.profile_tag == "SAFE"
        assert payload.confidence_level == "HIGH"
        assert payload.edge_pct == 10.0
        assert payload.kelly_fraction_capped == 0.05