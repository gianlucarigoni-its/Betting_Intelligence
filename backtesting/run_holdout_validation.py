"""Out-of-sample validation for a tuned backtest configuration.

Use this after selecting parameters on older seasons, then validate them on
one or more held-out seasons to avoid reading tuning noise as signal.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

from backtesting.calibration_report import CalibrationReportBuilder
from backtesting.historical_poisson_backtester import (
    HistoricalPoissonBacktestConfig,
    HistoricalPoissonBacktester,
)
from database.base import SessionLocal
from database.models import Competition
from historical.batch_importer import LEAGUE_CATALOG, LeagueConfig

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationDefaults:
    initial_bankroll: float = 1000.0
    flat_stake: float = 10.0
    min_edge_pct: float = 5.0
    max_edge_pct: float = 6.0
    min_model_probability: float = 0.55
    max_bookmaker_odds: float = 1.8
    away_min_edge_pct: float = 99.0
    away_min_model_probability: float = 0.58
    away_max_bookmaker_odds: float = 1.8
    allow_away_bets: bool = False
    min_prior_matches: int = 5
    shrinkage_matches: int = 10
    recent_form_half_life_matches: float = 0.0
    home_lambda_multiplier: float = 1.0
    away_lambda_multiplier: float = 1.0


def _filter_catalog(
    league_codes: list[str] | None,
    season_codes: list[str],
) -> list[LeagueConfig]:
    result: list[LeagueConfig] = []
    for league in LEAGUE_CATALOG:
        if league_codes and league.code not in league_codes:
            continue
        seasons = tuple(s for s in league.seasons if s in season_codes)
        if seasons:
            from dataclasses import replace
            result.append(replace(league, seasons=seasons))
    return result


def _season_label(season_code: str) -> str:
    return f"20{season_code[:2]}/20{season_code[2:]}"


def _season_dates(season_code: str) -> tuple[str, str]:
    start_year = 2000 + int(season_code[:2])
    end_year = 2000 + int(season_code[2:])
    return f"{start_year}-08-01", f"{end_year}-06-30"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--leagues",
        help="Codici lega separati da virgola (es. E0,SP1). Default: tutte.",
    )
    parser.add_argument(
        "--holdout-seasons",
        required=True,
        help="Codici stagione separati da virgola da validare out-of-sample.",
    )
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--flat-stake", type=float, default=10.0)
    parser.add_argument("--min-edge-pct", type=float, default=5.0)
    parser.add_argument("--max-edge-pct", type=float, default=6.0)
    parser.add_argument("--min-model-probability", type=float, default=0.55)
    parser.add_argument("--max-bookmaker-odds", type=float, default=1.8)
    parser.add_argument("--away-min-edge-pct", type=float, default=99.0)
    parser.add_argument("--away-min-model-probability", type=float, default=0.58)
    parser.add_argument("--away-max-bookmaker-odds", type=float, default=1.8)
    parser.add_argument(
        "--allow-away-bets",
        action="store_true",
        help="Abilita la selezione AWAY anche in holdout.",
    )
    parser.add_argument("--min-prior-matches", type=int, default=5)
    parser.add_argument("--shrinkage-matches", type=int, default=10)
    parser.add_argument(
        "--recent-form-half-life-matches",
        type=float,
        default=0.0,
    )
    parser.add_argument("--home-lambda-multiplier", type=float, default=1.0)
    parser.add_argument("--away-lambda-multiplier", type=float, default=1.0)
    return parser.parse_args()


def _phase_backtest(
    leagues: list[LeagueConfig],
    defaults: ValidationDefaults,
) -> list[int]:
    run_ids: list[int] = []
    for league in leagues:
        for season_code in league.seasons:
            season_label = _season_label(season_code)
            test_start, test_end = _season_dates(season_code)

            with SessionLocal() as session:
                competition = (
                    session.query(Competition)
                    .filter(
                        Competition.name == league.label,
                        Competition.season == season_label,
                    )
                    .first()
                )
                if competition is None:
                    LOGGER.warning(
                        "Competition non trovata: %s %s — skip",
                        league.label, season_label,
                    )
                    continue

                LOGGER.info(
                    "Holdout: %s %s (competition_id=%d)",
                    league.label, season_label, competition.id,
                )

                backtester = HistoricalPoissonBacktester(session)
                run = backtester.run(
                    HistoricalPoissonBacktestConfig(
                        competition_id=competition.id,
                        name=f"{league.label} {season_label} holdout-validation",
                        test_start_date=test_start,
                        test_end_date=test_end,
                        initial_bankroll=defaults.initial_bankroll,
                        flat_stake=defaults.flat_stake,
                        min_edge_pct=defaults.min_edge_pct,
                        max_edge_pct=defaults.max_edge_pct,
                        min_model_probability=defaults.min_model_probability,
                        max_bookmaker_odds=defaults.max_bookmaker_odds,
                        away_min_edge_pct=defaults.away_min_edge_pct,
                        away_min_model_probability=defaults.away_min_model_probability,
                        away_max_bookmaker_odds=defaults.away_max_bookmaker_odds,
                        allow_away_bets=defaults.allow_away_bets,
                        min_prior_matches=defaults.min_prior_matches,
                        shrinkage_matches=defaults.shrinkage_matches,
                        recent_form_half_life_matches=(
                            defaults.recent_form_half_life_matches
                        ),
                        home_lambda_multiplier=defaults.home_lambda_multiplier,
                        away_lambda_multiplier=defaults.away_lambda_multiplier,
                    )
                )
                LOGGER.info(
                    "  run_id=%d | bets=%d | P&L=%.2f | ROI=%s%%",
                    run.id,
                    run.total_bets,
                    run.profit_loss,
                    f"{run.roi_pct:.1f}" if run.roi_pct is not None else "N/A",
                )
                run_ids.append(run.id)

    LOGGER.info("Holdout completati: %d run creati", len(run_ids))
    return run_ids


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    args = _parse_args()
    league_codes = [c.strip() for c in args.leagues.split(",")] if args.leagues else None
    season_codes = [s.strip() for s in args.holdout_seasons.split(",")]
    leagues = _filter_catalog(league_codes, season_codes)

    if not leagues:
        LOGGER.error(
            "Nessuna lega/stagione trovata con i filtri: leagues=%s seasons=%s",
            league_codes,
            season_codes,
        )
        sys.exit(1)

    defaults = ValidationDefaults(
        initial_bankroll=args.initial_bankroll,
        flat_stake=args.flat_stake,
        min_edge_pct=args.min_edge_pct,
        max_edge_pct=args.max_edge_pct,
        min_model_probability=args.min_model_probability,
        max_bookmaker_odds=args.max_bookmaker_odds,
        away_min_edge_pct=args.away_min_edge_pct,
        away_min_model_probability=args.away_min_model_probability,
        away_max_bookmaker_odds=args.away_max_bookmaker_odds,
        allow_away_bets=args.allow_away_bets,
        min_prior_matches=args.min_prior_matches,
        shrinkage_matches=args.shrinkage_matches,
        recent_form_half_life_matches=args.recent_form_half_life_matches,
        home_lambda_multiplier=args.home_lambda_multiplier,
        away_lambda_multiplier=args.away_lambda_multiplier,
    )

    run_ids = _phase_backtest(leagues, defaults)

    with SessionLocal() as session:
        report = CalibrationReportBuilder(session).build(run_ids=run_ids)
        report.print_summary()


if __name__ == "__main__":
    main()
