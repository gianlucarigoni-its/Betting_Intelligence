"""Lightweight meta-model for betting selection reliability."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline
from sqlalchemy.orm import Session

from database.models import BacktestBet, Competition, Match


@dataclass(frozen=True, slots=True)
class SelectionMetaModelSample:
    """One supervised example for the meta-model."""

    selection: str
    league: str
    edge_pct: float
    bookmaker_odds: float
    model_probability: float
    bookmaker_probability: float
    model_market_distance: float
    lambda_home: float
    lambda_away: float
    lambda_gap: float
    label: int


class SelectionMetaModel:
    """Small calibrated classifier for bet reliability."""

    CATEGORICAL_FEATURES = ("selection", "league")
    NUMERIC_FEATURES = (
        "edge_pct",
        "bookmaker_odds",
        "model_probability",
        "bookmaker_probability",
        "model_market_distance",
        "lambda_home",
        "lambda_away",
        "lambda_gap",
    )

    def __init__(self, pipeline: Pipeline | None = None) -> None:
        self._pipeline = pipeline or self._build_pipeline()

    @classmethod
    def train(cls, samples: list[SelectionMetaModelSample]) -> "SelectionMetaModel":
        if not samples:
            raise ValueError("selection meta-model training requires samples")

        model = cls()
        model._pipeline.fit([cls._features(sample) for sample in samples], [sample.label for sample in samples])
        return model

    @classmethod
    def load(cls, path: str | Path) -> "SelectionMetaModel":
        with Path(path).open("rb") as fh:
            pipeline = pickle.load(fh)
        return cls(pipeline)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            pickle.dump(self._pipeline, fh)

    def predict_probability(self, sample: SelectionMetaModelSample) -> float:
        probabilities = self._pipeline.predict_proba([self._features(sample)])[0]
        return float(probabilities[1])

    def predict_probability_for_features(self, features: dict[str, object]) -> float:
        probabilities = self._pipeline.predict_proba([features])[0]
        return float(probabilities[1])

    @staticmethod
    def load_training_samples(
        session: Session,
        *,
        run_ids: Iterable[int] | None = None,
    ) -> list[SelectionMetaModelSample]:
        query = (
            session.query(BacktestBet, Match, Competition)
            .join(Match, BacktestBet.match_id == Match.id)
            .join(Competition, Match.competition_id == Competition.id)
            .filter(BacktestBet.result.is_not(None))
        )
        if run_ids is not None:
            query = query.filter(BacktestBet.backtest_run_id.in_(list(run_ids)))

        samples: list[SelectionMetaModelSample] = []
        for bet, _match, competition in query.all():
            if bet.result == "pending":
                continue
            samples.append(build_selection_meta_model_sample(bet, competition.name))
        return samples

    @staticmethod
    def _features(sample: SelectionMetaModelSample) -> dict[str, object]:
        return {
            "selection": sample.selection,
            "league": sample.league,
            "edge_pct": sample.edge_pct,
            "bookmaker_odds": sample.bookmaker_odds,
            "model_probability": sample.model_probability,
            "bookmaker_probability": sample.bookmaker_probability,
            "model_market_distance": sample.model_market_distance,
            "lambda_home": sample.lambda_home,
            "lambda_away": sample.lambda_away,
            "lambda_gap": sample.lambda_gap,
        }

    @classmethod
    def _build_pipeline(cls) -> Pipeline:
        classifier = LogisticRegression(max_iter=2000, class_weight="balanced")
        return Pipeline([
            ("vectorizer", DictVectorizer(sparse=False)),
            ("classifier", classifier),
        ])


def build_selection_meta_model_sample(
    bet: BacktestBet,
    league_name: str,
) -> SelectionMetaModelSample:
    """Build one meta-model sample from a persisted backtest record."""

    payload = _parse_reason_payload(bet.reason or "")
    lambda_home = _float_from_payload(payload, "lambda_home")
    lambda_away = _float_from_payload(payload, "lambda_away")
    return SelectionMetaModelSample(
        selection=bet.selection,
        league=league_name,
        edge_pct=bet.edge_pct,
        bookmaker_odds=bet.bookmaker_odds,
        model_probability=bet.model_probability,
        bookmaker_probability=bet.bookmaker_probability,
        model_market_distance=abs(bet.model_probability - bet.bookmaker_probability),
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        lambda_gap=abs(lambda_home - lambda_away),
        label=1 if bet.result == "won" else 0,
    )


def _parse_reason_payload(reason: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for chunk in reason.split("; "):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", maxsplit=1)
        payload[key.strip()] = value.strip()
    return payload


def _float_from_payload(payload: dict[str, str], key: str) -> float:
    raw = payload.get(key)
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0
