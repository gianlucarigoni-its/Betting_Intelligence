"""Import Football-Data history and run a first historical Poisson backtest."""

from __future__ import annotations

import argparse
import logging

from backtesting.historical_poisson_backtester import (
    HistoricalPoissonBacktestConfig,
    HistoricalPoissonBacktester,
)
from database.base import SessionLocal
from database.models import Competition
from historical.football_data_importer import FootballDataImportConfig, FootballDataImporter


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season-code", default="2324")
    parser.add_argument("--season-label", default="2023/2024")
    parser.add_argument("--division-code", default="E0")
    parser.add_argument("--competition-name", default="English Premier League")
    parser.add_argument("--country", default="England")
    parser.add_argument("--test-start-date", default="2023-08-01")
    parser.add_argument("--test-end-date", default="2024-06-30")
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--flat-stake", type=float, default=10.0)
    parser.add_argument("--min-edge-pct", type=float, default=3.0)
    parser.add_argument("--max-edge-pct", type=float, default=12.0)
    parser.add_argument("--min-model-probability", type=float, default=0.55)
    parser.add_argument("--max-bookmaker-odds", type=float, default=2.0)
    parser.add_argument("--min-prior-matches", type=int, default=5)
    parser.add_argument("--shrinkage-matches", type=int, default=10)
    parser.add_argument("--elo-initial-rating", type=float, default=1500.0)
    parser.add_argument("--elo-k-factor", type=float, default=24.0)
    parser.add_argument("--elo-home-advantage", type=float, default=65.0)
    parser.add_argument("--elo-season-regression", type=float, default=0.15)
    parser.add_argument("--elo-lambda-weight", type=float, default=0.0)
    parser.add_argument("--selection-meta-model-path")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    session = SessionLocal()
    try:
        importer = FootballDataImporter(session)
        import_result = importer.import_from_url(
            FootballDataImportConfig(
                season_code=args.season_code,
                division_code=args.division_code,
                competition_name=args.competition_name,
                country=args.country,
                season_label=args.season_label,
            )
        )
        LOGGER.info("Import result: %s", import_result)

        competition = (
            session.query(Competition)
            .filter(
                Competition.name == args.competition_name,
                Competition.season == args.season_label,
            )
            .one()
        )
        backtester = HistoricalPoissonBacktester(session)
        run = backtester.run(
            HistoricalPoissonBacktestConfig(
                competition_id=competition.id,
                name=f"{args.competition_name} {args.season_label} rolling Poisson",
                test_start_date=args.test_start_date,
                test_end_date=args.test_end_date,
                initial_bankroll=args.initial_bankroll,
                flat_stake=args.flat_stake,
                min_edge_pct=args.min_edge_pct,
                max_edge_pct=args.max_edge_pct,
                min_model_probability=args.min_model_probability,
                max_bookmaker_odds=args.max_bookmaker_odds,
                min_prior_matches=args.min_prior_matches,
                shrinkage_matches=args.shrinkage_matches,
                elo_initial_rating=args.elo_initial_rating,
                elo_k_factor=args.elo_k_factor,
                elo_home_advantage=args.elo_home_advantage,
                elo_season_regression=args.elo_season_regression,
                elo_lambda_weight=args.elo_lambda_weight,
                selection_meta_model_path=args.selection_meta_model_path,
            )
        )
        print(
            "Backtest completed: "
            f"run_id={run.id}, bets={run.total_bets}, "
            f"profit_loss={run.profit_loss:.2f}, roi_pct={run.roi_pct}, "
            f"final_bankroll={run.final_bankroll:.2f}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
