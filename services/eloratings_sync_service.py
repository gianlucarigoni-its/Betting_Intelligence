from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models import Sport, Team
from scrapers.eloratings_scraper import EloRatingsScraper, EloTeamRecord
from services.mappers.country_code_mapper import (
    CountryMetadata,
    get_country_metadata_from_elo_code,
)

LOGGER = logging.getLogger(__name__)

SyncAction = Literal["created", "updated", "unchanged"]


@dataclass(slots=True)
class EloSyncResult:
    """Summary of one ELO synchronization execution."""

    total_records: int = 0
    created_teams: int = 0
    updated_teams: int = 0
    unchanged_teams: int = 0
    skipped_records: int = 0
    failed_records: int = 0


class EloRatingsSyncService:
    """Synchronize ELO ratings from eloratings.net into the teams table."""

    NATIONAL_TEAM_TYPE = "national_team"
    FOOTBALL_SPORT_NAME = "football"
    FOOTBALL_SPORT_TYPE = "team_sport"

    def __init__(
        self,
        db_session: Session,
        scraper: Optional[EloRatingsScraper] = None,
    ) -> None:
        self.db_session = db_session
        self.scraper = scraper or EloRatingsScraper()

    def sync_team_ratings(self) -> EloSyncResult:
        """Fetch ELO ratings and upsert them into the teams table."""
        result = EloSyncResult()
        records = self.scraper.scrape_team_ratings()
        result.total_records = len(records)

        LOGGER.info("Starting ELO synchronization for %s records.", result.total_records)

        football_sport = self._get_or_create_football_sport()

        for record in records:
            try:
                metadata = get_country_metadata_from_elo_code(record.country_code)
                if metadata is None:
                    LOGGER.warning(
                        "Skipping country_code=%s because it is not mapped.",
                        record.country_code,
                    )
                    result.skipped_records += 1
                    continue

                action = self._create_or_update_team(
                    record=record,
                    metadata=metadata,
                    football_sport_id=football_sport.id,
                )

                if action == "created":
                    result.created_teams += 1
                elif action == "updated":
                    result.updated_teams += 1
                else:
                    result.unchanged_teams += 1

            except Exception as exc:
                result.failed_records += 1
                LOGGER.exception(
                    "Failed to process country_code=%s: %s",
                    record.country_code,
                    exc,
                )

        self.db_session.commit()
        LOGGER.info("Synchronization committed successfully.")
        LOGGER.info("ELO sync result: %s", result)
        return result

    def _create_or_update_team(
        self,
        record: EloTeamRecord,
        metadata: CountryMetadata,
        football_sport_id: int,
    ) -> SyncAction:
        """Create or update one team using canonical metadata and ELO rating."""
        existing_team = self._get_existing_team(metadata)
        timestamp_now = self._utc_now_string()

        canonical_name = metadata.canonical_name
        source_name = canonical_name
        country_name = canonical_name

        if existing_team is None:
            new_team = Team(
                sport_id=football_sport_id,
                name=canonical_name,
                canonical_name=canonical_name,
                short_name=metadata.fifa_code,
                country=country_name,
                country_code=record.country_code,
                iso_code_2=metadata.iso_code_2,
                fifa_code=metadata.fifa_code,
                type=self.NATIONAL_TEAM_TYPE,
                confederation=metadata.confederation,
                fifa_ranking=None,
                elo_rating=float(record.elo_rating),
                is_fifa_member=metadata.is_fifa_member,
                is_active=True,
                source_name="eloratings",
                source_team_name=source_name,
                founded_year=None,
                last_synced_at=timestamp_now,
            )
            self.db_session.add(new_team)
            LOGGER.info(
                "Created team %s (%s) with ELO=%s.",
                canonical_name,
                record.country_code,
                record.elo_rating,
            )
            return "created"

        has_changes = False

        if existing_team.sport_id != football_sport_id:
            existing_team.sport_id = football_sport_id
            has_changes = True

        if existing_team.name != canonical_name:
            existing_team.name = canonical_name
            has_changes = True

        if existing_team.canonical_name != canonical_name:
            existing_team.canonical_name = canonical_name
            has_changes = True

        if existing_team.short_name != metadata.fifa_code:
            existing_team.short_name = metadata.fifa_code
            has_changes = True

        if existing_team.country != country_name:
            existing_team.country = country_name
            has_changes = True

        if existing_team.country_code != record.country_code:
            existing_team.country_code = record.country_code
            has_changes = True

        if existing_team.iso_code_2 != metadata.iso_code_2:
            existing_team.iso_code_2 = metadata.iso_code_2
            has_changes = True

        if existing_team.fifa_code != metadata.fifa_code:
            existing_team.fifa_code = metadata.fifa_code
            has_changes = True

        if existing_team.type != self.NATIONAL_TEAM_TYPE:
            existing_team.type = self.NATIONAL_TEAM_TYPE
            has_changes = True

        if existing_team.confederation != metadata.confederation:
            existing_team.confederation = metadata.confederation
            has_changes = True

        if existing_team.elo_rating != float(record.elo_rating):
            existing_team.elo_rating = float(record.elo_rating)
            has_changes = True

        if existing_team.is_fifa_member != metadata.is_fifa_member:
            existing_team.is_fifa_member = metadata.is_fifa_member
            has_changes = True

        if existing_team.is_active is not True:
            existing_team.is_active = True
            has_changes = True

        if existing_team.source_name != "eloratings":
            existing_team.source_name = "eloratings"
            has_changes = True

        if existing_team.source_team_name != source_name:
            existing_team.source_team_name = source_name
            has_changes = True

        existing_team.last_synced_at = timestamp_now

        if has_changes:
            LOGGER.info(
                "Updated team %s (%s) with ELO=%s.",
                canonical_name,
                record.country_code,
                record.elo_rating,
            )
            return "updated"

        LOGGER.debug(
            "No changes detected for team %s (%s).",
            canonical_name,
            record.country_code,
        )
        return "unchanged"

    def _get_existing_team(self, metadata: CountryMetadata) -> Optional[Team]:
        """Find a team by the most stable identifiers available."""
        if metadata.fifa_code is not None:
            team = (
                self.db_session.query(Team)
                .filter(Team.fifa_code == metadata.fifa_code)
                .one_or_none()
            )
            if team is not None:
                return team

        if metadata.iso_code_2 is not None:
            team = (
                self.db_session.query(Team)
                .filter(Team.iso_code_2 == metadata.iso_code_2)
                .one_or_none()
            )
            if team is not None:
                return team

        return (
            self.db_session.query(Team)
            .filter(Team.canonical_name == metadata.canonical_name)
            .one_or_none()
        )

    def _get_or_create_football_sport(self) -> Sport:
        """Ensure the football sport row exists before syncing teams."""
        sport = (
            self.db_session.query(Sport)
            .filter(Sport.name == self.FOOTBALL_SPORT_NAME)
            .one_or_none()
        )

        if sport is not None:
            return sport

        sport = Sport(
            name=self.FOOTBALL_SPORT_NAME,
            type=self.FOOTBALL_SPORT_TYPE,
        )
        self.db_session.add(sport)
        self.db_session.flush()

        LOGGER.info("Created missing sport row: %s.", self.FOOTBALL_SPORT_NAME)
        return sport

    @staticmethod
    def _utc_now_string() -> str:
        """Return a UTC timestamp string compatible with the current schema."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def run_elo_ratings_sync() -> EloSyncResult:
    """Run the ELO synchronization using a managed database session."""
    session = SessionLocal()
    try:
        service = EloRatingsSyncService(db_session=session)
        return service.sync_team_ratings()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_result = run_elo_ratings_sync()
    print(sync_result)