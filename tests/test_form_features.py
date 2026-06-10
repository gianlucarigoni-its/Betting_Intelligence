"""Tests for robust pre-match form features."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from models.form_features import build_match_form_features


def _match(match_id: int, home_id: int, away_id: int, home_goals: int, away_goals: int):
    return SimpleNamespace(
        id=match_id,
        match_date=f"2023-08-{match_id:02d}",
        home_team_id=home_id,
        away_team_id=away_id,
        score_home_ft=home_goals,
        score_away_ft=away_goals,
    )


def test_form_features_use_distinct_five_and_ten_match_windows() -> None:
    matches = []
    for index in range(1, 6):
        matches.append(_match(index, 1, 100 + index, 0, 2))
    for index in range(6, 11):
        matches.append(_match(index, 1, 100 + index, 2, 0))
    for index in range(11, 21):
        matches.append(_match(index, 200 + index, 2, 1, 1))

    features = build_match_form_features(matches, home_team_id=1, away_team_id=2)

    assert features.home_5.points_per_match == pytest.approx(3.0)
    assert features.home_5.goal_diff_per_match == pytest.approx(2.0)
    assert features.home_5.clean_sheet_rate == pytest.approx(1.0)
    assert features.home_10.points_per_match == pytest.approx(1.5)
    assert features.home_10.goal_diff_per_match == pytest.approx(0.0)
    assert features.away_5.points_per_match == pytest.approx(1.0)
    assert features.goal_diff_delta_5 == pytest.approx(2.0)
    assert features.points_delta_5 == pytest.approx(2.0)


def test_form_features_are_neutral_without_history() -> None:
    features = build_match_form_features([], home_team_id=1, away_team_id=2)

    assert features.home_5.matches == 0
    assert features.away_10.matches == 0
    assert features.home_expected_strength == pytest.approx(1.0)
    assert features.away_expected_strength == pytest.approx(1.0)
    assert features.expected_strength_delta == pytest.approx(0.0)
