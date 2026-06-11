"""Evaluate whether a backtest slice is ready for real-capital deployment."""

from __future__ import annotations

import argparse

from backtesting.capital_readiness import CapitalReadinessCriteria, evaluate_capital_readiness, evaluate_slice_readiness
from backtesting.run_stability_report import _parse_run_ids
from backtesting.stability_report import BacktestStabilityAnalyzer
from database.base import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, help="Run ids, e.g. 265-314")
    parser.add_argument("--min-bets", type=int, default=100)
    parser.add_argument("--min-clv-count", type=int, default=100)
    parser.add_argument("--min-roi-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--min-clv-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--max-drawdown-pct-of-stake", type=float, default=20.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    criteria = CapitalReadinessCriteria(
        min_bets=args.min_bets,
        min_clv_count=args.min_clv_count,
        min_roi_ci_low_pct=args.min_roi_ci_low_pct,
        min_clv_ci_low_pct=args.min_clv_ci_low_pct,
        max_drawdown_pct_of_stake=args.max_drawdown_pct_of_stake,
    )
    with SessionLocal() as session:
        report = BacktestStabilityAnalyzer(session).build_report(run_ids=_parse_run_ids(args.runs))

    result = evaluate_capital_readiness(report.total, criteria)
    status = "PASS" if result.passed else "FAIL"
    drawdown = "N/A" if result.drawdown_pct_of_stake is None else f"{result.drawdown_pct_of_stake:.2f}%"
    roi_ci = (
        "N/A"
        if report.total.roi_ci_low_pct is None
        else f"[{report.total.roi_ci_low_pct:.2f}%, {report.total.roi_ci_high_pct:.2f}%]"
    )
    clv_ci = (
        "N/A"
        if report.total.clv_ci_low_pct is None
        else f"[{report.total.clv_ci_low_pct:.2f}%, {report.total.clv_ci_high_pct:.2f}%]"
    )
    print(f"CAPITAL_READINESS={status}")
    print(f"bets={report.total.bets} clv_count={report.total.clv_count}")
    print(f"roi={report.total.roi_pct:.2f}% roi_ci={roi_ci}")
    print(f"clv={report.total.avg_clv_pct:.2f}% clv_ci={clv_ci}")
    print(f"drawdown_pct_of_stake={drawdown}")
    if result.failures:
        print("FAILURES")
        for failure in result.failures:
            print(f"- {failure}")

    print("
BY_SELECTION_READINESS")
    for metric in report.by_selection:
        slice_result = evaluate_slice_readiness(metric, criteria)
        slice_status = "PASS" if slice_result.passed else "FAIL"
        print(f"{metric.label:<24} {slice_status} bets={metric.bets} roi={metric.roi_pct:.2f}% clv={metric.avg_clv_pct:.2f}%")
        if slice_result.failures:
            print("  FAILURES")
            for failure in slice_result.failures:
                print(f"  - {failure}")


if __name__ == "__main__":
    main()
