"""Tests for the lightweight betting selection meta-model."""

from __future__ import annotations

import pytest

from backtesting.selection_meta_model import SelectionMetaModel, SelectionMetaModelSample


def _sample(
    *,
    selection: str,
    league: str,
    edge: float,
    odds: float,
    model_prob: float,
    bookmaker_prob: float,
    lambda_home: float,
    lambda_away: float,
    label: int,
) -> SelectionMetaModelSample:
    return SelectionMetaModelSample(
        selection=selection,
        league=league,
        edge_pct=edge,
        bookmaker_odds=odds,
        model_probability=model_prob,
        bookmaker_probability=bookmaker_prob,
        model_market_distance=abs(model_prob - bookmaker_prob),
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        lambda_gap=abs(lambda_home - lambda_away),
        label=label,
    )


def test_selection_meta_model_trains_saves_and_loads(tmp_path) -> None:
    samples = [
        _sample(selection="HOME", league="A", edge=6.0, odds=1.75, model_prob=0.62, bookmaker_prob=0.56, lambda_home=1.8, lambda_away=0.8, label=1),
        _sample(selection="HOME", league="A", edge=5.5, odds=1.80, model_prob=0.61, bookmaker_prob=0.55, lambda_home=1.7, lambda_away=0.9, label=1),
        _sample(selection="AWAY", league="A", edge=6.0, odds=2.40, model_prob=0.47, bookmaker_prob=0.41, lambda_home=1.5, lambda_away=1.1, label=0),
        _sample(selection="DRAW", league="B", edge=4.0, odds=3.30, model_prob=0.31, bookmaker_prob=0.28, lambda_home=1.2, lambda_away=1.2, label=0),
    ]
    model = SelectionMetaModel.train(samples)
    probability = model.predict_probability(samples[0])

    assert 0.0 <= probability <= 1.0

    path = tmp_path / "selection_meta.pkl"
    model.save(path)
    loaded = SelectionMetaModel.load(path)

    assert loaded.predict_probability(samples[0]) == pytest.approx(probability)


def test_selection_meta_model_requires_samples() -> None:
    with pytest.raises(ValueError, match="requires samples"):
        SelectionMetaModel.train([])
