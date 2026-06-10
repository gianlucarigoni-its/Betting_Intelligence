"""Robust pre-match form features built from chronological results."""

from __future__ import annotations

from dataclasses import dataclass

from database.models import Match


@dataclass(frozen=True, slots=True)
class TeamFormWindow:
    """Recent team performance for one fixed match window."""

    matches: int
    points_per_match: float
    goals_for_per_match: float
    conceded_per_match: float
    goal_diff_per_match: float
    clean_sheet_rate: float


@dataclass(frozen=True, slots=True)
class MatchFormFeatures:
    """Pre-match home/away form features used by selection models."""

    home_5: TeamFormWindow
    home_10: TeamFormWindow
    away_5: TeamFormWindow
    away_10: TeamFormWindow
    home_expected_strength: float
    away_expected_strength: float

    @property
    def goal_diff_delta_5(self) -> float:
        return self.home_5.goal_diff_per_match - self.away_5.goal_diff_per_match

    @property
    def goal_diff_delta_10(self) -> float:
        return self.home_10.goal_diff_per_match - self.away_10.goal_diff_per_match

    @property
    def points_delta_5(self) -> float:
        return self.home_5.points_per_match - self.away_5.points_per_match

    @property
    def conceded_trend_delta(self) -> float:
        home_trend = self.home_5.conceded_per_match - self.home_10.conceded_per_match
        away_trend = self.away_5.conceded_per_match - self.away_10.conceded_per_match
        return home_trend - away_trend

    @property
    def expected_strength_delta(self) -> float:
        return self.home_expected_strength - self.away_expected_strength


def build_match_form_features(
    prior_matches: list[Match],
    home_team_id: int,
    away_team_id: int,
) -> MatchFormFeatures:
    """Return 5/10-match and venue-aware features using only prior matches."""

    home_history = _team_matches(prior_matches, home_team_id)
    away_history = _team_matches(prior_matches, away_team_id)
    return MatchFormFeatures(
        home_5=_window_metrics(home_history, home_team_id, 5),
        home_10=_window_metrics(home_history, home_team_id, 10),
        away_5=_window_metrics(away_history, away_team_id, 5),
        away_10=_window_metrics(away_history, away_team_id, 10),
        home_expected_strength=_venue_strength(
            home_history,
            home_team_id,
            is_home=True,
            window=10,
        ),
        away_expected_strength=_venue_strength(
            away_history,
            away_team_id,
            is_home=False,
            window=10,
        ),
    )


def _team_matches(matches: list[Match], team_id: int) -> list[Match]:
    return sorted(
        (
            match
            for match in matches
            if match.home_team_id == team_id or match.away_team_id == team_id
        ),
        key=lambda item: (item.match_date, item.id),
    )


def _window_metrics(
    matches: list[Match],
    team_id: int,
    window: int,
) -> TeamFormWindow:
    selected = matches[-window:]
    if not selected:
        return TeamFormWindow(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    points = 0.0
    goals_for = 0.0
    goals_against = 0.0
    clean_sheets = 0
    for match in selected:
        scored, conceded = _score_for_team(match, team_id)
        goals_for += scored
        goals_against += conceded
        if conceded == 0:
            clean_sheets += 1
        if scored > conceded:
            points += 3.0
        elif scored == conceded:
            points += 1.0

    count = len(selected)
    return TeamFormWindow(
        matches=count,
        points_per_match=points / count,
        goals_for_per_match=goals_for / count,
        conceded_per_match=goals_against / count,
        goal_diff_per_match=(goals_for - goals_against) / count,
        clean_sheet_rate=clean_sheets / count,
    )


def _venue_strength(
    matches: list[Match],
    team_id: int,
    *,
    is_home: bool,
    window: int,
) -> float:
    venue_matches = [
        match
        for match in matches
        if (match.home_team_id == team_id) == is_home
    ][-window:]
    if not venue_matches:
        return 1.0

    goals_for = 0.0
    goals_against = 0.0
    for match in venue_matches:
        scored, conceded = _score_for_team(match, team_id)
        goals_for += scored
        goals_against += conceded

    # Two pseudo-goals on both sides keep short samples from producing extremes.
    return (goals_for + 2.0) / (goals_against + 2.0)


def _score_for_team(match: Match, team_id: int) -> tuple[float, float]:
    home_goals = float(match.score_home_ft or 0)
    away_goals = float(match.score_away_ft or 0)
    if match.home_team_id == team_id:
        return home_goals, away_goals
    return away_goals, home_goals
