"""Tests for data readiness report helpers."""

from backtesting.run_data_readiness_report import DataReadinessRow, _summaries


def test_prediction_and_betting_ready_flags() -> None:
    row = DataReadinessRow("international", 10, 0, 0, 0, 20)
    summary = _summaries([row])[0]

    assert summary.prediction_ready is True
    assert summary.betting_ready is False
