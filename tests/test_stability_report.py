"""Tests for backtest stability and CLV metrics."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backtesting.stability_report import BacktestStabilityAnalyzer


def test_max_drawdown_tracks_peak_to_trough_loss() -> None:
    assert BacktestStabilityAnalyzer._max_drawdown([10.0, -5.0, -20.0, 8.0]) == pytest.approx(25.0)


def test_clv_is_positive_when_bet_beats_closing_price() -> None:
    bet = SimpleNamespace(
        match_id=1,
        market_type="1X2",
        selection="HOME",
        bookmaker_id=7,
        bookmaker_odds=2.20,
    )
    closing = SimpleNamespace(odd_value=2.00)

    clv = BacktestStabilityAnalyzer._clv_pct(
        bet,
        {(1, "1X2", "HOME", 7): closing},
    )

    assert clv == pytest.approx(10.0)


def test_clv_is_none_without_closing_price() -> None:
    bet = SimpleNamespace(
        match_id=1,
        market_type="1X2",
        selection="HOME",
        bookmaker_id=7,
        bookmaker_odds=2.20,
    )

    assert BacktestStabilityAnalyzer._clv_pct(bet, {}) is None


def test_bootstrap_roi_ci_returns_ordered_interval() -> None:
    low, high = BacktestStabilityAnalyzer._bootstrap_roi_ci(
        [(10.0, 10.0), (-10.0, 10.0), (8.0, 10.0), (-10.0, 10.0)],
        samples=200,
        seed=1,
    )

    assert low is not None
    assert high is not None
    assert low <= high
    assert low <= -5.0 <= high


def test_bootstrap_mean_ci_returns_ordered_interval() -> None:
    low, high = BacktestStabilityAnalyzer._bootstrap_mean_ci([1.0, 2.0, 3.0], samples=200, seed=1)

    assert low is not None
    assert high is not None
    assert low <= high
    assert low <= 2.0 <= high
