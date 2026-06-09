"""Walk-forward tuning for league-specific betting policies.

The script tunes one policy per league on older seasons, saves the resulting
policy file, and validates the chosen policy on the latest season as an
out-of-sample sanity check.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from backtesting.league_policy import LeagueBettingPolicy, LeaguePolicyStore
from database.base import SessionLocal
from database.models import BacktestBet, BacktestRun, Competition
from historical.batch_importer import LEAGUE_CATALOG, LeagueConfig

LOGGER = logging.getLogger(__name__)
DEFAULT_POLICY_PATH = Path("config/league_backtest_policy.json")


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    bets: int
    stake: float
    profit_loss: float
    roi_pct: float | None


@dataclass(frozen=True, slots=True)
class FoldResult:
    season_code: str
    train_seasons: tuple[str, ...]
    holdout: SimulationMetrics


@dataclass(frozen=True, slots=True)
class LeagueTuningResult:
    policy: LeagueBettingPolicy
    folds: tuple[FoldResult, ...]
    stable: bool
    reason: str


def _season_start_year(season_code: str) -> int:
    return 2000 + int(season_code[:2])


def _season_label(season_code: str) -> str:
    return f"20{season_code[:2]}/20{season_code[2:]}"


def _season_dates(season_code: str) -> tuple[str, str]:
    start_year = _season_start_year(season_code)
    end_year = 2000 + int(season_code[2:])
    return f"{start_year}-08-01", f"{end_year}-06-30"


def _filter_catalog(
    league_codes: list[str] | None,
    season_codes: list[str] | None,
) -> list[LeagueConfig]:
    result: list[LeagueConfig] = []
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


def _chronological_seasons(seasons: tuple[str, ...]) -> list[str]:
    return sorted(seasons, key=lambda code: _season_start_year(code))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--leagues",
        help="Codici lega separati da virgola (es. E0,SP1). Default: tutte.",
    )
    parser.add_argument(
        "--seasons",
        help="Codici stagione separati da virgola. Default: quelle del catalogo.",
    )
    parser.add_argument(
        "--policy-file",
        default=str(DEFAULT_POLICY_PATH),
        help="Percorso JSON della policy di betting per lega.",
    )
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--flat-stake", type=float, default=10.0)
    parser.add_argument("--min-prior-matches", type=int, default=5)
    parser.add_argument("--shrinkage-matches", type=int, default=10)
    parser.add_argument("--recent-form-half-life-matches", type=float, default=0.0)
    parser.add_argument("--home-lambda-multiplier", type=float, default=1.0)
    parser.add_argument("--away-lambda-multiplier", type=float, default=1.0)
    parser.add_argument("--min-walkforward-bets", type=int, default=5)
    parser.add_argument("--min-positive-fold-rate", type=float, default=0.5)
    return parser.parse_args()


def _simulate_season(
    session,
    *,
    competition_id: int,
    test_start_date: str,
    test_end_date: str,
    policy: LeagueBettingPolicy,
    initial_bankroll: float,
    flat_stake: float,
    min_prior_matches: int,
    shrinkage_matches: int,
    recent_form_half_life_matches: float,
    home_lambda_multiplier: float,
    away_lambda_multiplier: float,
) -> SimulationMetrics:
    del (
        test_start_date,
        test_end_date,
        min_prior_matches,
        shrinkage_matches,
        recent_form_half_life_matches,
        home_lambda_multiplier,
        away_lambda_multiplier,
    )
    latest_run = (
        session.query(BacktestRun)
        .filter(BacktestRun.notes.contains(f"competition_id={competition_id};"))
        .order_by(BacktestRun.id.desc())
        .first()
    )
    if latest_run is None:
        return SimulationMetrics(0, 0.0, 0.0, None)

    records = (
        session.query(BacktestBet)
        .filter(BacktestBet.backtest_run_id == latest_run.id)
        .all()
    )
    by_match: dict[int, list[BacktestBet]] = {}
    for record in records:
        by_match.setdefault(record.match_id, []).append(record)

    bankroll = initial_bankroll
    profit_loss = 0.0
    bets = 0
    for match_records in by_match.values():
        candidates: list[BacktestBet] = []
        for record in match_records:
            if record.selection == "AWAY" and not policy.allow_away_bets:
                continue
            if policy.max_bookmaker_odds is not None and record.bookmaker_odds > policy.max_bookmaker_odds:
                continue
            if record.model_probability < policy.min_model_probability:
                continue
            if record.selection == "AWAY":
                if (
                    policy.away_min_model_probability is not None
                    and record.model_probability < policy.away_min_model_probability
                ):
                    continue
                if (
                    policy.away_max_bookmaker_odds is not None
                    and record.bookmaker_odds > policy.away_max_bookmaker_odds
                ):
                    continue
            if record.edge_pct < policy.min_edge_pct:
                continue
            if (
                record.selection == "AWAY"
                and policy.away_min_edge_pct is not None
                and record.edge_pct < policy.away_min_edge_pct
            ):
                continue
            if policy.max_edge_pct is not None and record.edge_pct > policy.max_edge_pct:
                continue
            candidates.append(record)

        if not candidates:
            continue

        candidate = max(candidates, key=lambda item: item.edge_pct)
        if bankroll <= 0:
            break

        stake = min(flat_stake, bankroll)
        if candidate.result == "won":
            delta = stake * (candidate.bookmaker_odds - 1.0)
        elif candidate.result == "lost":
            delta = -stake
        else:
            delta = 0.0

        bankroll += delta
        profit_loss += delta
        bets += 1

    return SimulationMetrics(
        bets=bets,
        stake=flat_stake * bets,
        profit_loss=round(profit_loss, 2),
        roi_pct=(profit_loss / (flat_stake * bets) * 100.0) if bets else None,
    )


def _evaluate_policy_on_folds(
    *,
    league: LeagueConfig,
    policy: LeagueBettingPolicy,
    season_codes: list[str],
    initial_bankroll: float,
    flat_stake: float,
    min_prior_matches: int,
    shrinkage_matches: int,
    recent_form_half_life_matches: float,
    home_lambda_multiplier: float,
    away_lambda_multiplier: float,
) -> tuple[FoldResult, ...]:
    folds: list[FoldResult] = []
    chronological = _chronological_seasons(tuple(season_codes))

    for idx in range(2, len(chronological)):
        train_seasons = tuple(chronological[:idx])
        holdout_season = chronological[idx]
        season_label = _season_label(holdout_season)
        test_start, test_end = _season_dates(holdout_season)

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
                continue

            metrics = _simulate_season(
                session,
                competition_id=competition.id,
                test_start_date=test_start,
                test_end_date=test_end,
                policy=policy,
                initial_bankroll=initial_bankroll,
                flat_stake=flat_stake,
                min_prior_matches=min_prior_matches,
                shrinkage_matches=shrinkage_matches,
                recent_form_half_life_matches=recent_form_half_life_matches,
                home_lambda_multiplier=home_lambda_multiplier,
                away_lambda_multiplier=away_lambda_multiplier,
            )
            folds.append(
                FoldResult(
                    season_code=holdout_season,
                    train_seasons=train_seasons,
                    holdout=metrics,
                )
            )

    return tuple(folds)


def _policy_score(folds: tuple[FoldResult, ...]) -> tuple[float, int, float]:
    bets = sum(fold.holdout.bets for fold in folds)
    profit_loss = sum(fold.holdout.profit_loss for fold in folds)
    staked = sum(fold.holdout.stake for fold in folds)
    roi = (profit_loss / staked) * 100.0 if staked else float("-inf")
    return roi, bets, profit_loss


def _positive_fold_rate(folds: tuple[FoldResult, ...]) -> float:
    active_folds = [fold for fold in folds if fold.holdout.bets > 0]
    if not active_folds:
        return 0.0
    positive = sum(1 for fold in active_folds if fold.holdout.profit_loss > 0)
    return positive / len(active_folds)


def _no_bet_policy() -> LeagueBettingPolicy:
    return LeagueBettingPolicy(
        min_edge_pct=99.0,
        max_edge_pct=100.0,
        min_model_probability=0.99,
        max_bookmaker_odds=1.01,
        away_min_edge_pct=99.0,
        away_min_model_probability=0.99,
        away_max_bookmaker_odds=1.01,
        allow_away_bets=False,
    )


def _candidate_grid() -> tuple[LeagueBettingPolicy, ...]:
    edge_pairs = ((5.0, 6.0), (5.0, 6.5), (5.5, 6.5))
    odds_caps = (1.8, 2.0)
    model_probs = (0.53, 0.55, 0.57)
    away_modes = (
        LeagueBettingPolicy(
            min_edge_pct=5.0,
            max_edge_pct=6.0,
            min_model_probability=0.55,
            max_bookmaker_odds=1.8,
            away_min_edge_pct=99.0,
            away_min_model_probability=0.58,
            away_max_bookmaker_odds=1.8,
            allow_away_bets=False,
        ),
        LeagueBettingPolicy(
            min_edge_pct=5.0,
            max_edge_pct=6.5,
            min_model_probability=0.53,
            max_bookmaker_odds=1.8,
            away_min_edge_pct=8.0,
            away_min_model_probability=0.60,
            away_max_bookmaker_odds=1.7,
            allow_away_bets=True,
        ),
    )

    grid: list[LeagueBettingPolicy] = []
    for min_edge, max_edge in edge_pairs:
        for max_odds in odds_caps:
            for min_prob in model_probs:
                grid.append(
                    LeagueBettingPolicy(
                        min_edge_pct=min_edge,
                        max_edge_pct=max_edge,
                        min_model_probability=min_prob,
                        max_bookmaker_odds=max_odds,
                        away_min_edge_pct=99.0,
                        away_min_model_probability=0.58,
                        away_max_bookmaker_odds=1.8,
                        allow_away_bets=False,
                    )
                )
    grid.extend(away_modes)
    return tuple(grid)


def _tune_league(
    league: LeagueConfig,
    season_codes: list[str],
    *,
    initial_bankroll: float,
    flat_stake: float,
    min_prior_matches: int,
    shrinkage_matches: int,
    recent_form_half_life_matches: float,
    home_lambda_multiplier: float,
    away_lambda_multiplier: float,
    min_walkforward_bets: int,
    min_positive_fold_rate: float,
) -> LeagueTuningResult:
    candidates = _candidate_grid()
    best_policy = candidates[0]
    best_score = (float("-inf"), 0, float("-inf"))
    best_folds: tuple[FoldResult, ...] = ()

    for candidate in candidates:
        folds = _evaluate_policy_on_folds(
            league=league,
            policy=candidate,
            season_codes=season_codes,
            initial_bankroll=initial_bankroll,
            flat_stake=flat_stake,
            min_prior_matches=min_prior_matches,
            shrinkage_matches=shrinkage_matches,
            recent_form_half_life_matches=recent_form_half_life_matches,
            home_lambda_multiplier=home_lambda_multiplier,
            away_lambda_multiplier=away_lambda_multiplier,
        )
        if not folds:
            continue

        score = _policy_score(folds)
        if score[1] < 3:
            continue

        if score > best_score:
            best_score = score
            best_policy = candidate
            best_folds = folds

    best_roi, best_bets, _ = _policy_score(best_folds)
    positive_rate = _positive_fold_rate(best_folds)
    if best_bets < min_walkforward_bets:
        return LeagueTuningResult(
            policy=_no_bet_policy(),
            folds=best_folds,
            stable=False,
            reason=(
                f"no-bet: walk-forward bets {best_bets} < "
                f"{min_walkforward_bets}"
            ),
        )
    if positive_rate < min_positive_fold_rate:
        return LeagueTuningResult(
            policy=_no_bet_policy(),
            folds=best_folds,
            stable=False,
            reason=(
                f"no-bet: positive fold rate {positive_rate:.2f} < "
                f"{min_positive_fold_rate:.2f}"
            ),
        )
    if best_roi <= 0:
        return LeagueTuningResult(
            policy=_no_bet_policy(),
            folds=best_folds,
            stable=False,
            reason=f"no-bet: walk-forward ROI {best_roi:.2f}% <= 0",
        )

    return LeagueTuningResult(
        policy=best_policy,
        folds=best_folds,
        stable=True,
        reason="active",
    )


def _final_holdout(
    league: LeagueConfig,
    season_code: str,
    policy: LeagueBettingPolicy,
    *,
    initial_bankroll: float,
    flat_stake: float,
    min_prior_matches: int,
    shrinkage_matches: int,
    recent_form_half_life_matches: float,
    home_lambda_multiplier: float,
    away_lambda_multiplier: float,
) -> SimulationMetrics:
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
            return SimulationMetrics(0, 0.0, 0.0, None)

        return _simulate_season(
            session,
            competition_id=competition.id,
            test_start_date=test_start,
            test_end_date=test_end,
            policy=policy,
            initial_bankroll=initial_bankroll,
            flat_stake=flat_stake,
            min_prior_matches=min_prior_matches,
            shrinkage_matches=shrinkage_matches,
            recent_form_half_life_matches=recent_form_half_life_matches,
            home_lambda_multiplier=home_lambda_multiplier,
            away_lambda_multiplier=away_lambda_multiplier,
        )


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
            league_codes,
            season_codes,
        )
        sys.exit(1)

    policy_store = LeaguePolicyStore(args.policy_file)
    tuned_policies: dict[str, LeagueBettingPolicy] = {}

    print("\nWALK-FORWARD TUNING")
    print("=" * 72)
    for league in leagues:
        seasons = _chronological_seasons(league.seasons)
        if len(seasons) < 4:
            LOGGER.warning("Skip %s: servono almeno 4 stagioni", league.label)
            continue

        tune_seasons = seasons[:-1]
        final_holdout = seasons[-1]

        result = _tune_league(
            league,
            tune_seasons,
            initial_bankroll=args.initial_bankroll,
            flat_stake=args.flat_stake,
            min_prior_matches=args.min_prior_matches,
            shrinkage_matches=args.shrinkage_matches,
            recent_form_half_life_matches=args.recent_form_half_life_matches,
            home_lambda_multiplier=args.home_lambda_multiplier,
            away_lambda_multiplier=args.away_lambda_multiplier,
            min_walkforward_bets=args.min_walkforward_bets,
            min_positive_fold_rate=args.min_positive_fold_rate,
        )
        policy = result.policy
        folds = result.folds
        tuned_policies[league.label] = policy

        fold_roi = _policy_score(folds)
        final_metrics = _final_holdout(
            league,
            final_holdout,
            policy,
            initial_bankroll=args.initial_bankroll,
            flat_stake=args.flat_stake,
            min_prior_matches=args.min_prior_matches,
            shrinkage_matches=args.shrinkage_matches,
            recent_form_half_life_matches=args.recent_form_half_life_matches,
            home_lambda_multiplier=args.home_lambda_multiplier,
            away_lambda_multiplier=args.away_lambda_multiplier,
        )

        print(f"\n{league.label}")
        print(
            f"  policy  : edge {policy.min_edge_pct:.1f}-{policy.max_edge_pct:.1f} | "
            f"odds <= {policy.max_bookmaker_odds:.2f} | away={policy.allow_away_bets}"
        )
        print(f"  status  : {result.reason}")
        print(
            f"  walkfwd : ROI={fold_roi[0]:.2f}% | bets={fold_roi[1]} | "
            f"P&L={fold_roi[2]:.2f}"
        )
        print(
            f"  holdout : season={final_holdout} | ROI={final_metrics.roi_pct if final_metrics.roi_pct is not None else 'N/A'}% | "
            f"bets={final_metrics.bets} | P&L={final_metrics.profit_loss:.2f}"
        )

    policy_store.save(tuned_policies)
    print(f"\nPolicy file saved to: {args.policy_file}")
    print("=" * 72)


if __name__ == "__main__":
    main()
