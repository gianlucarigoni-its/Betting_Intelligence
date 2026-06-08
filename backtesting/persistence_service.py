"""Persistence helpers for backtest runs and simulated bets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from database.models import BacktestBet, BacktestRun


class BacktestBetResult(str, Enum):
    """Settlement result for a simulated backtest bet."""

    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSH = "push"


@dataclass(frozen=True, slots=True)
class BacktestRunInput:
    """Input required to create a backtest run."""

    name: str
    model_version: str
    model_type: str
    strategy_name: str
    test_start_date: str
    test_end_date: str
    initial_bankroll: float
    train_start_date: str | None = None
    train_end_date: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class BacktestBetInput:
    """Input required to persist one simulated backtest bet."""

    backtest_run_id: int
    match_id: int
    market_level: int
    market_type: str
    market_category: str
    selection: str
    model_probability: float
    bookmaker_probability: float
    bookmaker_odds: float
    edge_pct: float
    stake: float
    expected_value: float | None = None
    prediction_id: int | None = None
    bookmaker_id: int | None = None
    bankroll_before: float | None = None
    placed_at: str | None = None
    reason: str | None = None


class BacktestPersistenceService:
    """Store backtest runs, simulated bets and settlement summaries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(self, payload: BacktestRunInput) -> BacktestRun:
        """Create a new backtest run."""

        if payload.initial_bankroll <= 0:
            raise ValueError("initial_bankroll must be positive")

        run = BacktestRun(
            name=payload.name,
            model_version=payload.model_version,
            model_type=payload.model_type,
            strategy_name=payload.strategy_name,
            train_start_date=payload.train_start_date,
            train_end_date=payload.train_end_date,
            test_start_date=payload.test_start_date,
            test_end_date=payload.test_end_date,
            initial_bankroll=payload.initial_bankroll,
            final_bankroll=payload.initial_bankroll,
            notes=payload.notes,
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def record_bet(self, payload: BacktestBetInput) -> BacktestBet:
        """Persist one pending simulated bet and refresh run totals."""

        self._validate_probability(payload.model_probability, "model_probability")
        self._validate_probability(payload.bookmaker_probability, "bookmaker_probability")
        if payload.bookmaker_odds <= 1.0:
            raise ValueError("bookmaker_odds must be greater than 1")
        if payload.stake <= 0:
            raise ValueError("stake must be positive")

        bet = BacktestBet(
            backtest_run_id=payload.backtest_run_id,
            match_id=payload.match_id,
            prediction_id=payload.prediction_id,
            bookmaker_id=payload.bookmaker_id,
            market_level=payload.market_level,
            market_type=payload.market_type,
            market_category=payload.market_category,
            selection=payload.selection,
            model_probability=payload.model_probability,
            bookmaker_probability=payload.bookmaker_probability,
            bookmaker_odds=payload.bookmaker_odds,
            edge_pct=payload.edge_pct,
            expected_value=payload.expected_value,
            stake=payload.stake,
            potential_profit=payload.stake * (payload.bookmaker_odds - 1.0),
            bankroll_before=payload.bankroll_before,
            placed_at=payload.placed_at,
            reason=payload.reason,
        )
        self._session.add(bet)
        self._session.commit()
        self._session.refresh(bet)
        self._refresh_run_summary(payload.backtest_run_id)
        return bet

    def settle_bet(self, bet_id: int, result: BacktestBetResult) -> BacktestBet:
        """Settle a simulated bet and update the parent run summary."""

        if result == BacktestBetResult.PENDING:
            raise ValueError("settlement result cannot be pending")

        bet = self._session.get(BacktestBet, bet_id)
        if bet is None:
            raise ValueError(f"Backtest bet id={bet_id} not found")

        if result == BacktestBetResult.WON:
            profit_loss = bet.potential_profit
        elif result == BacktestBetResult.LOST:
            profit_loss = -bet.stake
        else:
            profit_loss = 0.0

        bet.result = result.value
        bet.profit_loss = profit_loss
        bet.settled_at = self._utc_now_string()
        if bet.bankroll_before is not None:
            bet.bankroll_after = bet.bankroll_before + profit_loss

        self._session.commit()
        self._session.refresh(bet)
        self._refresh_run_summary(bet.backtest_run_id)
        return bet

    def complete_run(self, run_id: int) -> BacktestRun:
        """Mark a backtest run as completed and refresh its metrics."""

        run = self._refresh_run_summary(run_id)
        run.completed_at = self._utc_now_string()
        self._session.commit()
        self._session.refresh(run)
        return run

    def _refresh_run_summary(self, run_id: int) -> BacktestRun:
        """Recalculate aggregate metrics from all bets in a run."""

        run = self._session.get(BacktestRun, run_id)
        if run is None:
            raise ValueError(f"Backtest run id={run_id} not found")

        bets = (
            self._session.query(BacktestBet)
            .filter(BacktestBet.backtest_run_id == run_id)
            .all()
        )
        settled_bets = [bet for bet in bets if bet.result != BacktestBetResult.PENDING.value]
        profit_loss = sum(bet.profit_loss or 0.0 for bet in settled_bets)
        total_staked = sum(bet.stake for bet in bets)

        run.total_bets = len(bets)
        run.winning_bets = sum(1 for bet in settled_bets if bet.result == BacktestBetResult.WON.value)
        run.losing_bets = sum(1 for bet in settled_bets if bet.result == BacktestBetResult.LOST.value)
        run.push_bets = sum(1 for bet in settled_bets if bet.result == BacktestBetResult.PUSH.value)
        run.total_staked = total_staked
        run.profit_loss = profit_loss
        run.final_bankroll = run.initial_bankroll + profit_loss
        run.roi_pct = (profit_loss / total_staked) * 100.0 if total_staked > 0 else None

        self._session.commit()
        self._session.refresh(run)
        return run

    @staticmethod
    def _validate_probability(probability: float, field_name: str) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"{field_name} must be between 0 and 1")

    @staticmethod
    def _utc_now_string() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
