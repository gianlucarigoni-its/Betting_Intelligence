"""Temporal backtester using rolling historical goals and closing odds."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

from scipy.stats import poisson
from sqlalchemy.orm import Session

from backtesting.persistence_service import (
    BacktestBetInput,
    BacktestBetResult,
    BacktestPersistenceService,
    BacktestRunInput,
)
from database.models import BacktestRun, Competition, HistoricalOddSnapshot, Match
from backtesting.selection_meta_model import SelectionMetaModel
from models.form_features import build_match_form_features
from models.poisson_markets import calculate_poisson_market_probabilities
from models.historical_elo import (
    HistoricalEloCalculator,
    HistoricalEloConfig,
    PreMatchEloRating,
)
from models.value_metrics import ValueMetricsCalculator, ValueMetricsInput


MAX_GOALS = 7


@dataclass(frozen=True, slots=True)
class HistoricalPoissonBacktestConfig:
    """Configuration for a rolling historical Poisson backtest."""

    competition_id: int
    name: str
    model_version: str = "historical-poisson-1.1"
    strategy_name: str = "flat_positive_edge"
    test_start_date: str = "1900-01-01"
    test_end_date: str = "2999-12-31"
    initial_bankroll: float = 1000.0
    flat_stake: float = 10.0
    min_edge_pct: float = 5.0
    max_edge_pct: float | None = 6.0
    min_model_probability: float = 0.55
    max_bookmaker_odds: float | None = 1.8
    allow_home_bets: bool = True
    allow_draw_bets: bool = False
    home_min_form_goal_diff_delta: float | None = None
    draw_min_edge_pct: float = 4.0
    draw_max_edge_pct: float | None = 9.0
    draw_min_model_probability: float = 0.24
    draw_max_bookmaker_odds: float | None = 4.2
    draw_max_lambda_gap: float | None = 0.25
    draw_max_abs_form_goal_diff_delta: float | None = 0.35
    away_min_edge_pct: float | None = 99.0
    away_min_model_probability: float | None = 0.58
    away_max_bookmaker_odds: float | None = 1.8
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
    selection_meta_model_path: str | None = None
    odds_snapshot_type: str = "closing"

@dataclass(frozen=True, slots=True)
class RollingPoissonProbabilities:
    """1X2 probabilities estimated from historical rolling goals."""

    home: float
    draw: float
    away: float
    lambda_home: float
    lambda_away: float
    form_goal_diff_delta: float
    form_goal_diff_delta_10: float
    form_points_delta_5: float
    form_conceded_trend_delta: float
    form_expected_strength_delta: float
    home_clean_sheet_rate_5: float
    away_clean_sheet_rate_5: float
    home_elo: float
    away_elo: float
    elo_diff: float
    over_25: float
    under_25: float
    btts_yes: float
    btts_no: float


class HistoricalPoissonBacktester:
    """Run a temporal Poisson backtest against stored historical odds."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._persistence = BacktestPersistenceService(session)
        self._value_calculator = ValueMetricsCalculator()

    def run(self, config: HistoricalPoissonBacktestConfig) -> BacktestRun:
        """Create and execute a backtest run."""

        competition = self._session.get(Competition, config.competition_id)
        if competition is None:
            raise ValueError(f"Competition id={config.competition_id} not found")

        selection_meta_model = self._load_selection_meta_model(config.selection_meta_model_path)

        run = self._persistence.create_run(
            BacktestRunInput(
                name=config.name,
                model_version=config.model_version,
                model_type="historical_poisson",
                strategy_name=config.strategy_name,
                test_start_date=config.test_start_date,
                test_end_date=config.test_end_date,
                initial_bankroll=config.initial_bankroll,
                notes=(
                    f"competition_id={config.competition_id}; "
                    f"min_edge_pct={config.min_edge_pct}; "
                    f"max_edge_pct={config.max_edge_pct}; "
                    f"min_model_probability={config.min_model_probability}; "
                    f"max_bookmaker_odds={config.max_bookmaker_odds}; "
                    f"allow_home_bets={config.allow_home_bets}; "
                    f"allow_draw_bets={config.allow_draw_bets}; "
                    f"home_min_form_goal_diff_delta="
                    f"{config.home_min_form_goal_diff_delta}; "
                    f"draw_min_edge_pct={config.draw_min_edge_pct}; "
                    f"draw_max_edge_pct={config.draw_max_edge_pct}; "
                    f"draw_min_model_probability="
                    f"{config.draw_min_model_probability}; "
                    f"draw_max_bookmaker_odds={config.draw_max_bookmaker_odds}; "
                    f"draw_max_lambda_gap={config.draw_max_lambda_gap}; "
                    f"draw_max_abs_form_goal_diff_delta="
                    f"{config.draw_max_abs_form_goal_diff_delta}; "
                    f"away_min_edge_pct={config.away_min_edge_pct}; "
                f"away_min_model_probability={config.away_min_model_probability}; "
                f"away_max_bookmaker_odds={config.away_max_bookmaker_odds}; "
                f"allow_away_bets={config.allow_away_bets}; "
                f"min_prior_matches={config.min_prior_matches}; "
                    f"flat_stake={config.flat_stake}; "
                    f"recent_form_half_life_matches="
                    f"{config.recent_form_half_life_matches}; "
                    f"home_lambda_multiplier="
                    f"{config.home_lambda_multiplier}; "
                    f"away_lambda_multiplier="
                    f"{config.away_lambda_multiplier}; "
                    f"elo_k_factor={config.elo_k_factor}; "
                    f"elo_home_advantage={config.elo_home_advantage}; "
                    f"elo_season_regression={config.elo_season_regression}; "
                    f"elo_lambda_weight={config.elo_lambda_weight}; "
                    f"selection_meta_model_path="
                    f"{config.selection_meta_model_path}; "
                    f"odds_snapshot_type={config.odds_snapshot_type}"
                ),
            )
        )

        matches = self._load_test_matches(config)
        elo_by_match = self._load_historical_elo_ratings(config)
        for match in matches:
            probabilities = self._estimate_probabilities(
                match,
                config,
                elo_rating=elo_by_match.get(match.id),
            )
            if probabilities is None:
                continue

            odds_by_selection = self._load_odds(match.id, config.odds_snapshot_type)
            if len(odds_by_selection) < 3:
                continue

            candidate = self._select_best_value_candidate(
                probabilities=probabilities,
                odds_by_selection=odds_by_selection,
                min_edge_pct=config.min_edge_pct,
                max_edge_pct=config.max_edge_pct,
                min_model_probability=config.min_model_probability,
                max_bookmaker_odds=config.max_bookmaker_odds,
                allow_home_bets=config.allow_home_bets,
                allow_draw_bets=config.allow_draw_bets,
                home_min_form_goal_diff_delta=(
                    config.home_min_form_goal_diff_delta
                ),
                draw_min_edge_pct=config.draw_min_edge_pct,
                draw_max_edge_pct=config.draw_max_edge_pct,
                draw_min_model_probability=config.draw_min_model_probability,
                draw_max_bookmaker_odds=config.draw_max_bookmaker_odds,
                draw_max_lambda_gap=config.draw_max_lambda_gap,
                draw_max_abs_form_goal_diff_delta=(
                    config.draw_max_abs_form_goal_diff_delta
                ),
                away_min_edge_pct=config.away_min_edge_pct,
                away_min_model_probability=config.away_min_model_probability,
                away_max_bookmaker_odds=config.away_max_bookmaker_odds,
                allow_away_bets=config.allow_away_bets,
                league_name=competition.name,
                selection_meta_model=selection_meta_model,
            )
            bet_selection: str | None = candidate[0] if candidate is not None else None
            bankroll_before = run.initial_bankroll + run.profit_loss
            bankroll_exhausted = bankroll_before <= 0

            # Salva TUTTE e 3 le selezioni: is_bet=True solo per il candidato
            # vincente. Le non-bet hanno stake=0 e servono per la calibrazione.
            for sel, odds_snapshot in odds_by_selection.items():
                model_prob = self._probability_for_selection(probabilities, sel)
                value_metrics = self._value_calculator.calculate(
                    ValueMetricsInput(
                        model_probability=model_prob,
                        bookmaker_odds=odds_snapshot.odd_value,
                    )
                )
                is_this_bet = (sel == bet_selection) and not bankroll_exhausted
                stake = min(config.flat_stake, bankroll_before) if is_this_bet else 0.0
                meta_probability = candidate[4] if candidate is not None else None
                meta_reason = (
                    f"meta_probability={meta_probability:.3f}; "
                    if meta_probability is not None
                    else ""
                )

                record = self._persistence.record_bet(
                    BacktestBetInput(
                        backtest_run_id=run.id,
                        match_id=match.id,
                        bookmaker_id=odds_snapshot.bookmaker_id,
                        market_level=1,
                        market_type="1X2",
                        market_category="match_result",
                        selection=sel,
                        model_probability=model_prob,
                        bookmaker_probability=(
                            odds_snapshot.fair_prob
                            if odds_snapshot.fair_prob is not None
                            else odds_snapshot.implied_prob
                        ),
                        bookmaker_odds=odds_snapshot.odd_value,
                        edge_pct=value_metrics.edge_pct,
                        expected_value=value_metrics.ev,
                        stake=stake,
                        is_bet=is_this_bet,
                        bankroll_before=bankroll_before if is_this_bet else None,
                        placed_at=odds_snapshot.snapshot_time,
                        reason=(
                            f"lambda_home={probabilities.lambda_home:.3f}; "
                            f"{meta_reason}"
                            f"lambda_away={probabilities.lambda_away:.3f}; "
                            f"form_gd_delta="
                            f"{probabilities.form_goal_diff_delta:.3f}; "
                            f"form_gd_delta_10="
                            f"{probabilities.form_goal_diff_delta_10:.3f}; "
                            f"form_points_delta_5="
                            f"{probabilities.form_points_delta_5:.3f}; "
                            f"form_conceded_trend_delta="
                            f"{probabilities.form_conceded_trend_delta:.3f}; "
                            f"form_expected_strength_delta="
                            f"{probabilities.form_expected_strength_delta:.3f}; "
                            f"home_clean_sheet_rate_5="
                            f"{probabilities.home_clean_sheet_rate_5:.3f}; "
                            f"away_clean_sheet_rate_5="
                            f"{probabilities.away_clean_sheet_rate_5:.3f}; "
                            f"home_elo={probabilities.home_elo:.1f}; "
                            f"away_elo={probabilities.away_elo:.1f}; "
                            f"elo_diff={probabilities.elo_diff:.1f}"
                        ),
                    )
                )
                self._persistence.settle_bet(
                    record.id,
                    self._settlement_result(match, sel),
                )

            run = self._session.get(BacktestRun, run.id) or run

            if bankroll_exhausted:
                break

        return self._persistence.complete_run(run.id)

    def _load_test_matches(self, config: HistoricalPoissonBacktestConfig) -> list[Match]:
        return (
            self._session.query(Match)
            .filter(
                Match.competition_id == config.competition_id,
                Match.status == "finished",
                Match.score_home_ft.is_not(None),
                Match.score_away_ft.is_not(None),
                Match.match_date >= config.test_start_date,
                Match.match_date <= config.test_end_date,
            )
            .order_by(Match.match_date.asc(), Match.id.asc())
            .all()
        )

    def _estimate_probabilities(
        self,
        match: Match,
        config: HistoricalPoissonBacktestConfig,
        *,
        elo_rating: PreMatchEloRating | None = None,
    ) -> RollingPoissonProbabilities | None:
        prior_matches = (
            self._session.query(Match)
            .filter(
                Match.competition_id == config.competition_id,
                Match.status == "finished",
                Match.score_home_ft.is_not(None),
                Match.score_away_ft.is_not(None),
                Match.match_date < match.match_date,
            )
            .order_by(Match.match_date.asc(), Match.id.asc())
            .all()
        )
        if len(prior_matches) < config.min_prior_matches:
            return None

        home_home_prior = [
            item
            for item in prior_matches
            if item.home_team_id == match.home_team_id
        ]
        away_away_prior = [
            item
            for item in prior_matches
            if item.away_team_id == match.away_team_id
        ]
        if (
            len(home_home_prior) < config.min_prior_matches
            or len(away_away_prior) < config.min_prior_matches
        ):
            return None

        half_life = config.recent_form_half_life_matches
        league_home_goals = self._avg_home_goals_for(
            prior_matches,
            half_life_matches=half_life,
        )
        league_away_goals = self._avg_away_goals_for(
            prior_matches,
            half_life_matches=half_life,
        )

        home_attack = self._shrink_ratio(
            value=(
                self._avg_home_goals_for(
                    home_home_prior,
                    half_life_matches=half_life,
                )
                / league_home_goals
            ),
            sample_size=len(home_home_prior),
            shrinkage_matches=config.shrinkage_matches,
        )
        home_defense = self._shrink_ratio(
            value=(
                self._avg_home_goals_against(
                    home_home_prior,
                    half_life_matches=half_life,
                )
                / league_away_goals
            ),
            sample_size=len(home_home_prior),
            shrinkage_matches=config.shrinkage_matches,
        )
        away_attack = self._shrink_ratio(
            value=(
                self._avg_away_goals_for(
                    away_away_prior,
                    half_life_matches=half_life,
                )
                / league_away_goals
            ),
            sample_size=len(away_away_prior),
            shrinkage_matches=config.shrinkage_matches,
        )
        away_defense = self._shrink_ratio(
            value=(
                self._avg_away_goals_against(
                    away_away_prior,
                    half_life_matches=half_life,
                )
                / league_home_goals
            ),
            sample_size=len(away_away_prior),
            shrinkage_matches=config.shrinkage_matches,
        )

        lambda_home = (
            league_home_goals
            * home_attack
            * away_defense
            * config.home_lambda_multiplier
        )
        lambda_away = (
            league_away_goals
            * away_attack
            * home_defense
            * config.away_lambda_multiplier
        )

        effective_elo = elo_rating or PreMatchEloRating(
            home_rating=config.elo_initial_rating,
            away_rating=config.elo_initial_rating,
            elo_diff=0.0,
            expected_home_score=0.5,
        )
        elo_signal = math.tanh(effective_elo.elo_diff / 400.0)
        elo_multiplier = math.exp(config.elo_lambda_weight * elo_signal)
        lambda_home *= elo_multiplier
        lambda_away /= elo_multiplier

        lambda_home = self._clamp_lambda(lambda_home)
        lambda_away = self._clamp_lambda(lambda_away)
        market_probabilities = calculate_poisson_market_probabilities(
            lambda_home,
            lambda_away,
            max_goals=MAX_GOALS,
        )
        home_prob = market_probabilities.home
        draw_prob = market_probabilities.draw
        away_prob = market_probabilities.away
        form = build_match_form_features(
            prior_matches,
            match.home_team_id,
            match.away_team_id,
        )

        return RollingPoissonProbabilities(
            home=home_prob,
            draw=draw_prob,
            away=away_prob,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            form_goal_diff_delta=form.goal_diff_delta_5,
            form_goal_diff_delta_10=form.goal_diff_delta_10,
            form_points_delta_5=form.points_delta_5,
            form_conceded_trend_delta=form.conceded_trend_delta,
            form_expected_strength_delta=form.expected_strength_delta,
            home_clean_sheet_rate_5=form.home_5.clean_sheet_rate,
            away_clean_sheet_rate_5=form.away_5.clean_sheet_rate,
            home_elo=effective_elo.home_rating,
            away_elo=effective_elo.away_rating,
            elo_diff=effective_elo.elo_diff,
            over_25=market_probabilities.over_25,
            under_25=market_probabilities.under_25,
            btts_yes=market_probabilities.btts_yes,
            btts_no=market_probabilities.btts_no,
        )

    @staticmethod
    def _load_selection_meta_model(path: str | None) -> SelectionMetaModel | None:
        if path is None:
            return None
        model_path = Path(path)
        if not model_path.exists():
            raise ValueError(f"Selection meta-model not found: {path}")
        return SelectionMetaModel.load(model_path)

    @staticmethod
    def _selection_policy_for(
        selection: str,
        *,
        min_edge_pct: float,
        max_edge_pct: float | None,
        min_model_probability: float,
        max_bookmaker_odds: float | None,
        allow_home_bets: bool,
        allow_draw_bets: bool,
        home_min_form_goal_diff_delta: float | None,
        draw_min_edge_pct: float,
        draw_max_edge_pct: float | None,
        draw_min_model_probability: float,
        draw_max_bookmaker_odds: float | None,
        draw_max_lambda_gap: float | None,
        draw_max_abs_form_goal_diff_delta: float | None,
        away_min_edge_pct: float | None,
        away_min_model_probability: float | None,
        away_max_bookmaker_odds: float | None,
        allow_away_bets: bool,
    ) -> dict[str, float | bool | None]:
        if selection == "HOME":
            return {
                "enabled": allow_home_bets,
                "min_edge_pct": min_edge_pct,
                "max_edge_pct": max_edge_pct,
                "min_model_probability": min_model_probability,
                "max_odds": max_bookmaker_odds,
                "min_form_goal_diff_delta": home_min_form_goal_diff_delta,
                "max_lambda_gap": None,
                "max_abs_form_goal_diff_delta": None,
                "min_model_probability_override": None,
                "max_odds_override": None,
            }
        if selection == "DRAW":
            return {
                "enabled": allow_draw_bets,
                "min_edge_pct": draw_min_edge_pct,
                "max_edge_pct": draw_max_edge_pct,
                "min_model_probability": draw_min_model_probability,
                "max_odds": draw_max_bookmaker_odds,
                "min_form_goal_diff_delta": None,
                "max_lambda_gap": draw_max_lambda_gap,
                "max_abs_form_goal_diff_delta": draw_max_abs_form_goal_diff_delta,
                "min_model_probability_override": None,
                "max_odds_override": None,
            }
        return {
            "enabled": allow_away_bets,
            "min_edge_pct": away_min_edge_pct if away_min_edge_pct is not None else min_edge_pct,
            "max_edge_pct": None,
            "min_model_probability": away_min_model_probability if away_min_model_probability is not None else min_model_probability,
            "max_odds": away_max_bookmaker_odds if away_max_bookmaker_odds is not None else max_bookmaker_odds,
            "min_form_goal_diff_delta": None,
            "max_lambda_gap": None,
            "max_abs_form_goal_diff_delta": None,
            "min_model_probability_override": away_min_model_probability,
            "max_odds_override": away_max_bookmaker_odds,
        }

    @staticmethod
    def _selection_meta_threshold(selection: str) -> float:
        if selection == "DRAW":
            return 0.52
        if selection == "AWAY":
            return 0.58
        return 0.55

    @staticmethod
    def _selection_meta_probability(
        *,
        selection_meta_model: SelectionMetaModel,
        selection: str,
        league_name: str,
        probabilities: RollingPoissonProbabilities,
        odds_snapshot: HistoricalOddSnapshot,
        model_probability: float,
    ) -> float:
        bookmaker_probability = (
            odds_snapshot.fair_prob
            if odds_snapshot.fair_prob is not None
            else odds_snapshot.implied_prob
        )
        return selection_meta_model.predict_probability_for_features(
            {
                "selection": selection,
                "league": league_name,
                "edge_pct": (model_probability - bookmaker_probability) * 100.0,
                "bookmaker_odds": odds_snapshot.odd_value,
                "model_probability": model_probability,
                "bookmaker_probability": bookmaker_probability,
                "model_market_distance": abs(model_probability - bookmaker_probability),
                "lambda_home": probabilities.lambda_home,
                "lambda_away": probabilities.lambda_away,
                "lambda_gap": abs(probabilities.lambda_home - probabilities.lambda_away),
            }
        )

    def _load_historical_elo_ratings(
        self,
        config: HistoricalPoissonBacktestConfig,
    ) -> dict[int, PreMatchEloRating]:
        competition = self._session.get(Competition, config.competition_id)
        if competition is None:
            raise ValueError(f"Competition id={config.competition_id} not found")

        matches = (
            self._session.query(Match)
            .join(Competition, Match.competition_id == Competition.id)
            .filter(
                Competition.sport_id == competition.sport_id,
                Competition.name == competition.name,
                Match.status == "finished",
                Match.score_home_ft.is_not(None),
                Match.score_away_ft.is_not(None),
                Match.match_date <= config.test_end_date,
            )
            .order_by(Match.match_date.asc(), Match.id.asc())
            .all()
        )
        calculator = HistoricalEloCalculator(
            HistoricalEloConfig(
                initial_rating=config.elo_initial_rating,
                k_factor=config.elo_k_factor,
                home_advantage=config.elo_home_advantage,
                season_regression=config.elo_season_regression,
            )
        )
        return calculator.build_pre_match_ratings(matches)

    def _load_odds(
        self,
        match_id: int,
        snapshot_type: str,
    ) -> dict[str, HistoricalOddSnapshot]:
        if snapshot_type not in {"opening", "closing"}:
            raise ValueError("odds_snapshot_type must be 'opening' or 'closing'")

        query = self._session.query(HistoricalOddSnapshot).filter(
            HistoricalOddSnapshot.match_id == match_id,
            HistoricalOddSnapshot.market_type == "1X2",
        )
        if snapshot_type == "opening":
            query = query.filter(HistoricalOddSnapshot.is_opening.is_(True))
        else:
            query = query.filter(HistoricalOddSnapshot.is_closing.is_(True))

        return {item.selection: item for item in query.all()}

    def _load_closing_odds(self, match_id: int) -> dict[str, HistoricalOddSnapshot]:
        return self._load_odds(match_id, "closing")

    def _select_best_value_candidate(
        self,
        *,
        probabilities: RollingPoissonProbabilities,
        odds_by_selection: dict[str, HistoricalOddSnapshot],
        min_edge_pct: float,
        max_edge_pct: float | None,
        min_model_probability: float,
        max_bookmaker_odds: float | None,
        allow_home_bets: bool,
        allow_draw_bets: bool,
        home_min_form_goal_diff_delta: float | None,
        draw_min_edge_pct: float,
        draw_max_edge_pct: float | None,
        draw_min_model_probability: float,
        draw_max_bookmaker_odds: float | None,
        draw_max_lambda_gap: float | None,
        draw_max_abs_form_goal_diff_delta: float | None,
        away_min_edge_pct: float | None,
        away_min_model_probability: float | None,
        away_max_bookmaker_odds: float | None,
        allow_away_bets: bool,
        league_name: str = "unknown",
        selection_meta_model: SelectionMetaModel | None = None,
    ) -> tuple[str, HistoricalOddSnapshot, float, float, float] | None:
        candidates: list[tuple[str, HistoricalOddSnapshot, float, float, float]] = []
        lambda_gap = abs(probabilities.lambda_home - probabilities.lambda_away)
        form_delta = probabilities.form_goal_diff_delta

        for selection, odds_snapshot in odds_by_selection.items():
            policy = self._selection_policy_for(
                selection,
                min_edge_pct=min_edge_pct,
                max_edge_pct=max_edge_pct,
                min_model_probability=min_model_probability,
                max_bookmaker_odds=max_bookmaker_odds,
                allow_home_bets=allow_home_bets,
                allow_draw_bets=allow_draw_bets,
                home_min_form_goal_diff_delta=home_min_form_goal_diff_delta,
                draw_min_edge_pct=draw_min_edge_pct,
                draw_max_edge_pct=draw_max_edge_pct,
                draw_min_model_probability=draw_min_model_probability,
                draw_max_bookmaker_odds=draw_max_bookmaker_odds,
                draw_max_lambda_gap=draw_max_lambda_gap,
                draw_max_abs_form_goal_diff_delta=draw_max_abs_form_goal_diff_delta,
                away_min_edge_pct=away_min_edge_pct,
                away_min_model_probability=away_min_model_probability,
                away_max_bookmaker_odds=away_max_bookmaker_odds,
                allow_away_bets=allow_away_bets,
            )
            if not policy["enabled"]:
                continue
            if policy["max_odds"] is not None and odds_snapshot.odd_value > policy["max_odds"]:
                continue

            model_probability = self._probability_for_selection(probabilities, selection)
            if model_probability < policy["min_model_probability"]:
                continue

            if selection == "DRAW":
                if policy["max_lambda_gap"] is not None and lambda_gap > policy["max_lambda_gap"]:
                    continue
                if policy["max_abs_form_goal_diff_delta"] is not None and abs(form_delta) > policy["max_abs_form_goal_diff_delta"]:
                    continue
            elif selection == "HOME" and policy["min_form_goal_diff_delta"] is not None:
                if form_delta < policy["min_form_goal_diff_delta"]:
                    continue

            if selection == "AWAY":
                if policy["min_model_probability_override"] is not None and model_probability < policy["min_model_probability_override"]:
                    continue
                if policy["max_odds_override"] is not None and odds_snapshot.odd_value > policy["max_odds_override"]:
                    continue

            value_metrics = self._value_calculator.calculate(
                ValueMetricsInput(
                    model_probability=model_probability,
                    bookmaker_odds=odds_snapshot.odd_value,
                )
            )
            if value_metrics.edge_pct < policy["min_edge_pct"]:
                continue
            if policy["max_edge_pct"] is not None and value_metrics.edge_pct > policy["max_edge_pct"]:
                continue

            meta_probability = 1.0
            if selection_meta_model is not None:
                meta_probability = self._selection_meta_probability(
                    selection_meta_model=selection_meta_model,
                    selection=selection,
                    league_name=league_name,
                    probabilities=probabilities,
                    odds_snapshot=odds_snapshot,
                    model_probability=model_probability,
                )
                if meta_probability < self._selection_meta_threshold(selection):
                    continue

            candidates.append(
                (
                    selection,
                    odds_snapshot,
                    value_metrics.edge_pct,
                    value_metrics.ev,
                    meta_probability,
                )
            )

        if not candidates:
            return None
        if selection_meta_model is None:
            return max(candidates, key=lambda item: item[2])
        return max(candidates, key=lambda item: (item[4], item[2]))


    @staticmethod
    def _recent_goal_difference(
        matches: list[Match],
        team_id: int,
        *,
        window_matches: int,
    ) -> float:
        team_matches = [
            match for match in matches
            if match.home_team_id == team_id or match.away_team_id == team_id
        ]
        if not team_matches:
            return 0.0

        ordered_matches = sorted(
            team_matches,
            key=lambda item: (item.match_date, item.id),
        )[-window_matches:]
        total = 0.0
        for match in ordered_matches:
            if match.home_team_id == team_id:
                total += float((match.score_home_ft or 0) - (match.score_away_ft or 0))
            else:
                total += float((match.score_away_ft or 0) - (match.score_home_ft or 0))
        return total / len(ordered_matches)

    @staticmethod
    def _avg_home_goals_for(
        matches: list[Match],
        *,
        half_life_matches: float,
    ) -> float:
        return HistoricalPoissonBacktester._weighted_average_goals(
            matches=matches,
            goal_attr="score_home_ft",
            half_life_matches=half_life_matches,
        )

    @staticmethod
    def _avg_home_goals_against(
        matches: list[Match],
        *,
        half_life_matches: float,
    ) -> float:
        return HistoricalPoissonBacktester._weighted_average_goals(
            matches=matches,
            goal_attr="score_away_ft",
            half_life_matches=half_life_matches,
        )

    @staticmethod
    def _avg_away_goals_for(
        matches: list[Match],
        *,
        half_life_matches: float,
    ) -> float:
        return HistoricalPoissonBacktester._weighted_average_goals(
            matches=matches,
            goal_attr="score_away_ft",
            half_life_matches=half_life_matches,
        )

    @staticmethod
    def _avg_away_goals_against(
        matches: list[Match],
        *,
        half_life_matches: float,
    ) -> float:
        return HistoricalPoissonBacktester._weighted_average_goals(
            matches=matches,
            goal_attr="score_home_ft",
            half_life_matches=half_life_matches,
        )

    @staticmethod
    def _weighted_average_goals(
        *,
        matches: list[Match],
        goal_attr: str,
        half_life_matches: float,
    ) -> float:
        """
        Calcola una media gol pesata per recenza.

        Le partite più recenti pesano di più. Con half-life = 8,
        una partita distante 8 gare pesa circa metà rispetto all'ultima.
        """
        if not matches:
            return 0.2

        if half_life_matches <= 0:
            simple_average = sum(
                float(getattr(match, goal_attr) or 0)
                for match in matches
            ) / len(matches)
            return max(simple_average, 0.2)

        ordered_matches = sorted(
            matches,
            key=lambda item: (item.match_date, item.id),
        )

        weighted_sum = 0.0
        total_weight = 0.0
        latest_index = len(ordered_matches) - 1

        for index, match in enumerate(ordered_matches):
            distance_from_latest = latest_index - index
            weight = 0.5 ** (distance_from_latest / half_life_matches)
            goals = float(getattr(match, goal_attr) or 0)

            weighted_sum += goals * weight
            total_weight += weight

        if total_weight <= 0:
            return 0.2

        return max(weighted_sum / total_weight, 0.2)

    @staticmethod
    def _shrink_ratio(*, value: float, sample_size: int, shrinkage_matches: int) -> float:
        if shrinkage_matches <= 0:
            return value
        weight = sample_size / (sample_size + shrinkage_matches)
        return (value * weight) + (1.0 * (1.0 - weight))

    @staticmethod
    def _aggregate_1x2(lambda_home: float, lambda_away: float) -> tuple[float, float, float]:
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        for home_goals in range(MAX_GOALS + 1):
            for away_goals in range(MAX_GOALS + 1):
                probability = float(poisson.pmf(home_goals, lambda_home)) * float(
                    poisson.pmf(away_goals, lambda_away)
                )
                if home_goals > away_goals:
                    home_win += probability
                elif home_goals == away_goals:
                    draw += probability
                else:
                    away_win += probability

        total = home_win + draw + away_win
        return home_win / total, draw / total, away_win / total

    @staticmethod
    def _probability_for_selection(
        probabilities: RollingPoissonProbabilities,
        selection: str,
    ) -> float:
        if selection == "HOME":
            return probabilities.home
        if selection == "DRAW":
            return probabilities.draw
        if selection == "AWAY":
            return probabilities.away
        if selection == "OVER_2_5":
            return probabilities.over_25
        if selection == "UNDER_2_5":
            return probabilities.under_25
        if selection == "BTTS_YES":
            return probabilities.btts_yes
        if selection == "BTTS_NO":
            return probabilities.btts_no
        raise ValueError(f"Unsupported selection: {selection}")

    @staticmethod
    def _settlement_result(match: Match, selection: str) -> BacktestBetResult:
        home_goals = match.score_home_ft or 0
        away_goals = match.score_away_ft or 0
        if selection in {"OVER_2_5", "UNDER_2_5"}:
            actual = "OVER_2_5" if home_goals + away_goals >= 3 else "UNDER_2_5"
            return BacktestBetResult.WON if selection == actual else BacktestBetResult.LOST
        if selection in {"BTTS_YES", "BTTS_NO"}:
            actual = "BTTS_YES" if home_goals > 0 and away_goals > 0 else "BTTS_NO"
            return BacktestBetResult.WON if selection == actual else BacktestBetResult.LOST
        if home_goals == away_goals:
            actual = "DRAW"
        elif home_goals > away_goals:
            actual = "HOME"
        else:
            actual = "AWAY"
        return BacktestBetResult.WON if selection == actual else BacktestBetResult.LOST

    @staticmethod
    def _clamp_lambda(value: float) -> float:
        return max(0.05, min(6.0, value))
