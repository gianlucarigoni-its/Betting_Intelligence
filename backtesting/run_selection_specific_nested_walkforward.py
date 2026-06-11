"""Selection-specific nested walk-forward validation and deployment gating."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from backtesting.capital_readiness import CapitalReadinessCriteria, evaluate_slice_readiness
from backtesting.run_selection_meta_nested_walkforward import (
    DEFAULT_THRESHOLDS,
    ClosingOddsMap,
    NestedFoldMetrics,
    ThresholdSummary,
    WalkforwardRow,
    _build_metrics,
    _evaluate_outer_fold,
    _format_pct,
    _select_threshold,
)
from backtesting.run_selection_meta_walkforward import _load_rows, _parse_run_ids, _parse_thresholds, _season_key
from backtesting.stability_report import BacktestStabilityAnalyzer, StabilityBetRow
from database.base import SessionLocal
from database.models import BacktestBet


@dataclass(frozen=True, slots=True)
class SelectionFoldResult:
    selection: str
    fold: NestedFoldMetrics
    inner_summary: ThresholdSummary | None


def _parse_selections(raw: str) -> tuple[str, ...]:
    selections = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not selections:
        raise ValueError("at least one selection is required")
    return selections


def _rows_for_selection(rows: list[WalkforwardRow], selection: str) -> list[WalkforwardRow]:
    return [row for row in rows if row[0].selection == selection]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--selections", default="OVER_2_5,UNDER_2_5")
    parser.add_argument("--min-train-seasons", type=int, default=2)
    parser.add_argument("--min-inner-train-seasons", type=int, default=1)
    parser.add_argument("--min-meta-bets", type=int, default=20)
    parser.add_argument("--min-total-bets", type=int, default=100)
    parser.add_argument("--thresholds")
    parser.add_argument("--label-strategy", choices=("win", "clv_positive", "win_and_clv_positive"), default="win")
    parser.add_argument("--selection-objective", choices=("quality", "volume_first"), default="quality")
    parser.add_argument("--clv-threshold-pct", type=float, default=0.0)
    parser.add_argument("--use-dual-model", action="store_true")
    parser.add_argument("--dual-combination", choices=("mean", "min"), default="mean")
    parser.add_argument("--min-roi-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--min-clv-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--max-drawdown-pct-of-stake", type=float, default=20.0)
    return parser.parse_args()


def _evaluate_selection(
    rows: list[WalkforwardRow],
    selection: str,
    seasons: tuple[str, ...],
    thresholds: tuple[float, ...],
    closing_odds: ClosingOddsMap,
    args: argparse.Namespace,
) -> tuple[list[SelectionFoldResult], list[BacktestBet]]:
    selection_rows = _rows_for_selection(rows, selection)
    results: list[SelectionFoldResult] = []
    selected_bets: list[BacktestBet] = []
    for index in range(args.min_train_seasons, len(seasons)):
        train_seasons = seasons[:index]
        holdout_season = seasons[index]
        threshold, inner_summary = _select_threshold(
            selection_rows,
            train_seasons,
            thresholds,
            closing_odds,
            min_inner_train_seasons=args.min_inner_train_seasons,
            min_meta_bets=args.min_meta_bets,
            label_strategy=args.label_strategy,
            objective=args.selection_objective,
            clv_threshold_pct=args.clv_threshold_pct,
            use_dual_model=args.use_dual_model,
            dual_combination=args.dual_combination,
        )
        evaluation = _evaluate_outer_fold(
            selection_rows,
            train_seasons,
            holdout_season,
            threshold,
            closing_odds,
            args.label_strategy,
            args.selection_objective,
            args.clv_threshold_pct,
            args.use_dual_model,
            args.dual_combination,
        )
        if evaluation is None:
            continue
        fold, bets = evaluation
        results.append(SelectionFoldResult(selection, fold, inner_summary))
        selected_bets.extend(bets)
    return results, selected_bets


def main() -> None:
    args = _parse_args()
    selections = _parse_selections(args.selections)
    thresholds = _parse_thresholds(args.thresholds) if args.thresholds else DEFAULT_THRESHOLDS
    with SessionLocal() as session:
        rows = _load_rows(session, _parse_run_ids(args.runs))
        closing_odds = BacktestStabilityAnalyzer(session)._load_closing_odds([
            StabilityBetRow(bet=bet, match=match, competition=competition)
            for bet, match, competition, _snapshot_type in rows
        ])

    seasons = tuple(sorted({competition.season for _bet, _match, competition, _snapshot in rows}, key=_season_key))
    criteria = CapitalReadinessCriteria(
        min_bets=args.min_total_bets,
        min_clv_count=args.min_total_bets,
        min_roi_ci_low_pct=args.min_roi_ci_low_pct,
        min_clv_ci_low_pct=args.min_clv_ci_low_pct,
        max_drawdown_pct_of_stake=args.max_drawdown_pct_of_stake,
    )
    combined_bets: list[BacktestBet] = []
    all_selection_pass = True

    for selection in selections:
        results, bets = _evaluate_selection(rows, selection, seasons, thresholds, closing_odds, args)
        combined_bets.extend(bets)
        print(f"SELECTION={selection}")
        for result in results:
            fold = result.fold
            print(
                f"{fold.season} threshold={fold.selected_threshold:.3f} bets={fold.meta_bets} "
                f"roi={_format_pct(fold.meta_roi)} clv={_format_pct(fold.meta_clv)}"
            )
        metrics = _build_metrics(bets, closing_odds, selection)
        readiness = evaluate_slice_readiness(metrics, criteria)
        all_selection_pass = all_selection_pass and readiness.passed
        print(
            f"SUMMARY bets={metrics.bets} roi={_format_pct(metrics.roi_pct)} "
            f"roi_ci=[{_format_pct(metrics.roi_ci_low_pct)}, {_format_pct(metrics.roi_ci_high_pct)}] "
            f"clv={_format_pct(metrics.avg_clv_pct)} "
            f"clv_ci=[{_format_pct(metrics.clv_ci_low_pct)}, {_format_pct(metrics.clv_ci_high_pct)}]"
        )
        print(f"SELECTION_READINESS={'PASS' if readiness.passed else 'FAIL'}")
        for failure in readiness.failures:
            print(f"- {failure}")
        print()

    combined_metrics = _build_metrics(combined_bets, closing_odds, "COMBINED")
    combined_readiness = evaluate_slice_readiness(combined_metrics, criteria)
    production_pass = all_selection_pass and combined_readiness.passed
    print("COMBINED")
    print(
        f"bets={combined_metrics.bets} roi={_format_pct(combined_metrics.roi_pct)} "
        f"roi_ci=[{_format_pct(combined_metrics.roi_ci_low_pct)}, {_format_pct(combined_metrics.roi_ci_high_pct)}] "
        f"clv={_format_pct(combined_metrics.avg_clv_pct)} "
        f"clv_ci=[{_format_pct(combined_metrics.clv_ci_low_pct)}, {_format_pct(combined_metrics.clv_ci_high_pct)}]"
    )
    print(f"PRODUCTION_READINESS={'PASS' if production_pass else 'FAIL'}")
    if not combined_readiness.passed:
        for failure in combined_readiness.failures:
            print(f"- combined: {failure}")
    if not all_selection_pass:
        print("- one or more selection slices failed readiness")


if __name__ == "__main__":
    main()
