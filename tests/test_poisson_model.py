"""
Test per il PoissonModel.

Copre:
- output coerente
- lambda positivi
- somma probabilità ragionevole
- score più probabile presente
- gestione del model_type ereditato dalle feature
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from models.feature_engineering import ConfidenceLevel, MatchFeatures, ModelType
from models.poisson_model import PoissonModel


def build_features(**overrides) -> MatchFeatures:
    """Factory di test per creare feature valide in modo semplice."""
    base = MatchFeatures(
        home_team_id=1,
        away_team_id=2,
        home_team_name="Spain",
        away_team_name="Germany",
        home_elo=2155.0,
        away_elo=1932.0,
        elo_diff=223.0,
        home_elo_win_prob=0.6211,
        away_elo_win_prob=0.1720,
        draw_prob_elo=0.2069,
        home_matches_count=0,
        away_matches_count=0,
        model_type=ModelType.ELO_ONLY,
        confidence=ConfidenceLevel.LOW,
        is_neutral_venue=True,
    )
    return replace(base, **overrides)


class TestPoissonModel:
    def test_predict_returns_valid_output(self) -> None:
        model = PoissonModel()
        features = build_features()

        prediction = model.predict(features)

        assert prediction.lambda_home > 0
        assert prediction.lambda_away > 0
        assert 0 <= prediction.home_win_prob <= 1
        assert 0 <= prediction.draw_prob <= 1
        assert 0 <= prediction.away_win_prob <= 1
        assert prediction.model_type == ModelType.ELO_ONLY

    def test_prediction_probabilities_sum_reasonably(self) -> None:
        model = PoissonModel()
        features = build_features()

        prediction = model.predict(features)
        total = prediction.home_win_prob + prediction.draw_prob + prediction.away_win_prob

        assert total == pytest.approx(1.0, abs=0.02)

    def test_scorelines_are_sorted_descending(self) -> None:
        model = PoissonModel()
        features = build_features()

        prediction = model.predict(features)

        probabilities = [item.probability for item in prediction.scorelines]
        assert probabilities == sorted(probabilities, reverse=True)

    def test_most_likely_score_is_present(self) -> None:
        model = PoissonModel()
        features = build_features()

        prediction = model.predict(features)

        assert prediction.most_likely_score in {
            (item.home_goals, item.away_goals) for item in prediction.scorelines
        }

    def test_favorite_gets_higher_home_lambda(self) -> None:
        model = PoissonModel()
        strong_home = build_features(elo_diff=300.0)
        weak_home = build_features(elo_diff=-300.0)

        strong_prediction = model.predict(strong_home)
        weak_prediction = model.predict(weak_home)

        assert strong_prediction.lambda_home > strong_prediction.lambda_away
        assert weak_prediction.lambda_home < weak_prediction.lambda_away

    def test_neutral_vs_non_neutral_changes_lambda_home(self) -> None:
        model = PoissonModel()
        neutral = build_features(is_neutral_venue=True)
        non_neutral = build_features(is_neutral_venue=False)

        neutral_prediction = model.predict(neutral)
        non_neutral_prediction = model.predict(non_neutral)

        assert non_neutral_prediction.lambda_home > neutral_prediction.lambda_home