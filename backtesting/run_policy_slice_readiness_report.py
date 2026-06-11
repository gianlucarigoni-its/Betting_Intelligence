"""Evaluate a specific policy slice against capital-readiness criteria."""

from __future__ import annotations

import argparse
from dataclasses import replace

from backtesting.capital_readiness import CapitalReadinessCriteria, evaluate_capital_readiness
from backtesting.run_stability_report import _parse_run_ids
from backtesting.stability_report import BacktestStabilityAnalyzer, StabilityBetRow, StabilitySliceMetrics
from database.base import SessionLocal
from database.models import BacktestBet, Competition, HistoricalOddSnapshot, Match


def _format_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, help="Run ids, e.g. 465-489")
    parser.add_argument("--league")
    parser.add_argument("--selection")
    parser.add_argument("--market-type", default="OU_2_5")
    parser.add_argument("--snapshot-type", choices=("opening", "closing"), default="opening")
    parser.add_argument("--edge-min", type=float)
    parser.add_argument("--edge-max", type=float)
    parser.add_argument("--min-model-probability", type=float)
    parser.add_argument("--max-bookmaker-odds", type=float)
    parser.add_argument("--min-bets", type=int, default=100)
    parser.add_argument("--min-clv-count", type=int, default=100)
    parser.add_argument("--min-roi-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--min-clv-ci-low-pct", type=float, default=0.0)
    parser.add_argument("--max-drawdown-pct-of-stake", type=float, default=20.0)
    parser.add_argument("--ignore-clv", action="store_true")
    parser.add_argument("--min-season-bets", type=int, default=20)
    parser.add_argument("--min-season-roi-pct", type=float, default=0.0)
    parser.add_argument("--require-all-profitable-seasons", action="store_true")
    return parser.parse_args()


def _build_metrics(
    bets: list[BacktestBet],
    closing_odds: dict[tuple[int, str, str, int | None], HistoricalOddSnapshot],
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
        label="SLICE",
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


def main() -> None:
    args = parse_args()
    run_ids = _parse_run_ids(args.runs)
    with SessionLocal() as session:
        rows = (
            session.query(BacktestBet, Competition, Match)
            .join(Match, BacktestBet.match_id == Match.id)
            .join(Competition, Match.competition_id == Competition.id)
            .filter(
                BacktestBet.backtest_run_id.in_(run_ids),
                BacktestBet.result != "pending",
                BacktestBet.market_type == args.market_type,
                BacktestBet.is_bet.is_(True),
            )
            .all()
        )
        stability_rows = [
            StabilityBetRow(bet=bet, match=match, competition=competition)
            for bet, competition, match in rows
        ]
        if args.league:
            stability_rows = [row for row in stability_rows if row.competition.name == args.league]
        if args.selection:
            stability_rows = [row for row in stability_rows if row.bet.selection == args.selection]
        if args.edge_min is not None:
            stability_rows = [row for row in stability_rows if row.bet.edge_pct >= args.edge_min]
        if args.edge_max is not None:
            stability_rows = [row for row in stability_rows if row.bet.edge_pct < args.edge_max]
        if args.min_model_probability is not None:
            stability_rows = [row for row in stability_rows if row.bet.model_probability >= args.min_model_probability]
        if args.max_bookmaker_odds is not None:
            stability_rows = [row for row in stability_rows if row.bet.bookmaker_odds <= args.max_bookmaker_odds]

        closing_odds = {}
        if args.snapshot_type == "opening" and stability_rows:
            closing_odds = BacktestStabilityAnalyzer(session)._load_closing_odds(stability_rows)

        metrics = _build_metrics([row.bet for row in stability_rows], closing_odds)
        season_metrics = [
            replace(
                _build_metrics([row.bet for row in stability_rows if row.competition.season == season], closing_odds),
                label=season,
            )
            for season in sorted({row.competition.season for row in stability_rows})
        ]
        season_metrics = [metric for metric in season_metrics if metric.bets >= args.min_season_bets]
        criteria = CapitalReadinessCriteria(
            min_bets=args.min_bets,
            min_clv_count=0 if args.ignore_clv else args.min_clv_count,
            min_roi_ci_low_pct=args.min_roi_ci_low_pct,
            min_clv_ci_low_pct=-999.0 if args.ignore_clv else args.min_clv_ci_low_pct,
            max_drawdown_pct_of_stake=args.max_drawdown_pct_of_stake,
        )
        readiness_metrics = metrics
        if args.ignore_clv:
            readiness_metrics = replace(
                metrics,
                avg_clv_pct=-999.0,
                clv_count=0,
                clv_ci_low_pct=-999.0,
                clv_ci_high_pct=-999.0,
            )
        readiness = evaluate_capital_readiness(readiness_metrics, criteria)
        failures = list(readiness.failures)
        if args.require_all_profitable_seasons:
            for metric in season_metrics:
                if metric.roi_pct is None or metric.roi_pct < args.min_season_roi_pct:
                    failures.append(
                        f"season {metric.label} roi {_format_pct(metric.roi_pct)} < "
                        f"min_season_roi {_format_pct(args.min_season_roi_pct)}"
                    )
        passed = not failures

    print(f"CAPITAL_READINESS={'PASS' if passed else 'FAIL'}")
    print(f"bets={metrics.bets} clv_count={metrics.clv_count}")
    print(f"roi={_format_pct(metrics.roi_pct)} roi_ci=[{_format_pct(metrics.roi_ci_low_pct)}, {_format_pct(metrics.roi_ci_high_pct)}]")
    if metrics.avg_clv_pct is not None:
        print(f"clv={_format_pct(metrics.avg_clv_pct)} clv_ci=[{_format_pct(metrics.clv_ci_low_pct)}, {_format_pct(metrics.clv_ci_high_pct)}]")
    print(f"drawdown_pct_of_stake={_format_pct((metrics.max_drawdown / metrics.total_staked) * 100.0 if metrics.total_staked else None)}")
    if season_metrics:
        print("BY_SEASON")
        for metric in season_metrics:
            print(
                f"- {metric.label}: bets={metric.bets} hit={metric.hit_rate:.3f} "
                f"roi={_format_pct(metric.roi_pct)} roi_ci=[{_format_pct(metric.roi_ci_low_pct)}, {_format_pct(metric.roi_ci_high_pct)}] "
                f"dd={metric.max_drawdown:.2f}"
            )
    if failures:
        print("FAILURES")
        for failure in failures:
            print(f"- {failure}")


if __name__ == "__main__":
    main()
