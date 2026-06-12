"""Tests for market coverage report helpers."""

from backtesting.run_market_coverage_report import MarketCoverageRow, _summaries


def test_summaries_count_opening_and_closing_seasons() -> None:
    rows = [
        MarketCoverageRow("2020/2021", "OU_2_5", 10, 10, "league"),
        MarketCoverageRow("2021/2022", "OU_2_5", 0, 10, "league"),
        MarketCoverageRow("2021/2022", "1X2", 20, 20, "league"),
    ]

    summaries = {summary.market_type: summary for summary in _summaries(rows)}

    assert summaries["OU_2_5"].seasons_with_opening == 1
    assert summaries["OU_2_5"].seasons_with_closing == 2
    assert summaries["OU_2_5"].opening_snapshots == 10
    assert summaries["OU_2_5"].closing_snapshots == 20


def test_summaries_are_split_by_competition_type() -> None:
    rows = [
        MarketCoverageRow("2024", "1X2", 10, 10, "league"),
        MarketCoverageRow("2024", "1X2", 0, 0, "international"),
    ]

    summaries = {(summary.competition_type, summary.market_type): summary for summary in _summaries(rows)}

    assert summaries[("league", "1X2")].opening_snapshots == 10
    assert summaries[("international", "1X2")].opening_snapshots == 0
