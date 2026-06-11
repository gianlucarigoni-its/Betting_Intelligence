"""Tests for real-capital readiness gates."""

from __future__ import annotations

from backtesting.capital_readiness import CapitalReadinessCriteria, evaluate_capital_readiness
from backtesting.stability_report import StabilitySliceMetrics


def _metrics(**overrides) -> StabilitySliceMetrics:
    payload = {
        "label": "TOTAL",
        "bets": 150,
        "wins": 90,
        "hit_rate": 0.6,
        "total_staked": 1500.0,
        "profit_loss": 150.0,
        "roi_pct": 10.0,
        "max_drawdown": 100.0,
        "avg_clv_pct": 1.0,
        "clv_count": 150,
        "roi_ci_low_pct": 2.0,
        "roi_ci_high_pct": 18.0,
        "clv_ci_low_pct": 0.2,
        "clv_ci_high_pct": 1.8,
    }
    payload.update(overrides)
    return StabilitySliceMetrics(**payload)


def test_capital_readiness_passes_when_all_gates_pass() -> None:
    result = evaluate_capital_readiness(_metrics(), CapitalReadinessCriteria())

    assert result.passed
    assert result.failures == ()


def test_capital_readiness_fails_on_low_volume_and_negative_ci() -> None:
    result = evaluate_capital_readiness(
        _metrics(bets=21, clv_count=21, roi_ci_low_pct=-5.0, clv_ci_low_pct=-0.1),
        CapitalReadinessCriteria(min_bets=100, min_clv_count=100),
    )

    assert not result.passed
    assert any("bets" in failure for failure in result.failures)
    assert any("roi_ci_low" in failure for failure in result.failures)
    assert any("clv_ci_low" in failure for failure in result.failures)
