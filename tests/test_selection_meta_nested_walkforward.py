"""Tests for nested selection meta-model walk-forward helpers."""

from __future__ import annotations

from types import SimpleNamespace

from backtesting.run_selection_meta_nested_walkforward import ThresholdSummary, _combined_probability, _label_for_strategy, _threshold_score
from backtesting.selection_meta_model import build_selection_meta_model_sample


def _summary(*, threshold: float, bets: int, roi: float, clv: float, baseline_roi: float = -5.0, baseline_clv: float = -0.5) -> ThresholdSummary:
    return ThresholdSummary(
        threshold=threshold,
        folds=2,
        baseline_bets=100,
        baseline_roi=baseline_roi,
        baseline_profit_loss=baseline_roi,
        baseline_clv=baseline_clv,
        baseline_clv_count=100,
        meta_bets=bets,
        meta_roi=roi,
        meta_profit_loss=roi,
        meta_clv=clv,
        meta_clv_count=bets,
    )


def test_threshold_score_prioritizes_volume_positive_roi_and_clv_gate() -> None:
    low_volume = _summary(threshold=0.62, bets=10, roi=25.0, clv=2.0)
    deployable_shape = _summary(threshold=0.60, bets=25, roi=6.0, clv=0.2)

    assert _threshold_score(deployable_shape, min_meta_bets=20) > _threshold_score(low_volume, min_meta_bets=20)


def test_threshold_score_prefers_higher_improvement_when_gate_passes() -> None:
    lower_uplift = _summary(threshold=0.58, bets=50, roi=4.0, clv=0.1)
    higher_uplift = _summary(threshold=0.60, bets=45, roi=8.0, clv=0.2)

    assert _threshold_score(higher_uplift, min_meta_bets=20) > _threshold_score(lower_uplift, min_meta_bets=20)


def test_label_for_strategy_can_target_positive_clv() -> None:
    bet = SimpleNamespace(
        result="lost",
        match_id=10,
        market_type="OU_2_5",
        selection="OVER_2_5",
        bookmaker_id=1,
        bookmaker_odds=2.10,
    )
    closing = SimpleNamespace(odd_value=2.00)
    closing_odds = {(10, "OU_2_5", "OVER_2_5", 1): closing}

    assert _label_for_strategy(bet, closing_odds, "clv_positive", clv_threshold_pct=0.0) == 1
    assert _label_for_strategy(bet, closing_odds, "clv_positive", clv_threshold_pct=5.5) == 0
    assert _label_for_strategy(bet, closing_odds, "win_and_clv_positive", clv_threshold_pct=0.0) == 0


def test_sample_builder_label_override_sets_supervised_target() -> None:
    bet = SimpleNamespace(
        selection="OVER_2_5",
        market_type="OU_2_5",
        edge_pct=5.0,
        bookmaker_odds=2.0,
        model_probability=0.55,
        bookmaker_probability=0.50,
        result="lost",
        reason="lambda_home=1.5; lambda_away=1.2",
    )

    sample = build_selection_meta_model_sample(
        bet,
        "Premier League",
        odds_snapshot_type="opening",
        label_override=1,
    )

    assert sample.label == 1
    assert sample.market_type == "OU_2_5"
    assert sample.odds_snapshot_type == "opening"


def test_combined_probability_supports_mean_and_min() -> None:
    class FakeModel:
        def __init__(self, probability: float) -> None:
            self._probability = probability

        def predict_probability(self, sample):
            return self._probability

    bet = SimpleNamespace(
        selection="OVER_2_5",
        market_type="OU_2_5",
        edge_pct=5.0,
        bookmaker_odds=2.0,
        model_probability=0.55,
        bookmaker_probability=0.50,
        result="won",
        reason="lambda_home=1.5; lambda_away=1.2",
        bookmaker_id=1,
        match_id=10,
    )
    competition = SimpleNamespace(name="Premier League")
    row = (bet, None, competition, "opening")
    closing_odds = {(10, "OU_2_5", "OVER_2_5", 1): SimpleNamespace(odd_value=1.90)}

    mean_score = _combined_probability(
        row,
        closing_odds,
        FakeModel(0.70),
        FakeModel(0.50),
        "win",
        clv_threshold_pct=0.0,
        dual_combination="mean",
    )
    min_score = _combined_probability(
        row,
        closing_odds,
        FakeModel(0.70),
        FakeModel(0.50),
        "win",
        clv_threshold_pct=0.0,
        dual_combination="min",
    )

    assert mean_score == 0.60
    assert min_score == 0.50
