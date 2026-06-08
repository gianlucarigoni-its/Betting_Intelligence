from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models import ScrapingLog, Sport, Team
from scrapers.eloratings_scraper import EloRatingsScraper, EloTeamRecord
from services.mappers.country_code_mapper import get_country_name_from_elo_code


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EloSyncResult:
    """Summary of one synchronization run."""

    total_records: int = 0
    created_teams: int = 0
    updated_teams: int = 0
    unchanged_teams: int = 0
    skipped_records: int = 0
    failed_records: int = 0


class EloRatingsSyncService:
    """Synchronize ELO ratings into the teams table with add-or-update behavior."""

    SOURCE_NAME = "eloratings.net"

    def __init__(self, db_session: Optional[Session] = None) -> None:
        self.db_session = db_session or SessionLocal()
        self.scraper = EloRatingsScraper()

    def sync_team_ratings(self, dry_run: bool = True) -> EloSyncResult:
      """
      Synchronize ELO team ratings into the database.

      Args:
          dry_run: If True, no persistent DB changes are committed.

      Returns:
          EloSyncResult: summary of sync execution.
      """
      result = EloSyncResult()
      status = "SUCCESS"
      error_message: str | None = None
      started_at = time.perf_counter()

      try:
          football_sport = self._get_football_sport()
          records = self.scraper.scrape_team_ratings()
          result.total_records = len(records)

          for record in records:
              try:
                  was_processed = self._create_or_update_team(
                      record=record,
                      football_sport_id=football_sport.id,
                      result=result,
                  )
                  if not was_processed:
                      result.skipped_records += 1
              except Exception as record_error:  # noqa: BLE001
                  result.failed_records += 1
                  LOGGER.exception(
                      "Failed to process country_code=%s: %s",
                      record.country_code,
                      record_error,
                  )

          if dry_run:
              self.db_session.rollback()
              LOGGER.info("Dry-run completed. Transaction rolled back.")
          else:
              self.db_session.commit()
              LOGGER.info("Synchronization committed successfully.")

      except Exception as sync_error:  # noqa: BLE001
          self.db_session.rollback()
          status = "FAILED"
          error_message = str(sync_error)
          LOGGER.exception("ELO synchronization failed: %s", sync_error)
          raise
      finally:
          duration_seconds = round(time.perf_counter() - started_at, 3)
          self._write_scraping_log(
              result=result,
              dry_run=dry_run,
              status=status,
              error_message=error_message,
              duration_seconds=duration_seconds,
          )
          self.db_session.close()

      return result

    def _create_or_update_team(
        self,
        record: EloTeamRecord,
        football_sport_id: int,
        result: EloSyncResult,
    ) -> bool:
        """
        Create a new team or update an existing one based on country_code.
        """
        country_name = get_country_name_from_elo_code(record.country_code)
        if country_name is None:
            LOGGER.warning(
                "Skipping unknown country_code=%s because no mapper entry exists.",
                record.country_code,
            )
            return False

        team = self._find_team_by_country_code(record.country_code)

        if team is None:
            team = Team(
                sport_id=football_sport_id,
                name=country_name,
                short_name=record.country_code,
                country=country_name,
                country_code=record.country_code,
                type="national_team",
                confederation=None,
                fifa_ranking=None,
                elo_rating=float(record.elo_rating),
                founded_year=None,
            )
            self.db_session.add(team)
            result.created_teams += 1

            LOGGER.info(
                "Created new team name=%s country_code=%s elo_rating=%s",
                team.name,
                team.country_code,
                team.elo_rating,
            )
            return True

        was_changed = False

        if team.name != country_name:
            team.name = country_name
            was_changed = True

        if team.country != country_name:
            team.country = country_name
            was_changed = True

        if team.short_name != record.country_code:
            team.short_name = record.country_code
            was_changed = True

        if team.elo_rating != float(record.elo_rating):
            team.elo_rating = float(record.elo_rating)
            was_changed = True

        if team.type != "national_team":
            team.type = "national_team"
            was_changed = True

        if was_changed:
            result.updated_teams += 1
            LOGGER.info(
                "Updated existing team name=%s country_code=%s elo_rating=%s",
                team.name,
                team.country_code,
                team.elo_rating,
            )
        else:
            result.unchanged_teams += 1
            LOGGER.info(
                "No changes needed for team name=%s country_code=%s",
                team.name,
                team.country_code,
            )

        return True

    def _find_team_by_country_code(self, country_code: str) -> Team | None:
        """Find a team by country_code."""
        statement: Select[tuple[Team]] = select(Team).where(
            Team.country_code == country_code
        )
        return self.db_session.execute(statement).scalar_one_or_none()

    def _get_football_sport(self) -> Sport:
        """Return the Football sport row from the database."""
        statement: Select[tuple[Sport]] = select(Sport).where(Sport.name == "Football")
        sport = self.db_session.execute(statement).scalar_one_or_none()

        if sport is None:
            raise ValueError(
                "Sport 'Football' not found. Run database seed before synchronization."
            )

        return sport

    def _write_scraping_log(
      self,
      result: EloSyncResult,
      dry_run: bool,
      status: str,
      error_message: str | None,
      duration_seconds: float,
  ) -> None:
      """Write one scraping log entry aligned with the ScrapingLog ORM model."""
      try:
          resolved_status = f"{status}_DRY_RUN" if dry_run and status == "SUCCESS" else status

          log_entry = ScrapingLog(
              source_name=self.SOURCE_NAME,
              url="https://eloratings.net/World.tsv",
              status=resolved_status,
              rows_fetched=result.total_records,
              error_message=error_message,
              duration_seconds=duration_seconds,
          )
          self.db_session.add(log_entry)
          self.db_session.commit()

      except SQLAlchemyError as log_error:
          self.db_session.rollback()
          LOGGER.exception("Failed to persist scraping log: %s", log_error)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    service = EloRatingsSyncService()
    result = service.sync_team_ratings(dry_run=False)
    print(result)