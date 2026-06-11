"""Tests for nested selection meta-model walk-forward helpers."""

from __future__ import annotations

from backtesting.run_selection_meta_nested_walkforward import ThresholdSummary, _threshold_score


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
