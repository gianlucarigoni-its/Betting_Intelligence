"""Tests for leakage-safe historical ELO ratings."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from models.historical_elo import HistoricalEloCalculator, HistoricalEloConfig


def _match(
    match_id: int,
    date: str,
    home_id: int,
    away_id: int,
    home_goals: int,
    away_goals: int,
    competition_id: int = 1,
):
    return SimpleNamespace(
        id=match_id,
        match_date=date,
        home_team_id=home_id,
        away_team_id=away_id,
        score_home_ft=home_goals,
        score_away_ft=away_goals,
        competition_id=competition_id,
    )


def test_elo_snapshots_are_strictly_pre_match() -> None:
    matches = [
        _match(1, "2023-08-01", 1, 2, 3, 0),
        _match(2, "2023-08-08", 1, 2, 0, 4),
    ]
    snapshots = HistoricalEloCalculator().build_pre_match_ratings(matches)

    assert snapshots[1].home_rating == pytest.approx(1500.0)
    assert snapshots[1].away_rating == pytest.approx(1500.0)
    assert snapshots[2].home_rating > snapshots[2].away_rating


def test_future_result_does_not_change_current_pre_match_elo() -> None:
    first = _match(1, "2023-08-01", 1, 2, 2, 0)
    second_home_win = _match(2, "2023-08-08", 1, 2, 5, 0)
    second_away_win = _match(2, "2023-08-08", 1, 2, 0, 5)
    calculator = HistoricalEloCalculator()

    before_home_win = calculator.build_pre_match_ratings([first, second_home_win])[2]
    before_away_win = calculator.build_pre_match_ratings([first, second_away_win])[2]

    assert before_home_win == before_away_win


def test_new_season_regresses_rating_toward_mean() -> None:
    config = HistoricalEloConfig(season_regression=0.25)
    matches = [
        _match(1, "2023-08-01", 1, 2, 4, 0, competition_id=1),
        _match(2, "2023-08-08", 1, 2, 2, 0, competition_id=1),
        _match(3, "2024-08-01", 1, 2, 0, 0, competition_id=2),
    ]
    snapshots = HistoricalEloCalculator(config).build_pre_match_ratings(matches)

    end_previous_season_gap = snapshots[2].home_rating - snapshots[2].away_rating
    new_season_gap = snapshots[3].home_rating - snapshots[3].away_rating
    assert 0.0 < new_season_gap < end_previous_season_gap * 2.0
