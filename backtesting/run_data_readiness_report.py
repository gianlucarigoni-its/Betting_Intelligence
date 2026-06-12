"""Report data readiness by competition type for prediction and betting use."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import Integer, func

from database.base import SessionLocal
from database.models import Competition, HistoricalOddSnapshot, Match, TeamRatingSnapshot


@dataclass(frozen=True, slots=True)
class DataReadinessRow:
    competition_type: str
    matches: int
    odds_snapshots: int
    opening_snapshots: int
    closing_snapshots: int
    rating_snapshots: int


@dataclass(frozen=True, slots=True)
class DataReadinessSummary:
    competition_type: str
    matches: int
    odds_snapshots: int
    opening_snapshots: int
    closing_snapshots: int
    rating_snapshots: int

    @property
    def prediction_ready(self) -> bool:
        return self.matches > 0 and self.rating_snapshots > 0

    @property
    def betting_ready(self) -> bool:
        return self.prediction_ready and self.opening_snapshots > 0 and self.closing_snapshots > 0


def _load_rows(session) -> list[DataReadinessRow]:
    query = (
        session.query(
            Competition.type,
            func.count(func.distinct(Match.id)),
            func.count(func.distinct(HistoricalOddSnapshot.id)),
            func.sum(func.cast(HistoricalOddSnapshot.is_opening, Integer)),
            func.sum(func.cast(HistoricalOddSnapshot.is_closing, Integer)),
            func.count(func.distinct(TeamRatingSnapshot.id)),
        )
        .join(Match, Match.competition_id == Competition.id)
        .outerjoin(HistoricalOddSnapshot, HistoricalOddSnapshot.match_id == Match.id)
        .outerjoin(TeamRatingSnapshot, TeamRatingSnapshot.team_id.in_([Match.home_team_id, Match.away_team_id]))
        .group_by(Competition.type)
        .order_by(Competition.type)
    )
    return [
        DataReadinessRow(
            competition_type=competition_type,
            matches=int(matches or 0),
            odds_snapshots=int(odds_snapshots or 0),
            opening_snapshots=int(opening or 0),
            closing_snapshots=int(closing or 0),
            rating_snapshots=int(ratings or 0),
        )
        for competition_type, matches, odds_snapshots, opening, closing, ratings in query.all()
    ]


def _summaries(rows: list[DataReadinessRow]) -> list[DataReadinessSummary]:
    return [
        DataReadinessSummary(
            competition_type=row.competition_type,
            matches=row.matches,
            odds_snapshots=row.odds_snapshots,
            opening_snapshots=row.opening_snapshots,
            closing_snapshots=row.closing_snapshots,
            rating_snapshots=row.rating_snapshots,
        )
        for row in rows
    ]


def main() -> None:
    with SessionLocal() as session:
        rows = _load_rows(session)

    print("COMPETITION_TYPE  MATCHES  ODDS  OPENING  CLOSING  RATINGS  PRED_READY  BET_READY")
    for row in _summaries(rows):
        print(
            f"{row.competition_type:<16} {row.matches:<7} {row.odds_snapshots:<5} "
            f"{row.opening_snapshots:<8} {row.closing_snapshots:<8} {row.rating_snapshots:<8} "
            f"{str(row.prediction_ready):<10} {str(row.betting_ready):<9}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.parse_args()
    main()
