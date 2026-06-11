"""Walk-forward validation for the selection meta-model."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from backtesting.selection_meta_model import (
    SelectionMetaModel,
    build_selection_meta_model_sample,
)
from database.base import SessionLocal
from database.models import BacktestBet, Competition, Match


@dataclass(frozen=True, slots=True)
class MetaFoldMetrics:
    season: str
    train_seasons: tuple[str, ...]
    samples: int
    brier: float
    baseline_bets: int
    baseline_roi: float | None
    baseline_profit_loss: float
    meta_bets: int
    meta_roi: float | None
    meta_profit_loss: float
    meta_hit_rate: float


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


def _season_key(season: str) -> int:
    return int(season.split("/")[0])


def _meta_threshold(selection: str) -> float:
    if selection == "DRAW":
        return 0.52
    if selection == "AWAY":
        return 0.58
    return 0.55


def _roi(profit_loss: float, stake: float) -> float | None:
    return (profit_loss / stake) * 100.0 if stake > 0 else None


def _load_rows(session, run_ids: list[int]) -> list[tuple[BacktestBet, Competition]]:
    rows = (
        session.query(BacktestBet, Competition)
        .join(Match, BacktestBet.match_id == Match.id)
        .join(Competition, Match.competition_id == Competition.id)
        .filter(
            BacktestBet.backtest_run_id.in_(run_ids),
            BacktestBet.result != "pending",
        )
        .all()
    )
    return [(bet, competition) for bet, competition in rows]


def _profit_loss_for_bets(bets: list[BacktestBet]) -> float:
    return sum(bet.profit_loss or 0.0 for bet in bets)


def _stake_for_bets(bets: list[BacktestBet]) -> float:
    return sum(bet.stake for bet in bets)


def build_walkforward_metrics(
    rows: list[tuple[BacktestBet, Competition]],
    *,
    min_train_seasons: int,
) -> tuple[MetaFoldMetrics, SelectionMetaModel | None]:
    seasons = tuple(sorted({competition.season for _, competition in rows}, key=_season_key))
    folds: list[MetaFoldMetrics] = []
    final_model: SelectionMetaModel | None = None

    for index, holdout_season in enumerate(seasons):
        train_seasons = seasons[:index]
        if len(train_seasons) < min_train_seasons:
            continue

        train_samples = [
            build_selection_meta_model_sample(bet, competition.name)
            for bet, competition in rows
            if competition.season in train_seasons
        ]
        holdout_rows = [(bet, competition) for bet, competition in rows if competition.season == holdout_season]
        holdout_samples = [build_selection_meta_model_sample(bet, competition.name) for bet, competition in holdout_rows]
        if not train_samples or not holdout_samples:
            continue

        model = SelectionMetaModel.train(train_samples)
        scored = [(sample, model.predict_probability(sample), bet) for sample, (bet, _competition) in zip(holdout_samples, holdout_rows)]
        brier = sum((probability - sample.label) ** 2 for sample, probability, _bet in scored) / len(scored)

        baseline_bets = [bet for _sample, _probability, bet in scored if bet.is_bet]
        meta_bets = [
            bet
            for sample, probability, bet in scored
            if bet.is_bet and probability >= _meta_threshold(sample.selection)
        ]
        baseline_pl = _profit_loss_for_bets(baseline_bets)
        meta_pl = _profit_loss_for_bets(meta_bets)
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
                meta_bets=len(meta_bets),
                meta_roi=_roi(meta_pl, _stake_for_bets(meta_bets)),
                meta_profit_loss=meta_pl,
                meta_hit_rate=(meta_wins / len(meta_bets)) if meta_bets else 0.0,
            )
        )

    all_samples = [build_selection_meta_model_sample(bet, competition.name) for bet, competition in rows]
    if all_samples:
        final_model = SelectionMetaModel.train(all_samples)
    return tuple(folds), final_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, help="Run ids, e.g. 265-314")
    parser.add_argument("--min-train-seasons", type=int, default=3)
    parser.add_argument("--output-model")
    return parser.parse_args()


def _format_roi(value: float | None) -> str:
    return "N/A" if value is None or math.isnan(value) else f"{value:.2f}%"


def main() -> None:
    args = parse_args()
    run_ids = _parse_run_ids(args.runs)
    with SessionLocal() as session:
        rows = _load_rows(session, run_ids)

    folds, final_model = build_walkforward_metrics(rows, min_train_seasons=args.min_train_seasons)
    print("SEASON        TRAIN_SEASONS  SAMPLES  BRIER   BASE_BETS  BASE_ROI  META_BETS  META_ROI  META_HIT")
    for fold in folds:
        print(
            f"{fold.season:<13} {len(fold.train_seasons):<13} {fold.samples:<7} "
            f"{fold.brier:.4f}  {fold.baseline_bets:<9} {_format_roi(fold.baseline_roi):<9} "
            f"{fold.meta_bets:<9} {_format_roi(fold.meta_roi):<9} {fold.meta_hit_rate:.3f}"
        )

    baseline_bets = sum(fold.baseline_bets for fold in folds)
    baseline_pl = sum(fold.baseline_profit_loss for fold in folds)
    meta_bets = sum(fold.meta_bets for fold in folds)
    meta_pl = sum(fold.meta_profit_loss for fold in folds)
    baseline_stake = baseline_bets * 10.0
    meta_stake = meta_bets * 10.0
    print("\nSUMMARY")
    print(f"folds={len(folds)}")
    print(f"baseline_bets={baseline_bets} baseline_roi={_format_roi(_roi(baseline_pl, baseline_stake))} baseline_pl={baseline_pl:.2f}")
    print(f"meta_bets={meta_bets} meta_roi={_format_roi(_roi(meta_pl, meta_stake))} meta_pl={meta_pl:.2f}")

    if args.output_model and final_model is not None:
        final_model.save(Path(args.output_model))
        print(f"saved_model={args.output_model}")


if __name__ == "__main__":
    main()
