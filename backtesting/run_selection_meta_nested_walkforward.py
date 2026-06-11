"""Nested walk-forward validation for the selection meta-model."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from backtesting.capital_readiness import CapitalReadinessCriteria, evaluate_capital_readiness
from backtesting.run_selection_meta_walkforward import (
    _load_rows,
    _mean_clv_for_bets,
    _parse_run_ids,
    _parse_thresholds,
    _profit_loss_for_bets,
    _roi,
    _season_key,
    _stake_for_bets,
)
from backtesting.selection_meta_model import SelectionMetaModel, build_selection_meta_model_sample
from backtesting.stability_report import BacktestStabilityAnalyzer, StabilityBetRow, StabilitySliceMetrics
from database.base import SessionLocal
from database.models import BacktestBet, Competition, HistoricalOddSnapshot, Match

WalkforwardRow = tuple[BacktestBet, Match, Competition, str]
ClosingOddsMap = dict[tuple[int, str, str, int | None], HistoricalOddSnapshot]
DEFAULT_THRESHOLDS = (0.55, 0.58, 0.59, 0.60, 0.605, 0.61, 0.615, 0.62)


@dataclass(frozen=True, slots=True)
class ThresholdSummary:
    threshold: float
    folds: int
    baseline_bets: int
    baseline_roi: float | None
    baseline_profit_loss: float
    baseline_clv: float | None
    baseline_clv_count: int
    meta_bets: int
    meta_roi: float | None
    meta_profit_loss: float
    meta_clv: float | None
    meta_clv_count: int


@dataclass(frozen=True, slots=True)
class NestedFoldMetrics:
    season: str
    train_seasons: tuple[str, ...]
    selected_threshold: float
    samples: int
    brier: float
    baseline_bets: int
    baseline_roi: float | None
    baseline_profit_loss: float
    baseline_clv: float | None
    baseline_clv_count: int
    meta_bets: int
    meta_roi: float | None
    meta_profit_loss: float
    meta_hit_rate: float
    meta_clv: float | None
    meta_clv_count: int
    inner_threshold: float
    inner_meta_roi: float | None
    inner_meta_clv: float | None
    inner_meta_bets: int


def _format_pct(value: float | None) -> str:
    return "N/A" if value is None or math.isnan(value) else f"{value:.2f}%"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, help="Run ids, e.g. 440-464")
    parser.add_argument("--min-train-seasons", type=int, default=2)
    parser.add_argument("--thresholds", help="Comma-separated thresholds to evaluate")
    parser.add_argument("--min-inner-train-seasons", type=int, default=1)
    parser.add_argument("--min-meta-bets", type=int, default=20)
    parser.add_argument("--min-total-bets", type=int, default=100)
    parser.add_argument("--min-roi-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--min-clv-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--max-drawdown-pct-of-stake", type=float, default=20.0)
    parser.add_argument("--output-model")
    return parser.parse_args()


def _threshold_score(summary: ThresholdSummary, *, min_meta_bets: int) -> tuple[float, ...]:
    meta_roi = summary.meta_roi if summary.meta_roi is not None else float("-inf")
    meta_clv = summary.meta_clv if summary.meta_clv is not None else float("-inf")
    baseline_roi = summary.baseline_roi if summary.baseline_roi is not None else float("-inf")
    baseline_clv = summary.baseline_clv if summary.baseline_clv is not None else float("-inf")
    roi_delta = meta_roi - baseline_roi if math.isfinite(meta_roi) and math.isfinite(baseline_roi) else float("-inf")
    clv_delta = meta_clv - baseline_clv if math.isfinite(meta_clv) and math.isfinite(baseline_clv) else float("-inf")
    hard_gate = int(summary.meta_bets >= min_meta_bets and meta_roi > 0.0 and meta_clv > 0.0)
    return (hard_gate, roi_delta, clv_delta, meta_roi, meta_clv, summary.meta_bets)


def _build_metrics(
    bets: list[BacktestBet],
    closing_odds: ClosingOddsMap,
    label: str,
) -> StabilitySliceMetrics:
    wins = sum(1 for bet in bets if bet.result == "won")
    total_staked = sum(bet.stake for bet in bets)
    profit_loss = sum(bet.profit_loss or 0.0 for bet in bets)
    clv_values = [
        value for value in (BacktestStabilityAnalyzer._clv_pct(bet, closing_odds) for bet in bets) if value is not None
    ]
    roi_ci = BacktestStabilityAnalyzer._bootstrap_roi_ci([(bet.profit_loss or 0.0, bet.stake) for bet in bets])
    clv_ci = BacktestStabilityAnalyzer._bootstrap_mean_ci(clv_values)
    return StabilitySliceMetrics(
        label=label,
        bets=len(bets),
        wins=wins,
        hit_rate=wins / len(bets) if bets else 0.0,
        total_staked=total_staked,
        profit_loss=profit_loss,
        roi_pct=(profit_loss / total_staked) * 100.0 if total_staked else None,
        max_drawdown=BacktestStabilityAnalyzer._max_drawdown([bet.profit_loss or 0.0 for bet in bets]),
        avg_clv_pct=(sum(clv_values) / len(clv_values)) if clv_values else None,
        clv_count=len(clv_values),
        roi_ci_low_pct=roi_ci[0],
        roi_ci_high_pct=roi_ci[1],
        clv_ci_low_pct=clv_ci[0],
        clv_ci_high_pct=clv_ci[1],
    )


def _aggregate_threshold_summary(
    rows: list[WalkforwardRow],
    train_seasons: tuple[str, ...],
    threshold: float,
    closing_odds: ClosingOddsMap,
    *,
    min_inner_train_seasons: int,
) -> ThresholdSummary | None:
    seasons = tuple(sorted(train_seasons, key=_season_key))
    baseline_bets = 0
    baseline_profit_loss = 0.0
    baseline_stake = 0.0
    baseline_clv_sum = 0.0
    baseline_clv_count = 0
    meta_bets = 0
    meta_profit_loss = 0.0
    meta_stake = 0.0
    meta_clv_sum = 0.0
    meta_clv_count = 0
    folds = 0

    for index in range(min_inner_train_seasons, len(seasons)):
        inner_train_seasons = seasons[:index]
        inner_eval_season = seasons[index]
        inner_train_rows = [row for row in rows if row[2].season in inner_train_seasons]
        inner_eval_rows = [row for row in rows if row[2].season == inner_eval_season]
        if not inner_train_rows or not inner_eval_rows:
            continue

        train_samples = [
            build_selection_meta_model_sample(
                bet,
                competition.name,
                odds_snapshot_type=snapshot_type,
            )
            for bet, _match, competition, snapshot_type in inner_train_rows
        ]
        eval_samples = [
            build_selection_meta_model_sample(
                bet,
                competition.name,
                odds_snapshot_type=snapshot_type,
            )
            for bet, _match, competition, snapshot_type in inner_eval_rows
        ]
        if not train_samples or not eval_samples:
            continue

        try:
            model = SelectionMetaModel.train(train_samples)
        except ValueError:
            continue

        scored = [
            (sample, model.predict_probability(sample), bet)
            for sample, (bet, _match, _competition, _snapshot_type) in zip(eval_samples, inner_eval_rows)
        ]
        baseline_bets_fold = [bet for _sample, _probability, bet in scored if bet.is_bet]
        meta_bets_fold = [
            bet for sample, probability, bet in scored if bet.is_bet and probability >= threshold
        ]
        baseline_profit_loss_fold = _profit_loss_for_bets(baseline_bets_fold)
        baseline_stake_fold = _stake_for_bets(baseline_bets_fold)
        meta_profit_loss_fold = _profit_loss_for_bets(meta_bets_fold)
        meta_stake_fold = _stake_for_bets(meta_bets_fold)
        baseline_clv_fold, baseline_clv_count_fold = _mean_clv_for_bets(baseline_bets_fold, closing_odds)
        meta_clv_fold, meta_clv_count_fold = _mean_clv_for_bets(meta_bets_fold, closing_odds)

        baseline_bets += len(baseline_bets_fold)
        baseline_profit_loss += baseline_profit_loss_fold
        baseline_stake += baseline_stake_fold
        meta_bets += len(meta_bets_fold)
        meta_profit_loss += meta_profit_loss_fold
        meta_stake += meta_stake_fold
        if baseline_clv_fold is not None:
            baseline_clv_sum += baseline_clv_fold * baseline_clv_count_fold
            baseline_clv_count += baseline_clv_count_fold
        if meta_clv_fold is not None:
            meta_clv_sum += meta_clv_fold * meta_clv_count_fold
            meta_clv_count += meta_clv_count_fold
        folds += 1

    if folds == 0:
        return None

    baseline_clv = baseline_clv_sum / baseline_clv_count if baseline_clv_count else None
    meta_clv = meta_clv_sum / meta_clv_count if meta_clv_count else None
    return ThresholdSummary(
        threshold=threshold,
        folds=folds,
        baseline_bets=baseline_bets,
        baseline_roi=_roi(baseline_profit_loss, baseline_stake),
        baseline_profit_loss=baseline_profit_loss,
        baseline_clv=baseline_clv,
        baseline_clv_count=baseline_clv_count,
        meta_bets=meta_bets,
        meta_roi=_roi(meta_profit_loss, meta_stake),
        meta_profit_loss=meta_profit_loss,
        meta_clv=meta_clv,
        meta_clv_count=meta_clv_count,
    )


def _select_threshold(
    rows: list[WalkforwardRow],
    train_seasons: tuple[str, ...],
    thresholds: tuple[float, ...],
    closing_odds: ClosingOddsMap,
    *,
    min_inner_train_seasons: int,
    min_meta_bets: int,
) -> tuple[float, ThresholdSummary | None]:
    best_threshold = thresholds[0]
    best_summary: ThresholdSummary | None = None
    best_score = (float("-inf"),)

    for threshold in thresholds:
        summary = _aggregate_threshold_summary(
            rows,
            train_seasons,
            threshold,
            closing_odds,
            min_inner_train_seasons=min_inner_train_seasons,
        )
        if summary is None:
            continue
        score = _threshold_score(summary, min_meta_bets=min_meta_bets)
        if score > best_score:
            best_score = score
            best_threshold = threshold
            best_summary = summary

    return best_threshold, best_summary


def _evaluate_outer_fold(
    rows: list[WalkforwardRow],
    train_seasons: tuple[str, ...],
    holdout_season: str,
    threshold: float,
    closing_odds: ClosingOddsMap,
) -> tuple[NestedFoldMetrics, list[BacktestBet]] | None:
    train_rows = [row for row in rows if row[2].season in train_seasons]
    holdout_rows = [row for row in rows if row[2].season == holdout_season]
    if not train_rows or not holdout_rows:
        return None

    train_samples = [
        build_selection_meta_model_sample(
            bet,
            competition.name,
            odds_snapshot_type=snapshot_type,
        )
        for bet, _match, competition, snapshot_type in train_rows
    ]
    holdout_samples = [
        build_selection_meta_model_sample(
            bet,
            competition.name,
            odds_snapshot_type=snapshot_type,
        )
        for bet, _match, competition, snapshot_type in holdout_rows
    ]
    if not train_samples or not holdout_samples:
        return None

    try:
        model = SelectionMetaModel.train(train_samples)
    except ValueError:
        return None

    scored = [
        (sample, model.predict_probability(sample), bet)
        for sample, (bet, _match, _competition, _snapshot_type) in zip(holdout_samples, holdout_rows)
    ]
    brier = sum((probability - sample.label) ** 2 for sample, probability, _bet in scored) / len(scored)

    baseline_bets = [bet for _sample, _probability, bet in scored if bet.is_bet]
    meta_bets = [bet for sample, probability, bet in scored if bet.is_bet and probability >= threshold]
    baseline_profit_loss = _profit_loss_for_bets(baseline_bets)
    meta_profit_loss = _profit_loss_for_bets(meta_bets)
    baseline_clv, baseline_clv_count = _mean_clv_for_bets(baseline_bets, closing_odds)
    meta_clv, meta_clv_count = _mean_clv_for_bets(meta_bets, closing_odds)
    meta_wins = sum(1 for bet in meta_bets if bet.result == "won")

    metrics = NestedFoldMetrics(
        season=holdout_season,
        train_seasons=train_seasons,
        selected_threshold=threshold,
        samples=len(holdout_samples),
        brier=brier,
        baseline_bets=len(baseline_bets),
        baseline_roi=_roi(baseline_profit_loss, _stake_for_bets(baseline_bets)),
        baseline_profit_loss=baseline_profit_loss,
        baseline_clv=baseline_clv,
        baseline_clv_count=baseline_clv_count,
        meta_bets=len(meta_bets),
        meta_roi=_roi(meta_profit_loss, _stake_for_bets(meta_bets)),
        meta_profit_loss=meta_profit_loss,
        meta_hit_rate=(meta_wins / len(meta_bets)) if meta_bets else 0.0,
        meta_clv=meta_clv,
        meta_clv_count=meta_clv_count,
        inner_threshold=threshold,
        inner_meta_roi=None,
        inner_meta_clv=None,
        inner_meta_bets=0,
    )
    return metrics, meta_bets


def main() -> None:
    args = _parse_args()
    thresholds = _parse_thresholds(args.thresholds) if args.thresholds else DEFAULT_THRESHOLDS
    run_ids = _parse_run_ids(args.runs)

    with SessionLocal() as session:
        rows = _load_rows(session, run_ids)
        closing_odds = BacktestStabilityAnalyzer(session)._load_closing_odds([
            StabilityBetRow(bet=bet, match=match, competition=competition)
            for bet, match, competition, _snapshot_type in rows
        ])

    seasons = tuple(sorted({competition.season for _bet, _match, competition, _snapshot_type in rows}, key=_season_key))
    outer_folds: list[NestedFoldMetrics] = []
    selected_thresholds: list[float] = []
    selected_inner_summaries: list[ThresholdSummary | None] = []
    all_outer_meta_bets: list[BacktestBet] = []

    for index in range(args.min_train_seasons, len(seasons)):
        train_seasons = seasons[:index]
        holdout_season = seasons[index]
        threshold, inner_summary = _select_threshold(
            rows,
            train_seasons,
            thresholds,
            closing_odds,
            min_inner_train_seasons=args.min_inner_train_seasons,
            min_meta_bets=args.min_meta_bets,
        )
        evaluation = _evaluate_outer_fold(rows, train_seasons, holdout_season, threshold, closing_odds)
        if evaluation is None:
            continue
        metrics, meta_bets = evaluation
        outer_folds.append(metrics)
        selected_thresholds.append(threshold)
        selected_inner_summaries.append(inner_summary)
        all_outer_meta_bets.extend(meta_bets)

    baseline_bets = sum(fold.baseline_bets for fold in outer_folds)
    baseline_pl = sum(fold.baseline_profit_loss for fold in outer_folds)
    meta_bets_total = sum(fold.meta_bets for fold in outer_folds)
    meta_pl = sum(fold.meta_profit_loss for fold in outer_folds)
    baseline_stake = baseline_bets * 10.0
    meta_stake = meta_bets_total * 10.0
    baseline_clv_sum = sum(
        fold.baseline_clv * fold.baseline_clv_count
        for fold in outer_folds
        if fold.baseline_clv is not None
    )
    baseline_clv_count = sum(fold.baseline_clv_count for fold in outer_folds)
    baseline_clv = (baseline_clv_sum / baseline_clv_count) if baseline_clv_count else None

    readiness_metrics = _build_metrics(all_outer_meta_bets, closing_odds, label="META")
    criteria = CapitalReadinessCriteria(
        min_bets=args.min_total_bets,
        min_clv_count=args.min_total_bets,
        min_roi_ci_low_pct=args.min_roi_ci_low_pct,
        min_clv_ci_low_pct=args.min_clv_ci_low_pct,
        max_drawdown_pct_of_stake=args.max_drawdown_pct_of_stake,
    )
    readiness = evaluate_capital_readiness(readiness_metrics, criteria)

    print("SEASON        TRAIN_SEASONS  THR    SAMPLES  BRIER   BASE_BETS  BASE_ROI  BASE_CLV  META_BETS  META_ROI  META_CLV  META_HIT")
    for fold, inner_summary in zip(outer_folds, selected_inner_summaries, strict=False):
        print(
            f"{fold.season:<13} {len(fold.train_seasons):<13} {fold.selected_threshold:<5.3f} "
            f"{fold.samples:<7} {fold.brier:.4f}  {fold.baseline_bets:<9} {_format_pct(fold.baseline_roi):<9} "
            f"{_format_pct(fold.baseline_clv):<9} {fold.meta_bets:<9} {_format_pct(fold.meta_roi):<9} "
            f"{_format_pct(fold.meta_clv):<9} {fold.meta_hit_rate:.3f}"
        )
        if inner_summary is not None:
            print(
                f"  inner thr={inner_summary.threshold:.3f} inner meta bets={inner_summary.meta_bets} "
                f"inner meta roi={_format_pct(inner_summary.meta_roi)} inner meta clv={_format_pct(inner_summary.meta_clv)}"
            )

    print("\nSUMMARY")
    print(f"folds={len(outer_folds)}")
    print(
        f"baseline_bets={baseline_bets} baseline_roi={_format_pct(_roi(baseline_pl, baseline_stake))} "
        f"baseline_clv={_format_pct(baseline_clv)} baseline_pl={baseline_pl:.2f}"
    )
    print(
        f"meta_bets={meta_bets_total} meta_roi={_format_pct(_roi(meta_pl, meta_stake))} "
        f"meta_clv={_format_pct(readiness_metrics.avg_clv_pct)} meta_pl={meta_pl:.2f}"
    )
    print(f"CAPITAL_READINESS={'PASS' if readiness.passed else 'FAIL'}")
    print(f"bets={readiness_metrics.bets} clv_count={readiness_metrics.clv_count}")
    print(f"roi={_format_pct(readiness_metrics.roi_pct)} roi_ci=[{_format_pct(readiness_metrics.roi_ci_low_pct)}, {_format_pct(readiness_metrics.roi_ci_high_pct)}]")
    print(f"clv={_format_pct(readiness_metrics.avg_clv_pct)} clv_ci=[{_format_pct(readiness_metrics.clv_ci_low_pct)}, {_format_pct(readiness_metrics.clv_ci_high_pct)}]")
    print(f"drawdown_pct_of_stake={_format_pct((readiness_metrics.max_drawdown / readiness_metrics.total_staked) * 100.0 if readiness_metrics.total_staked else None)}")
    if readiness.failures:
        print("FAILURES")
        for failure in readiness.failures:
            print(f"- {failure}")

    if args.output_model:
        final_samples = [
            build_selection_meta_model_sample(
                bet,
                competition.name,
                odds_snapshot_type=snapshot_type,
            )
            for bet, _match, competition, snapshot_type in rows
        ]
        if final_samples:
            model = SelectionMetaModel.train(final_samples)
            model.save(Path(args.output_model))
            print(f"saved_model={args.output_model}")


if __name__ == "__main__":
    main()
