"""Temporal backtester using rolling historical goals and closing odds."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import poisson
from sqlalchemy.orm import Session

from backtesting.persistence_service import (
    BacktestBetInput,
    BacktestBetResult,
    BacktestPersistenceService,
    BacktestRunInput,
)
from database.models import BacktestRun, HistoricalOddSnapshot, Match
from models.value_metrics import ValueMetricsCalculator, ValueMetricsInput


MAX_GOALS = 7


@dataclass(frozen=True, slots=True)
class HistoricalPoissonBacktestConfig:
    """Configuration for a rolling historical Poisson backtest."""

    competition_id: int
    name: str
    model_version: str = "historical-poisson-1.0"
    strategy_name: str = "flat_positive_edge"
    test_start_date: str = "1900-01-01"
    test_end_date: str = "2999-12-31"
    initial_bankroll: float = 1000.0
    flat_stake: float = 10.0
    min_edge_pct: float = 3.0
    max_edge_pct: float | None = 12.0
    min_model_probability: float = 0.55
    max_bookmaker_odds: float | None = 2.0
    min_prior_matches: int = 5
    shrinkage_matches: int = 10
    recent_form_half_life_matches: float = 0.0

@dataclass(frozen=True, slots=True)
class RollingPoissonProbabilities:
    """1X2 probabilities estimated from historical rolling goals."""

    home: float
    draw: float
    away: float
    lambda_home: float
    lambda_away: float


class HistoricalPoissonBacktester:
    """Run a temporal Poisson backtest against stored historical odds."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._persistence = BacktestPersistenceService(session)
        self._value_calculator = ValueMetricsCalculator()

    def run(self, config: HistoricalPoissonBacktestConfig) -> BacktestRun:
        """Create and execute a backtest run."""

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
                    f"min_prior_matches={config.min_prior_matches}; "
                    f"flat_stake={config.flat_stake}; "
                    f"recent_form_half_life_matches="
                    f"{config.recent_form_half_life_matches}"
                ),
            )
        )

        matches = self._load_test_matches(config)
        for match in matches:
            probabilities = self._estimate_probabilities(match, config)
            if probabilities is None:
                continue

            odds_by_selection = self._load_closing_odds(match.id)
            if len(odds_by_selection) < 3:
                continue

            candidate = self._select_best_value_candidate(
                probabilities=probabilities,
                odds_by_selection=odds_by_selection,
                min_edge_pct=config.min_edge_pct,
                max_edge_pct=config.max_edge_pct,
                min_model_probability=config.min_model_probability,
                max_bookmaker_odds=config.max_bookmaker_odds,
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
                            f"lambda_away={probabilities.lambda_away:.3f}"
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

        lambda_home = league_home_goals * home_attack * away_defense
        lambda_away = league_away_goals * away_attack * home_defense

        lambda_home = self._clamp_lambda(lambda_home)
        lambda_away = self._clamp_lambda(lambda_away)
        home_prob, draw_prob, away_prob = self._aggregate_1x2(lambda_home, lambda_away)

        return RollingPoissonProbabilities(
            home=home_prob,
            draw=draw_prob,
            away=away_prob,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
        )

    def _load_closing_odds(self, match_id: int) -> dict[str, HistoricalOddSnapshot]:
        odds = (
            self._session.query(HistoricalOddSnapshot)
            .filter(
                HistoricalOddSnapshot.match_id == match_id,
                HistoricalOddSnapshot.market_type == "1X2",
                HistoricalOddSnapshot.is_closing.is_(True),
            )
            .all()
        )
        return {item.selection: item for item in odds}

    def _select_best_value_candidate(
        self,
        *,
        probabilities: RollingPoissonProbabilities,
        odds_by_selection: dict[str, HistoricalOddSnapshot],
        min_edge_pct: float,
        max_edge_pct: float | None,
        min_model_probability: float,
        max_bookmaker_odds: float | None,
    ) -> tuple[str, HistoricalOddSnapshot, float, float] | None:
        candidates: list[tuple[str, HistoricalOddSnapshot, float, float]] = []
        for selection, odds_snapshot in odds_by_selection.items():
            if max_bookmaker_odds is not None and odds_snapshot.odd_value > max_bookmaker_odds:
                continue

            model_probability = self._probability_for_selection(probabilities, selection)
            if model_probability < min_model_probability:
                continue

            value_metrics = self._value_calculator.calculate(
                ValueMetricsInput(
                    model_probability=model_probability,
                    bookmaker_odds=odds_snapshot.odd_value,
                )
            )
            if value_metrics.edge_pct < min_edge_pct:
                continue
            if max_edge_pct is not None and value_metrics.edge_pct > max_edge_pct:
                continue

            candidates.append(
                (
                    selection,
                    odds_snapshot,
                    value_metrics.edge_pct,
                    value_metrics.ev,
                )
            )

        if not candidates:
            return None
        return max(candidates, key=lambda item: item[2])

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
        raise ValueError(f"Unsupported selection: {selection}")

    @staticmethod
    def _settlement_result(match: Match, selection: str) -> BacktestBetResult:
        if match.score_home_ft == match.score_away_ft:
            actual = "DRAW"
        elif (match.score_home_ft or 0) > (match.score_away_ft or 0):
            actual = "HOME"
        else:
            actual = "AWAY"
        return BacktestBetResult.WON if selection == actual else BacktestBetResult.LOST

    @staticmethod
    def _clamp_lambda(value: float) -> float:
        return max(0.05, min(6.0, value))
