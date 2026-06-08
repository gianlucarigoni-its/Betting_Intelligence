"""
Poisson model per la predizione dei punteggi nel betting calcistico.

Questo layer riceve solo MatchFeatures dal feature engineering,
calcola i lambda attesi per casa e trasferta e produce una distribuzione
di scoreline pronta per successive logiche di edge, EV e Kelly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple

from scipy.stats import poisson

from models.feature_engineering import MatchFeatures, ModelType


MAX_GOALS: int = 7


class MarketSide(str, Enum):
    """Lato del mercato 1X2."""

    HOME = "home"
    DRAW = "draw"
    AWAY = "away"


@dataclass(frozen=True)
class ScorelineProbability:
    """Rappresenta un singolo risultato esatto."""

    home_goals: int
    away_goals: int
    probability: float


@dataclass(frozen=True)
class PoissonPrediction:
    """Output principale del modello Poisson."""

    lambda_home: float
    lambda_away: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    scorelines: tuple[ScorelineProbability, ...]
    most_likely_score: tuple[int, int]
    model_type: ModelType


def _clamp_lambda(value: float, minimum: float = 0.05, maximum: float = 6.0) -> float:
    """Mantiene il lambda in un range realistico per il calcio."""
    return max(minimum, min(maximum, value))


def _estimate_base_lambdas(features: MatchFeatures) -> tuple[float, float]:
    """
    Stima i lambda iniziali usando l'ELO come proxy.

    Senza xG storici, usiamo un'approssimazione semplice:
    squadra più forte -> lambda leggermente più alto.
    """
    base_goals = 1.35
    strength_shift = features.elo_diff / 800.0

    lambda_home = base_goals + strength_shift
    lambda_away = base_goals - strength_shift

    if not features.is_neutral_venue:
        lambda_home += 0.20

    return _clamp_lambda(lambda_home), _clamp_lambda(lambda_away)


def _poisson_probability(lmbda: float, goals: int) -> float:
    """Calcola P(X = goals) per una variabile Poisson."""
    return float(poisson.pmf(goals, lmbda))


def _build_scorelines(lambda_home: float, lambda_away: float) -> tuple[ScorelineProbability, ...]:
    """Genera tutte le combinazioni di punteggio fino a MAX_GOALS."""
    scorelines: list[ScorelineProbability] = []

    for home_goals in range(0, MAX_GOALS + 1):
        for away_goals in range(0, MAX_GOALS + 1):
            probability = _poisson_probability(lambda_home, home_goals) * _poisson_probability(
                lambda_away,
                away_goals,
            )
            scorelines.append(
                ScorelineProbability(
                    home_goals=home_goals,
                    away_goals=away_goals,
                    probability=round(probability, 6),
                ),
            )

    scorelines.sort(key=lambda item: item.probability, reverse=True)
    return tuple(scorelines)


def _aggregate_1x2(scorelines: tuple[ScorelineProbability, ...]) -> tuple[float, float, float]:
    """Somma le probabilità dei punteggi per ottenere il mercato 1X2."""
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for item in scorelines:
        if item.home_goals > item.away_goals:
            home_win += item.probability
        elif item.home_goals == item.away_goals:
            draw += item.probability
        else:
            away_win += item.probability

    total = home_win + draw + away_win
    if total <= 0:
        return 0.0, 0.0, 0.0

    return (
        round(home_win / total, 4),
        round(draw / total, 4),
        round(away_win / total, 4),
    )


class PoissonModel:
    """Modello Poisson per il betting calcistico."""

    def predict(self, features: MatchFeatures) -> PoissonPrediction:
        """
        Genera la predizione completa per una partita.

        Se il feature engineering segnala ELO_ONLY, il modello continua
        comunque a produrre una stima Poisson, ma la confidenza dovrà essere
        gestita a livello superiore.
        """
        lambda_home, lambda_away = _estimate_base_lambdas(features)
        scorelines = _build_scorelines(lambda_home, lambda_away)
        home_win_prob, draw_prob, away_win_prob = _aggregate_1x2(scorelines)

        most_likely = scorelines[0]
        return PoissonPrediction(
            lambda_home=round(lambda_home, 4),
            lambda_away=round(lambda_away, 4),
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            scorelines=scorelines,
            most_likely_score=(most_likely.home_goals, most_likely.away_goals),
            model_type=features.model_type,
        )