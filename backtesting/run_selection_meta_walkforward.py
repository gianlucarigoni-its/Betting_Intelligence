"""Walk-forward validation for the selection meta-model."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from backtesting.selection_meta_model import (
    SelectionMetaModel,
    build_selection_meta_model_sample,
    _odds_snapshot_type_from_notes,
)
from backtesting.stability_report import BacktestStabilityAnalyzer, StabilityBetRow
from database.base import SessionLocal
from database.models import BacktestBet, BacktestRun, Competition, HistoricalOddSnapshot, Match


WalkforwardRow = tuple[BacktestBet, Match, Competition, str]
ClosingOddsMap = dict[tuple[int, str, str, int | None], HistoricalOddSnapshot]


@dataclass(frozen=True, slots=True)
class MetaFoldMetrics:
    season: str
    train_seasons: tuple[str, ...]
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


def _parse_run_ids(value: str) -> list[int]:
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
    return run_ids


def _parse_thresholds(value: str) -> tuple[float, ...]:
    return tuple(float(chunk.strip()) for chunk in value.split(",") if chunk.strip())


def _season_key(season: str) -> int:
    return int(season.split("/")[0])


def _meta_threshold(selection: str, override: float | None = None) -> float:
    if override is not None:
        return override
    if selection == "DRAW":
        return 0.52
    if selection == "AWAY":
        return 0.58
    return 0.55


def _roi(profit_loss: float, stake: float) -> float | None:
    return (profit_loss / stake) * 100.0 if stake > 0 else None


def _load_rows(session, run_ids: list[int]) -> list[WalkforwardRow]:
    rows = (
        session.query(BacktestBet, Match, Competition, BacktestRun)
        .join(Match, BacktestBet.match_id == Match.id)
        .join(Competition, Match.competition_id == Competition.id)
        .join(BacktestRun, BacktestBet.backtest_run_id == BacktestRun.id)
        .filter(
            BacktestBet.backtest_run_id.in_(run_ids),
            BacktestBet.result != "pending",
        )
        .all()
    )
    return [
        (bet, match, competition, _odds_snapshot_type_from_notes(run.notes))
        for bet, match, competition, run in rows
    ]


def _profit_loss_for_bets(bets: list[BacktestBet]) -> float:
    return sum(bet.profit_loss or 0.0 for bet in bets)


def _stake_for_bets(bets: list[BacktestBet]) -> float:
    return sum(bet.stake for bet in bets)


def _mean_clv_for_bets(
    bets: list[BacktestBet],
    closing_odds: ClosingOddsMap,
) -> tuple[float | None, int]:
    values = [
        value
        for value in (BacktestStabilityAnalyzer._clv_pct(bet, closing_odds) for bet in bets)
        if value is not None
    ]
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def build_walkforward_metrics(
    rows: list[WalkforwardRow],
    *,
    min_train_seasons: int,
    meta_threshold: float | None = None,
    closing_odds: ClosingOddsMap | None = None,
) -> tuple[tuple[MetaFoldMetrics, ...], SelectionMetaModel | None]:
    seasons = tuple(sorted({competition.season for _bet, _match, competition, _snapshot_type in rows}, key=_season_key))
    folds: list[MetaFoldMetrics] = []
    final_model: SelectionMetaModel | None = None
    closing_odds = closing_odds or {}

    for index, holdout_season in enumerate(seasons):
        train_seasons = seasons[:index]
        if len(train_seasons) < min_train_seasons:
            continue

        train_samples = [
            build_selection_meta_model_sample(
                bet,
                competition.name,
                odds_snapshot_type=snapshot_type,
            )
            for bet, _match, competition, snapshot_type in rows
            if competition.season in train_seasons
        ]
        holdout_rows = [
            (bet, match, competition, snapshot_type)
            for bet, match, competition, snapshot_type in rows
            if competition.season == holdout_season
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
            continue

        model = SelectionMetaModel.train(train_samples)
        scored = [
            (sample, model.predict_probability(sample), bet)
            for sample, (bet, _match, _competition, _snapshot_type) in zip(holdout_samples, holdout_rows)
        ]
        brier = sum((probability - sample.label) ** 2 for sample, probability, _bet in scored) / len(scored)

        baseline_bets = [bet for _sample, _probability, bet in scored if bet.is_bet]
        meta_bets = [
            bet
            for sample, probability, bet in scored
            if bet.is_bet and probability >= _meta_threshold(sample.selection, meta_threshold)
        ]
        baseline_pl = _profit_loss_for_bets(baseline_bets)
        meta_pl = _profit_loss_for_bets(meta_bets)
        baseline_clv, baseline_clv_count = _mean_clv_for_bets(baseline_bets, closing_odds)
        meta_clv, meta_clv_count = _mean_clv_for_bets(meta_bets, closing_odds)
        meta_wins = sum(1 for bet in meta_bets if bet.result == "won")
        folds.append(
            MetaFoldMetrics(
                season=holdout_season,
                train_seasons=train_seasons,
                samples=len(holdout_samples),
                brier=brier,
                baseline_bets=len(baseline_bets),
                baseline_roi=_roi(baseline_pl, _stake_for_bets(baseline_bets)),
                baseline_profit_loss=baseline_pl,
                baseline_clv=baseline_clv,
                baseline_clv_count=baseline_clv_count,
                meta_bets=len(meta_bets),
                meta_roi=_roi(meta_pl, _stake_for_bets(meta_bets)),
                meta_profit_loss=meta_pl,
                meta_hit_rate=(meta_wins / len(meta_bets)) if meta_bets else 0.0,
                meta_clv=meta_clv,
                meta_clv_count=meta_clv_count,
            )
        )

    all_samples = [
        build_selection_meta_model_sample(
            bet,
            competition.name,
            odds_snapshot_type=snapshot_type,
        )
        for bet, _match, competition, snapshot_type in rows
    ]
    if all_samples:
        final_model = SelectionMetaModel.train(all_samples)
    return tuple(folds), final_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, help="Run ids, e.g. 265-314")
    parser.add_argument("--min-train-seasons", type=int, default=3)
    parser.add_argument("--meta-threshold", type=float)
    parser.add_argument(
        "--thresholds",
        help="Comma-separated meta thresholds to sweep, e.g. 0.58,0.59,0.60",
    )
    parser.add_argument("--output-model")
    return parser.parse_args()


def _format_pct(value: float | None) -> str:
    return "N/A" if value is None or math.isnan(value) else f"{value:.2f}%"


def _aggregate_clv(folds: tuple[MetaFoldMetrics, ...], *, meta: bool) -> float | None:
    total = 0.0
    count = 0
    for fold in folds:
        avg = fold.meta_clv if meta else fold.baseline_clv
        clv_count = fold.meta_clv_count if meta else fold.baseline_clv_count
        if avg is None or clv_count == 0:
            continue
        total += avg * clv_count
        count += clv_count
    return (total / count) if count else None


def main() -> None:
    args = parse_args()
    run_ids = _parse_run_ids(args.runs)
    with SessionLocal() as session:
        rows = _load_rows(session, run_ids)
        closing_odds = BacktestStabilityAnalyzer(session)._load_closing_odds([
            StabilityBetRow(bet=bet, match=match, competition=competition)
            for bet, match, competition, _snapshot_type in rows
        ])

    if args.thresholds:
        print("THRESHOLD  FOLDS  META_BETS  META_ROI  META_CLV  META_PL")
        for threshold in _parse_thresholds(args.thresholds):
            folds, _final_model = build_walkforward_metrics(
                rows,
                min_train_seasons=args.min_train_seasons,
                meta_threshold=threshold,
                closing_odds=closing_odds,
            )
            meta_bets = sum(fold.meta_bets for fold in folds)
            meta_pl = sum(fold.meta_profit_loss for fold in folds)
            meta_stake = meta_bets * 10.0
            print(
                f"{threshold:<10.3f} {len(folds):<6} {meta_bets:<10} "
                f"{_format_pct(_roi(meta_pl, meta_stake)):<9} "
                f"{_format_pct(_aggregate_clv(folds, meta=True)):<9} {meta_pl:.2f}"
            )
        return

    folds, final_model = build_walkforward_metrics(
        rows,
        min_train_seasons=args.min_train_seasons,
        meta_threshold=args.meta_threshold,
        closing_odds=closing_odds,
    )
    print("SEASON        TRAIN_SEASONS  SAMPLES  BRIER   BASE_BETS  BASE_ROI  BASE_CLV  META_BETS  META_ROI  META_CLV  META_HIT")
    for fold in folds:
        print(
            f"{fold.season:<13} {len(fold.train_seasons):<13} {fold.samples:<7} "
            f"{fold.brier:.4f}  {fold.baseline_bets:<9} {_format_pct(fold.baseline_roi):<9} "
            f"{_format_pct(fold.baseline_clv):<9} {fold.meta_bets:<9} "
            f"{_format_pct(fold.meta_roi):<9} {_format_pct(fold.meta_clv):<9} {fold.meta_hit_rate:.3f}"
        )

    baseline_bets = sum(fold.baseline_bets for fold in folds)
    baseline_pl = sum(fold.baseline_profit_loss for fold in folds)
    meta_bets = sum(fold.meta_bets for fold in folds)
    meta_pl = sum(fold.meta_profit_loss for fold in folds)
    baseline_stake = baseline_bets * 10.0
    meta_stake = meta_bets * 10.0
    print("\nSUMMARY")
    print(f"folds={len(folds)}")
    print(
        f"baseline_bets={baseline_bets} baseline_roi={_format_pct(_roi(baseline_pl, baseline_stake))} "
        f"baseline_clv={_format_pct(_aggregate_clv(folds, meta=False))} baseline_pl={baseline_pl:.2f}"
    )
    print(
        f"meta_bets={meta_bets} meta_roi={_format_pct(_roi(meta_pl, meta_stake))} "
        f"meta_clv={_format_pct(_aggregate_clv(folds, meta=True))} meta_pl={meta_pl:.2f}"
    )

    if args.output_model and final_model is not None:
        final_model.save(Path(args.output_model))
        print(f"saved_model={args.output_model}")


if __name__ == "__main__":
    main()
