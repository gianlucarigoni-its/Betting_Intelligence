"""Tests for historical rolling Poisson backtester."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backtesting.historical_poisson_backtester import (
    HistoricalPoissonBacktestConfig,
    HistoricalPoissonBacktester,
)
from database.base import Base
from database.models import BacktestBet, Competition, Match
from models.historical_elo import PreMatchEloRating
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
    all_records = session.query(BacktestBet).all()
    real_bets = [bet for bet in all_records if bet.is_bet]

    assert len(all_records) >= run.total_bets
    assert len(real_bets) == run.total_bets
    assert all(bet.stake > 0 for bet in real_bets)
    assert all(bet.stake == 0 for bet in all_records if not bet.is_bet)
    assert all(bet.result in {"won", "lost"} for bet in all_records)


def test_historical_poisson_backtester_applies_away_specific_filters() -> None:
    session = build_session()
    backtester = HistoricalPoissonBacktester(session)
    selector = backtester._select_best_value_candidate  # type: ignore[attr-defined]
    fake_probabilities = SimpleNamespace(
        home=0.615, draw=0.18, away=0.20,
        lambda_home=1.4, lambda_away=1.0, form_goal_diff_delta=0.1,
    )
    odds_by_selection = {
        "HOME": SimpleNamespace(selection="HOME", odd_value=1.80, bookmaker_id=1),
        "DRAW": SimpleNamespace(selection="DRAW", odd_value=3.50, bookmaker_id=2),
        "AWAY": SimpleNamespace(selection="AWAY", odd_value=1.70, bookmaker_id=3),
    }

    candidate = selector(
        probabilities=fake_probabilities,
        odds_by_selection=odds_by_selection,
        min_edge_pct=5.0,
        max_edge_pct=6.0,
        min_model_probability=0.55,
        max_bookmaker_odds=1.8,
        allow_home_bets=True,
        allow_draw_bets=False,
        home_min_form_goal_diff_delta=None,
        draw_min_edge_pct=4.0,
        draw_max_edge_pct=9.0,
        draw_min_model_probability=0.24,
        draw_max_bookmaker_odds=4.2,
        draw_max_lambda_gap=0.25,
        draw_max_abs_form_goal_diff_delta=0.35,
        away_min_edge_pct=99.0,
        away_min_model_probability=0.58,
        away_max_bookmaker_odds=1.8,
        allow_away_bets=False,
    )

    assert candidate is not None
    assert candidate[0] == "HOME"


def test_historical_poisson_backtester_disables_away_by_default() -> None:
    session = build_session()
    backtester = HistoricalPoissonBacktester(session)
    selector = backtester._select_best_value_candidate  # type: ignore[attr-defined]

    fake_probabilities = SimpleNamespace(
        home=0.61, draw=0.15, away=0.27,
        lambda_home=1.3, lambda_away=1.1, form_goal_diff_delta=0.0,
    )
    odds_by_selection = {
        "HOME": SimpleNamespace(selection="HOME", odd_value=1.80, bookmaker_id=1),
        "DRAW": SimpleNamespace(selection="DRAW", odd_value=3.80, bookmaker_id=2),
        "AWAY": SimpleNamespace(selection="AWAY", odd_value=2.50, bookmaker_id=3),
    }

    candidate = selector(
        probabilities=fake_probabilities,
        odds_by_selection=odds_by_selection,
        min_edge_pct=5.0,
        max_edge_pct=6.0,
        min_model_probability=0.55,
        max_bookmaker_odds=1.8,
        allow_home_bets=True,
        allow_draw_bets=False,
        home_min_form_goal_diff_delta=None,
        draw_min_edge_pct=4.0,
        draw_max_edge_pct=9.0,
        draw_min_model_probability=0.24,
        draw_max_bookmaker_odds=4.2,
        draw_max_lambda_gap=0.25,
        draw_max_abs_form_goal_diff_delta=0.35,
        away_min_edge_pct=99.0,
        away_min_model_probability=0.58,
        away_max_bookmaker_odds=1.8,
        allow_away_bets=False,
    )

    assert candidate is not None
    assert candidate[0] == "HOME"


def test_historical_poisson_backtester_can_select_draw_when_balanced() -> None:
    session = build_session()
    backtester = HistoricalPoissonBacktester(session)
    selector = backtester._select_best_value_candidate  # type: ignore[attr-defined]

    fake_probabilities = SimpleNamespace(
        home=0.34, draw=0.29, away=0.37,
        lambda_home=1.2, lambda_away=1.1, form_goal_diff_delta=0.05,
    )
    odds_by_selection = {
        "HOME": SimpleNamespace(selection="HOME", odd_value=2.20, bookmaker_id=1),
        "DRAW": SimpleNamespace(selection="DRAW", odd_value=3.20, bookmaker_id=2),
        "AWAY": SimpleNamespace(selection="AWAY", odd_value=2.40, bookmaker_id=3),
    }

    candidate = selector(
        probabilities=fake_probabilities,
        odds_by_selection=odds_by_selection,
        min_edge_pct=5.0,
        max_edge_pct=6.0,
        min_model_probability=0.55,
        max_bookmaker_odds=1.8,
        allow_home_bets=True,
        allow_draw_bets=True,
        home_min_form_goal_diff_delta=None,
        draw_min_edge_pct=-3.0,
        draw_max_edge_pct=1.0,
        draw_min_model_probability=0.24,
        draw_max_bookmaker_odds=4.2,
        draw_max_lambda_gap=0.25,
        draw_max_abs_form_goal_diff_delta=0.35,
        away_min_edge_pct=99.0,
        away_min_model_probability=0.58,
        away_max_bookmaker_odds=1.8,
        allow_away_bets=False,
    )

    assert candidate is not None
    assert candidate[0] == "DRAW"


def test_elo_weight_moves_lambdas_in_rating_direction() -> None:
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
        "T1,01/08/2023,Alpha,Beta,2,0,H,1.80,3.60,4.50\n"
        "T1,02/08/2023,Beta,Alpha,0,2,A,4.50,3.60,1.80\n"
        "T1,03/08/2023,Alpha,Gamma,3,1,H,1.80,3.60,4.50\n"
        "T1,04/08/2023,Gamma,Alpha,1,2,A,4.50,3.60,1.80\n"
        "T1,05/08/2023,Beta,Gamma,1,1,D,2.60,3.20,2.70\n"
        "T1,06/08/2023,Gamma,Beta,1,0,H,2.60,3.20,2.70\n"
        "T1,07/08/2023,Alpha,Beta,2,1,H,1.80,3.60,4.50\n"
    )
    importer.import_from_csv_text(config=config, csv_text=csv_text)
    competition = session.query(Competition).filter(Competition.name == "Test League").one()
    target = (
        session.query(Match)
        .filter(Match.competition_id == competition.id)
        .order_by(Match.match_date.desc())
        .first()
    )
    assert target is not None
    backtester = HistoricalPoissonBacktester(session)
    base_config = HistoricalPoissonBacktestConfig(
        competition_id=competition.id,
        name="elo base",
        min_prior_matches=2,
        elo_lambda_weight=0.0,
    )
    weighted_config = HistoricalPoissonBacktestConfig(
        competition_id=competition.id,
        name="elo weighted",
        min_prior_matches=2,
        elo_lambda_weight=0.25,
    )
    strong_home = PreMatchEloRating(
        home_rating=1700.0,
        away_rating=1400.0,
        elo_diff=300.0,
        expected_home_score=0.85,
    )

    base = backtester._estimate_probabilities(  # type: ignore[attr-defined]
        target, base_config, elo_rating=strong_home
    )
    weighted = backtester._estimate_probabilities(  # type: ignore[attr-defined]
        target, weighted_config, elo_rating=strong_home
    )

    assert base is not None
    assert weighted is not None
    assert weighted.lambda_home > base.lambda_home
    assert weighted.lambda_away < base.lambda_away
    assert weighted.elo_diff == 300.0


def test_meta_model_can_gate_otherwise_valid_home_candidate() -> None:
    session = build_session()
    backtester = HistoricalPoissonBacktester(session)
    selector = backtester._select_best_value_candidate  # type: ignore[attr-defined]

    class RejectHomeModel:
        def predict_probability_for_features(self, features):
            return 0.40 if features["selection"] == "HOME" else 0.0

    fake_probabilities = SimpleNamespace(
        home=0.615, draw=0.18, away=0.20,
        lambda_home=1.4, lambda_away=1.0, form_goal_diff_delta=0.1,
    )
    odds_by_selection = {
        "HOME": SimpleNamespace(selection="HOME", odd_value=1.80, bookmaker_id=1, fair_prob=0.54, implied_prob=0.56),
        "DRAW": SimpleNamespace(selection="DRAW", odd_value=3.50, bookmaker_id=2, fair_prob=0.27, implied_prob=0.29),
        "AWAY": SimpleNamespace(selection="AWAY", odd_value=1.70, bookmaker_id=3, fair_prob=0.19, implied_prob=0.59),
    }

    candidate = selector(
        probabilities=fake_probabilities,
        odds_by_selection=odds_by_selection,
        min_edge_pct=5.0,
        max_edge_pct=8.0,
        min_model_probability=0.55,
        max_bookmaker_odds=1.8,
        allow_home_bets=True,
        allow_draw_bets=False,
        home_min_form_goal_diff_delta=None,
        draw_min_edge_pct=4.0,
        draw_max_edge_pct=9.0,
        draw_min_model_probability=0.24,
        draw_max_bookmaker_odds=4.2,
        draw_max_lambda_gap=0.25,
        draw_max_abs_form_goal_diff_delta=0.35,
        away_min_edge_pct=99.0,
        away_min_model_probability=0.58,
        away_max_bookmaker_odds=1.8,
        allow_away_bets=False,
        league_name="Test League",
        selection_meta_model=RejectHomeModel(),
    )

    assert candidate is None
