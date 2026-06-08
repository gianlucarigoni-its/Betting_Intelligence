"""Tests for historical rolling Poisson backtester."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backtesting.historical_poisson_backtester import (
    HistoricalPoissonBacktestConfig,
    HistoricalPoissonBacktester,
)
from database.base import Base
from database.models import BacktestBet, Competition
from historical.football_data_importer import FootballDataImportConfig, FootballDataImporter


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_historical_poisson_backtester_records_and_settles_bets() -> None:
    session = build_session()
    importer = FootballDataImporter(session)
    config = FootballDataImportConfig(
        season_code="2324",
        division_code="T1",
        competition_name="Test League",
        country="England",
        season_label="2023/2024",
    )
    csv_text = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A\n"
        "T1,01/08/2023,Alpha,Beta,3,0,H,1.80,3.60,4.50\n"
        "T1,02/08/2023,Beta,Alpha,0,2,A,4.50,3.60,1.80\n"
        "T1,03/08/2023,Alpha,Gamma,4,1,H,1.80,3.60,4.50\n"
        "T1,04/08/2023,Gamma,Alpha,1,3,A,4.50,3.60,1.80\n"
        "T1,05/08/2023,Beta,Gamma,1,1,D,2.60,3.20,2.70\n"
        "T1,06/08/2023,Gamma,Beta,2,1,H,2.60,3.20,2.70\n"
        "T1,07/08/2023,Alpha,Beta,3,1,H,3.00,3.50,2.20\n"
    )
    importer.import_from_csv_text(config=config, csv_text=csv_text)
    competition = session.query(Competition).filter(Competition.name == "Test League").one()

    run = HistoricalPoissonBacktester(session).run(
        HistoricalPoissonBacktestConfig(
            competition_id=competition.id,
            name="test backtest",
            test_start_date="2023-08-01",
            test_end_date="2023-08-31",
            initial_bankroll=1000.0,
            flat_stake=10.0,
            min_edge_pct=0.0,
            max_edge_pct=None,
            min_model_probability=0.0,
            max_bookmaker_odds=None,
            min_prior_matches=2,
        )
    )

    assert run.total_bets >= 1
    assert run.total_staked == run.total_bets * 10.0
    assert run.final_bankroll is not None
    assert session.query(BacktestBet).count() == run.total_bets
    assert all(bet.result in {"won", "lost"} for bet in session.query(BacktestBet).all())
