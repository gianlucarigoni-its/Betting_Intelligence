"""Build leakage-safe pre-match ELO snapshots for international matches."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import Competition, HistoricalDataImport, Match, TeamRatingSnapshot
from models.historical_elo import HistoricalEloCalculator, HistoricalEloConfig


@dataclass(frozen=True, slots=True)
class NationalEloSnapshotResult:
    matches_seen: int
    snapshots_created: int
    snapshots_updated: int


class NationalEloSnapshotBuilder:
    """Persist pre-match national-team ELO snapshots from stored results."""

    SOURCE_NAME = "historical_international_results"
    RATING_TYPE = "pre_match_elo"

    def __init__(self, session: Session, config: HistoricalEloConfig | None = None) -> None:
        self.session = session
        self.calculator = HistoricalEloCalculator(config)

    def build(self, *, min_date: str | None = None) -> NationalEloSnapshotResult:
        query = (
            self.session.query(Match)
            .join(Competition, Match.competition_id == Competition.id)
            .filter(
                Competition.type == "international",
                Match.status == "finished",
                Match.score_home_ft.is_not(None),
                Match.score_away_ft.is_not(None),
            )
            .order_by(Match.match_date.asc(), Match.id.asc())
        )
        if min_date is not None:
            query = query.filter(Match.match_date >= min_date)
        matches = query.all()
        ratings = self.calculator.build_pre_match_ratings(matches)
        created = 0
        updated = 0
        seen_snapshot_keys: set[tuple[int, str]] = set()
        for match in matches:
            rating = ratings.get(match.id)
            if rating is None:
                continue
            for team_id, value in (
                (match.home_team_id, rating.home_rating),
                (match.away_team_id, rating.away_rating),
            ):
                snapshot_key = (team_id, match.match_date)
                if snapshot_key in seen_snapshot_keys:
                    continue
                seen_snapshot_keys.add(snapshot_key)
                existing = (
                    self.session.query(TeamRatingSnapshot)
                    .filter(
                        TeamRatingSnapshot.team_id == team_id,
                        TeamRatingSnapshot.source_name == self.SOURCE_NAME,
                        TeamRatingSnapshot.rating_type == self.RATING_TYPE,
                        TeamRatingSnapshot.snapshot_date == match.match_date,
                    )
                    .one_or_none()
                )
                if existing is None:
                    self.session.add(TeamRatingSnapshot(
                        team_id=team_id,
                        source_name=self.SOURCE_NAME,
                        rating_type=self.RATING_TYPE,
                        rating_value=value,
                        snapshot_date=match.match_date,
                        valid_from=match.match_date,
                    ))
                    created += 1
                elif abs(existing.rating_value - value) > 1e-9:
                    existing.rating_value = value
                    updated += 1
        self.session.add(HistoricalDataImport(
            source_name=self.SOURCE_NAME,
            dataset_name="National team pre-match ELO snapshots",
            matches_imported=0,
            odds_imported=0,
            ratings_imported=created + updated,
            notes=f"matches_seen={len(matches)}; min_date={min_date or 'all'}",
        ))
        self.session.commit()
        return NationalEloSnapshotResult(
            matches_seen=len(matches),
            snapshots_created=created,
            snapshots_updated=updated,
        )
