"""Leakage-safe historical ELO ratings for football matches."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from database.models import Match


@dataclass(frozen=True, slots=True)
class HistoricalEloConfig:
    """Configuration for the chronological ELO calculator."""

    initial_rating: float = 1500.0
    k_factor: float = 24.0
    home_advantage: float = 65.0
    season_regression: float = 0.15
    max_margin_multiplier: float = 1.5


@dataclass(frozen=True, slots=True)
class PreMatchEloRating:
    """ELO state immediately before a match starts."""

    home_rating: float
    away_rating: float
    elo_diff: float
    expected_home_score: float


class HistoricalEloCalculator:
    """Build pre-match ELO ratings using only earlier match results."""

    def __init__(self, config: HistoricalEloConfig | None = None) -> None:
        self.config = config or HistoricalEloConfig()

    def build_pre_match_ratings(
        self,
        matches: Iterable[Match],
    ) -> dict[int, PreMatchEloRating]:
        ratings: dict[int, float] = {}
        seen_teams: set[int] = set()
        seen_team_competitions: set[tuple[int, int]] = set()
        snapshots: dict[int, PreMatchEloRating] = {}

        ordered = sorted(matches, key=lambda item: (item.match_date, item.id))
        for match in ordered:
            home_rating = self._rating_for_match(
                ratings,
                seen_teams,
                seen_team_competitions,
                match.home_team_id,
                match.competition_id,
            )
            away_rating = self._rating_for_match(
                ratings,
                seen_teams,
                seen_team_competitions,
                match.away_team_id,
                match.competition_id,
            )
            expected_home = self._expected_home_score(home_rating, away_rating)
            snapshots[match.id] = PreMatchEloRating(
                home_rating=home_rating,
                away_rating=away_rating,
                elo_diff=home_rating - away_rating,
                expected_home_score=expected_home,
            )

            if match.score_home_ft is None or match.score_away_ft is None:
                continue

            actual_home = self._actual_home_score(
                match.score_home_ft,
                match.score_away_ft,
            )
            margin_multiplier = self._margin_multiplier(
                abs(match.score_home_ft - match.score_away_ft)
            )
            adjustment = (
                self.config.k_factor
                * margin_multiplier
                * (actual_home - expected_home)
            )
            ratings[match.home_team_id] = home_rating + adjustment
            ratings[match.away_team_id] = away_rating - adjustment
            seen_teams.update((match.home_team_id, match.away_team_id))

        return snapshots

    def _rating_for_match(
        self,
        ratings: dict[int, float],
        seen_teams: set[int],
        seen_team_competitions: set[tuple[int, int]],
        team_id: int,
        competition_id: int,
    ) -> float:
        rating = ratings.get(team_id, self.config.initial_rating)
        team_competition = (team_id, competition_id)
        if team_competition not in seen_team_competitions:
            if team_id in seen_teams:
                rating = (
                    rating * (1.0 - self.config.season_regression)
                    + self.config.initial_rating * self.config.season_regression
                )
                ratings[team_id] = rating
            seen_team_competitions.add(team_competition)
        return rating

    def _expected_home_score(self, home_rating: float, away_rating: float) -> float:
        adjusted_home = home_rating + self.config.home_advantage
        return 1.0 / (1.0 + math.pow(10.0, (away_rating - adjusted_home) / 400.0))

    def _margin_multiplier(self, goal_difference: int) -> float:
        if goal_difference <= 1:
            return 1.0
        multiplier = 1.0 + 0.25 * math.log(goal_difference)
        return min(multiplier, self.config.max_margin_multiplier)

    @staticmethod
    def _actual_home_score(home_goals: int, away_goals: int) -> float:
        if home_goals > away_goals:
            return 1.0
        if home_goals < away_goals:
            return 0.0
        return 0.5
