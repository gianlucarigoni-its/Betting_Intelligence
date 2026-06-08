"""Tests for backtesting persistence service."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backtesting.persistence_service import (
    BacktestBetInput,
    BacktestBetResult,
    BacktestPersistenceService,
    BacktestRunInput,
)
from database.base import Base
from database.models import BacktestBet, BacktestRun


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestBacktestPersistenceService:
    def test_create_run_persists_backtest_run(self) -> None:
        session = build_session()
        service = BacktestPersistenceService(session)

        run = service.create_run(
            BacktestRunInput(
                name="ELO Poisson 1X2",
                model_version="1.0",
                model_type="poisson",
                strategy_name="flat_edge_3",
                test_start_date="2024-01-01",
                test_end_date="2024-12-31",
                initial_bankroll=1000.0,
            )
        )

        stored = session.query(BacktestRun).one()
        assert run.id is not None
        assert stored.name == "ELO Poisson 1X2"
        assert stored.final_bankroll == 1000.0
        assert stored.total_bets == 0

    def test_record_bet_persists_pending_bet_and_updates_totals(self) -> None:
        session = build_session()
        service = BacktestPersistenceService(session)
        run = service.create_run(
            BacktestRunInput(
                name="test",
                model_version="1.0",
                model_type="poisson",
                strategy_name="flat",
                test_start_date="2024-01-01",
                test_end_date="2024-12-31",
                initial_bankroll=1000.0,
            )
        )

        bet = service.record_bet(
            BacktestBetInput(
                backtest_run_id=run.id,
                match_id=1,
                market_level=1,
                market_type="1X2",
                market_category="match_result",
                selection="HOME",
                model_probability=0.60,
                bookmaker_probability=0.50,
                bookmaker_odds=2.00,
                edge_pct=10.0,
                expected_value=0.20,
                stake=25.0,
                bankroll_before=1000.0,
                reason="positive edge",
            )
        )

        stored_bet = session.query(BacktestBet).one()
        stored_run = session.query(BacktestRun).one()
        assert bet.id is not None
        assert stored_bet.result == BacktestBetResult.PENDING.value
        assert stored_bet.potential_profit == 25.0
        assert stored_run.total_bets == 1
        assert stored_run.total_staked == 25.0
        assert stored_run.profit_loss == 0.0

    def test_settle_bet_updates_bet_and_run_summary(self) -> None:
        session = build_session()
        service = BacktestPersistenceService(session)
        run = service.create_run(
            BacktestRunInput(
                name="test",
                model_version="1.0",
                model_type="poisson",
                strategy_name="flat",
                test_start_date="2024-01-01",
                test_end_date="2024-12-31",
                initial_bankroll=1000.0,
            )
        )
        bet = service.record_bet(
            BacktestBetInput(
                backtest_run_id=run.id,
                match_id=1,
                market_level=1,
                market_type="1X2",
                market_category="match_result",
                selection="HOME",
                model_probability=0.60,
                bookmaker_probability=0.50,
                bookmaker_odds=2.20,
                edge_pct=14.55,
                stake=50.0,
                bankroll_before=1000.0,
            )
        )

        settled_bet = service.settle_bet(bet.id, BacktestBetResult.WON)
        stored_run = session.query(BacktestRun).one()

        assert settled_bet.result == BacktestBetResult.WON.value
        assert settled_bet.profit_loss == pytest.approx(60.0)
        assert settled_bet.bankroll_after == pytest.approx(1060.0)
        assert stored_run.winning_bets == 1
        assert stored_run.final_bankroll == pytest.approx(1060.0)
        assert stored_run.roi_pct == pytest.approx(120.0)

    def test_create_run_rejects_invalid_bankroll(self) -> None:
        session = build_session()
        service = BacktestPersistenceService(session)

        with pytest.raises(ValueError, match="initial_bankroll"):
            service.create_run(
                BacktestRunInput(
                    name="bad",
                    model_version="1.0",
                    model_type="poisson",
                    strategy_name="flat",
                    test_start_date="2024-01-01",
                    test_end_date="2024-12-31",
                    initial_bankroll=0.0,
                )
            )
