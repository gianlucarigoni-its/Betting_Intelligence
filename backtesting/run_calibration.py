# backtesting/run_calibration.py
"""
Pipeline completo: import → backtest → calibration report.

Uso tipico (tutto il catalogo, ultime 5 stagioni):
    python -m backtesting.run_calibration

Solo Premier League, due stagioni, senza re-importare:
    python -m backtesting.run_calibration \
        --leagues E0 \
        --seasons 2324,2223 \
        --skip-import

Solo calibration su run già esistenti:
    python -m backtesting.run_calibration \
        --skip-import --skip-backtest
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

from backtesting.calibration_report import CalibrationReportBuilder
from backtesting.league_policy import LeagueBettingPolicy, LeaguePolicyStore
from backtesting.historical_poisson_backtester import (
    HistoricalPoissonBacktestConfig,
    HistoricalPoissonBacktester,
)
from database.base import SessionLocal
from database.models import Competition
from historical.batch_importer import (
    LEAGUE_CATALOG,
    BatchImportSummary,
    LeagueConfig,
    run_batch_import,
)

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configurazione backtest — valori di default condivisi
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BacktestDefaults:
    initial_bankroll: float = 1000.0
    flat_stake: float = 10.0
    allow_home_bets: bool = True
    allow_draw_bets: bool = False
    min_edge_pct: float = 5.0
    max_edge_pct: float = 6.0
    min_model_probability: float = 0.55
    max_bookmaker_odds: float = 1.8
    home_min_form_goal_diff_delta: float | None = None
    draw_min_edge_pct: float = 4.0
    draw_max_edge_pct: float | None = 9.0
    draw_min_model_probability: float = 0.24
    draw_max_bookmaker_odds: float = 4.2
    draw_max_lambda_gap: float | None = 0.25
    draw_max_abs_form_goal_diff_delta: float | None = 0.35
    away_min_edge_pct: float = 99.0
    away_min_model_probability: float = 0.58
    away_max_bookmaker_odds: float = 1.8
    allow_away_bets: bool = False
    min_prior_matches: int = 5
    shrinkage_matches: int = 10
    recent_form_half_life_matches: float = 0.0
    home_lambda_multiplier: float = 1.0
    away_lambda_multiplier: float = 1.0
    elo_initial_rating: float = 1500.0
    elo_k_factor: float = 24.0
    elo_home_advantage: float = 65.0
    elo_season_regression: float = 0.15
    elo_lambda_weight: float = 0.0


# ---------------------------------------------------------------------------
# Funzioni pure di supporto
# ---------------------------------------------------------------------------

def _season_dates(season_code: str) -> tuple[str, str]:
    """
    Ricava le date di inizio/fine stagione dal codice.

    Examples:
        >>> _season_dates("2324")
        ('2023-08-01', '2024-06-30')
        >>> _season_dates("1920")
        ('2019-08-01', '2020-06-30')
    """
    start_year = 2000 + int(season_code[:2])
    end_year = 2000 + int(season_code[2:])
    return f"{start_year}-08-01", f"{end_year}-06-30"


def _filter_catalog(
    league_codes: list[str] | None,
    season_codes: list[str] | None,
) -> list[LeagueConfig]:
    """
    Filtra il LEAGUE_CATALOG in base ai codici specificati da CLI.
    Se i filtri sono None restituisce il catalogo completo.
    """
    result = []
    for league in LEAGUE_CATALOG:
        if league_codes and league.code not in league_codes:
            continue
        seasons = (
            tuple(s for s in league.seasons if s in season_codes)
            if season_codes
            else league.seasons
        )
        if seasons:
            from dataclasses import replace
            result.append(replace(league, seasons=seasons))
    return result


# ---------------------------------------------------------------------------
# Fasi del pipeline
# ---------------------------------------------------------------------------

def _phase_import(leagues: list[LeagueConfig]) -> BatchImportSummary:
    """Fase 1: scarica e importa i CSV da football-data.co.uk."""
    LOGGER.info("=== FASE 1: IMPORT ===")
    summary = run_batch_import(leagues=leagues)
    summary.print_report()
    return summary


def _phase_backtest(
    leagues: list[LeagueConfig],
    defaults: BacktestDefaults,
    policy_store: LeaguePolicyStore | None = None,
) -> list[int]:
    """
    Fase 2: esegue un backtest per ogni (lega, stagione) trovata nel DB.

    Returns:
        Lista di run_id creati in questa sessione.
    """
    LOGGER.info("=== FASE 2: BACKTEST ===")
    run_ids: list[int] = []
    policy_map = policy_store.load() if policy_store else {}

    for league in leagues:
        for season_code in league.seasons:
            season_label = f"20{season_code[:2]}/20{season_code[2:]}"
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
                    "Backtest: %s %s (competition_id=%d)",
                    league.label, season_label, competition.id,
                )

                league_policy = policy_map.get(league.label)
                effective = league_policy or LeagueBettingPolicy(
                    allow_home_bets=defaults.allow_home_bets,
                    allow_draw_bets=defaults.allow_draw_bets,
                    min_edge_pct=defaults.min_edge_pct,
                    max_edge_pct=defaults.max_edge_pct,
                    min_model_probability=defaults.min_model_probability,
                    max_bookmaker_odds=defaults.max_bookmaker_odds,
                    home_min_form_goal_diff_delta=(
                        defaults.home_min_form_goal_diff_delta
                    ),
                    draw_min_edge_pct=defaults.draw_min_edge_pct,
                    draw_max_edge_pct=defaults.draw_max_edge_pct,
                    draw_min_model_probability=defaults.draw_min_model_probability,
                    draw_max_bookmaker_odds=defaults.draw_max_bookmaker_odds,
                    draw_max_lambda_gap=defaults.draw_max_lambda_gap,
                    draw_max_abs_form_goal_diff_delta=(
                        defaults.draw_max_abs_form_goal_diff_delta
                    ),
                    away_min_edge_pct=defaults.away_min_edge_pct,
                    away_min_model_probability=defaults.away_min_model_probability,
                    away_max_bookmaker_odds=defaults.away_max_bookmaker_odds,
                    allow_away_bets=defaults.allow_away_bets,
                    min_prior_matches=defaults.min_prior_matches,
                    shrinkage_matches=defaults.shrinkage_matches,
                    recent_form_half_life_matches=defaults.recent_form_half_life_matches,
                    home_lambda_multiplier=defaults.home_lambda_multiplier,
                    away_lambda_multiplier=defaults.away_lambda_multiplier,
                    elo_initial_rating=defaults.elo_initial_rating,
                    elo_k_factor=defaults.elo_k_factor,
                    elo_home_advantage=defaults.elo_home_advantage,
                    elo_season_regression=defaults.elo_season_regression,
                    elo_lambda_weight=defaults.elo_lambda_weight,
                )

                try:
                    backtester = HistoricalPoissonBacktester(session)
                    run = backtester.run(
                        HistoricalPoissonBacktestConfig(
                            competition_id=competition.id,
                            name=(
                                f"{league.label} {season_label} "
                                f"rolling-poisson"
                            ),
                            test_start_date=test_start,
                            test_end_date=test_end,
                            initial_bankroll=defaults.initial_bankroll,
                            flat_stake=defaults.flat_stake,
                            allow_home_bets=effective.allow_home_bets,
                            allow_draw_bets=effective.allow_draw_bets,
                            min_edge_pct=effective.min_edge_pct,
                            max_edge_pct=effective.max_edge_pct,
                            min_model_probability=effective.min_model_probability,
                            max_bookmaker_odds=effective.max_bookmaker_odds,
                            home_min_form_goal_diff_delta=(
                                effective.home_min_form_goal_diff_delta
                            ),
                            draw_min_edge_pct=effective.draw_min_edge_pct,
                            draw_max_edge_pct=effective.draw_max_edge_pct,
                            draw_min_model_probability=(
                                effective.draw_min_model_probability
                            ),
                            draw_max_bookmaker_odds=effective.draw_max_bookmaker_odds,
                            draw_max_lambda_gap=effective.draw_max_lambda_gap,
                            draw_max_abs_form_goal_diff_delta=(
                                effective.draw_max_abs_form_goal_diff_delta
                            ),
                            away_min_edge_pct=effective.away_min_edge_pct,
                            away_min_model_probability=effective.away_min_model_probability,
                            away_max_bookmaker_odds=effective.away_max_bookmaker_odds,
                            allow_away_bets=effective.allow_away_bets,
                            min_prior_matches=effective.min_prior_matches,
                            shrinkage_matches=effective.shrinkage_matches,
                            recent_form_half_life_matches=effective.recent_form_half_life_matches,
                            home_lambda_multiplier=effective.home_lambda_multiplier,
                            away_lambda_multiplier=effective.away_lambda_multiplier,
                            elo_initial_rating=effective.elo_initial_rating,
                            elo_k_factor=effective.elo_k_factor,
                            elo_home_advantage=effective.elo_home_advantage,
                            elo_season_regression=effective.elo_season_regression,
                            elo_lambda_weight=effective.elo_lambda_weight,
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

                except Exception as exc:
                    LOGGER.error(
                        "Backtest fallito per %s %s: %s",
                        league.label, season_label, exc,
                        exc_info=True,
                    )

    LOGGER.info("Backtest completati: %d run creati", len(run_ids))
    return run_ids


def _phase_calibration(run_ids: list[int] | None) -> None:
    """Fase 3: costruisce e stampa il calibration report."""
    LOGGER.info("=== FASE 3: CALIBRATION REPORT ===")
    with SessionLocal() as session:
        builder = CalibrationReportBuilder(session)
        try:
            report = builder.build(run_ids=run_ids or None)
            report.print_summary()
        except ValueError as exc:
            LOGGER.error("Calibration fallita: %s", exc)
            sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Selezione dati
    parser.add_argument(
        "--leagues",
        help="Codici lega separati da virgola (es. E0,SP1). Default: tutte.",
    )
    parser.add_argument(
        "--seasons",
        help="Codici stagione separati da virgola (es. 2324,2223). Default: tutte.",
    )

    # Controllo fasi
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Salta la fase di import (usa i dati già nel DB).",
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Salta la fase di backtest (calibra sui run già nel DB).",
    )
    parser.add_argument(
        "--policy-file",
        help="JSON con policy di betting per lega, generato dal tuning walk-forward.",
    )

    # Parametri backtest
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--flat-stake", type=float, default=10.0)
    parser.add_argument("--min-edge-pct", type=float, default=5.0)
    parser.add_argument("--max-edge-pct", type=float, default=6.0)
    parser.add_argument(
        "--min-model-probability", type=float, default=0.55,
    )
    parser.add_argument("--max-bookmaker-odds", type=float, default=1.8)
    parser.add_argument("--away-min-edge-pct", type=float, default=99.0)
    parser.add_argument("--away-min-model-probability", type=float, default=0.58)
    parser.add_argument("--away-max-bookmaker-odds", type=float, default=1.8)
    parser.add_argument(
        "--allow-away-bets",
        action="store_true",
        help="Abilita la selezione AWAY oltre ai filtri globali.",
    )
    parser.add_argument("--min-prior-matches", type=int, default=5)
    parser.add_argument("--shrinkage-matches", type=int, default=10)
    parser.add_argument(
        "--recent-form-half-life-matches",
        type=float,
        default=0.0,
        help=(
            "Half-life in numero di partite per pesare la forma recente. "
            "0.0 disattiva il peso temporale e usa la media semplice."
        ),
    )
    parser.add_argument(
        "--home-lambda-multiplier",
        type=float,
        default=1.0,
        help="Moltiplicatore sperimentale per lambda_home.",
    )
    parser.add_argument(
        "--away-lambda-multiplier",
        type=float,
        default=1.0,
        help="Moltiplicatore sperimentale per lambda_away.",
    )
    parser.add_argument("--elo-initial-rating", type=float, default=1500.0)
    parser.add_argument("--elo-k-factor", type=float, default=24.0)
    parser.add_argument("--elo-home-advantage", type=float, default=65.0)
    parser.add_argument("--elo-season-regression", type=float, default=0.15)
    parser.add_argument(
        "--elo-lambda-weight",
        type=float,
        default=0.0,
        help="Peso del correttore ELO sui lambda. 0.0 mantiene il Poisson base.",
    )

    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    args = _parse_args()

    league_codes = [c.strip() for c in args.leagues.split(",")] if args.leagues else None
    season_codes = [s.strip() for s in args.seasons.split(",")] if args.seasons else None
    leagues = _filter_catalog(league_codes, season_codes)

    if not leagues:
        LOGGER.error(
            "Nessuna lega/stagione trovata con i filtri: leagues=%s seasons=%s",
            league_codes, season_codes,
        )
        sys.exit(1)

    defaults = BacktestDefaults(
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
        elo_initial_rating=args.elo_initial_rating,
        elo_k_factor=args.elo_k_factor,
        elo_home_advantage=args.elo_home_advantage,
        elo_season_regression=args.elo_season_regression,
        elo_lambda_weight=args.elo_lambda_weight,
    )
    policy_store = LeaguePolicyStore(args.policy_file) if args.policy_file else None

    # Fase 1 — Import
    if not args.skip_import:
        _phase_import(leagues)
    else:
        LOGGER.info("Import saltato (--skip-import).")

    # Fase 2 — Backtest
    new_run_ids: list[int] = []
    if not args.skip_backtest:
        new_run_ids = _phase_backtest(leagues, defaults, policy_store=policy_store)
    else:
        LOGGER.info("Backtest saltato (--skip-backtest).")

    # Fase 3 — Calibration
    # Se abbiamo appena creato run, il report li isola.
    # Se skip-backtest, il report copre tutto il DB.
    _phase_calibration(new_run_ids if new_run_ids else None)


if __name__ == "__main__":
    main()
