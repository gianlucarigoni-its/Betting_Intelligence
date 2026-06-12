"""Validate operational recommendation bands with temporal walk-forward scoring."""

from __future__ import annotations

import argparse
from collections import defaultdict

from backtesting.capital_readiness import CapitalReadinessCriteria, evaluate_slice_readiness
from backtesting.run_selection_meta_walkforward import _load_rows, _parse_run_ids, _season_key
from backtesting.selection_meta_model import SelectionMetaModel, build_selection_meta_model_sample
from backtesting.stability_report import BacktestStabilityAnalyzer, StabilityBetRow
from database.base import SessionLocal
from models.value_metrics import ValueMetricsResult
from recommendation.profile_engine import ConfidenceLevel, RecommendationEngine, RecommendationInput


def confidence_from_probability(probability: float) -> ConfidenceLevel:
    if probability >= 0.62:
        return ConfidenceLevel.HIGH
    if probability >= 0.54:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--min-train-seasons", type=int, default=3)
    parser.add_argument("--min-bets", type=int, default=100)
    parser.add_argument("--min-clv-count", type=int, default=100)
    parser.add_argument("--target", choices=("win", "clv_positive"), default="clv_positive")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_ids = _parse_run_ids(args.runs)
    engine = RecommendationEngine()
    with SessionLocal() as session:
        rows = _load_rows(session, run_ids)
        stability_rows = [
            StabilityBetRow(bet=bet, match=match, competition=competition)
            for bet, match, competition, _snapshot_type in rows
        ]
        closing_odds = BacktestStabilityAnalyzer(session)._load_closing_odds(stability_rows)

    seasons = sorted({competition.season for _bet, _match, competition, _snapshot in rows}, key=_season_key)
    by_band: dict[str, list[StabilityBetRow]] = defaultdict(list)
    for index, holdout_season in enumerate(seasons):
        train_seasons = seasons[:index]
        if len(train_seasons) < args.min_train_seasons:
            continue
        train_samples = []
        for bet, _match, competition, snapshot in rows:
            if competition.season not in train_seasons:
                continue
            label_override = None
            if args.target == "clv_positive":
                closing = closing_odds.get((bet.match_id, bet.market_type, bet.selection, bet.bookmaker_id))
                if closing is None or closing.odd_value <= 0:
                    continue
                label_override = int(bet.bookmaker_odds > closing.odd_value)
            train_samples.append(build_selection_meta_model_sample(
                bet, competition.name, odds_snapshot_type=snapshot, label_override=label_override
            ))
        if not train_samples or len({sample.label for sample in train_samples}) < 2:
            continue
        model = SelectionMetaModel.train(train_samples)
        for bet, match, competition, snapshot in rows:
            if competition.season != holdout_season or not bet.is_bet:
                continue
            sample = build_selection_meta_model_sample(bet, competition.name, odds_snapshot_type=snapshot)
            reliability = model.predict_probability(sample)
            closing = closing_odds.get((bet.match_id, bet.market_type, bet.selection, bet.bookmaker_id))
            closing_edge = None
            if closing is not None and closing.odd_value > 1.0:
                closing_edge = (bet.model_probability - (1.0 / closing.odd_value)) * 100.0
            metrics = ValueMetricsResult(
                model_probability=bet.model_probability,
                bookmaker_probability=bet.bookmaker_probability,
                bookmaker_odds=bet.bookmaker_odds,
                edge_pct=bet.edge_pct,
                ev=bet.expected_value or 0.0,
                kelly_fraction=0.0,
                quarter_kelly_fraction=0.0,
            )
            result = engine.classify(RecommendationInput(
                value_metrics=metrics,
                confidence_level=confidence_from_probability(reliability),
                selection=bet.selection,
                market_type=bet.market_type,
                opening_edge_pct=bet.edge_pct if snapshot == "opening" else None,
                closing_edge_pct=closing_edge,
                market_dislocation_pct=abs(bet.model_probability - bet.bookmaker_probability) * 100.0,
            ))
            by_band[result.band.value].append(StabilityBetRow(bet=bet, match=match, competition=competition))

    criteria = CapitalReadinessCriteria(min_bets=args.min_bets, min_clv_count=args.min_clv_count)
    print("BAND             STATUS  BETS  ROI       ROI_CI_LOW  CLV       CLV_CI_LOW")
    passed_bands: list[str] = []
    for band in sorted(by_band):
        metrics = BacktestStabilityAnalyzer._metrics_for(band, by_band[band], closing_odds)
        readiness = evaluate_slice_readiness(metrics, criteria)
        status = "PASS" if readiness.passed else "FAIL"
        if readiness.passed:
            passed_bands.append(band)
        print(
            f"{band:<16} {status:<7} {metrics.bets:<5} "
            f"{(metrics.roi_pct or 0.0):>8.2f}% {(metrics.roi_ci_low_pct or 0.0):>11.2f}% "
            f"{(metrics.avg_clv_pct or 0.0):>8.2f}% {(metrics.clv_ci_low_pct or 0.0):>11.2f}%"
        )
    print(f"PROMOTED_BANDS={','.join(passed_bands) if passed_bands else 'NONE'}")
    print(f"CAPITAL_READY={'YES' if passed_bands else 'NO'}")


if __name__ == "__main__":
    main()
