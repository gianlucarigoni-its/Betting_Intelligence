"""Print temporal stability, drawdown and CLV diagnostics for backtest runs."""

from __future__ import annotations

import argparse

from backtesting.stability_report import BacktestStabilityAnalyzer, StabilitySliceMetrics
from database.base import SessionLocal


def _parse_run_ids(value: str | None) -> list[int] | None:
    if value is None:
        return None
    run_ids: list[int] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", maxsplit=1)
            run_ids.extend(range(int(start), int(end) + 1))
        else:
            run_ids.append(int(chunk))
    return run_ids or None


def _print_slice(metric: StabilitySliceMetrics) -> None:
    roi = "N/A" if metric.roi_pct is None else f"{metric.roi_pct:.2f}%"
    clv = "N/A" if metric.avg_clv_pct is None else f"{metric.avg_clv_pct:.2f}%"
    roi_ci = "N/A" if metric.roi_ci_low_pct is None else f"[{metric.roi_ci_low_pct:.2f}%, {metric.roi_ci_high_pct:.2f}%]"
    clv_ci = "N/A" if metric.clv_ci_low_pct is None else f"[{metric.clv_ci_low_pct:.2f}%, {metric.clv_ci_high_pct:.2f}%]"
    print(
        f"{metric.label:<24} bets={metric.bets:<4} "
        f"hit={metric.hit_rate:.3f} roi={roi:<8} "
        f"roi_ci={roi_ci:<20} pl={metric.profit_loss:.2f} "
        f"dd={metric.max_drawdown:.2f} clv={clv} clv_ci={clv_ci}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", help="Run ids, e.g. 205-259 or 205,206")
    parser.add_argument("--min-bets", type=int, default=0)
    args = parser.parse_args()

    with SessionLocal() as session:
        report = BacktestStabilityAnalyzer(session).build_report(
            run_ids=_parse_run_ids(args.runs),
            min_bets=args.min_bets,
        )

    print("TOTAL")
    _print_slice(report.total)
    print("\nBY SEASON")
    for metric in report.by_season:
        _print_slice(metric)
    print("\nBY LEAGUE")
    for metric in report.by_league:
        _print_slice(metric)
    print("\nBY SELECTION")
    for metric in report.by_selection:
        _print_slice(metric)


if __name__ == "__main__":
    main()
