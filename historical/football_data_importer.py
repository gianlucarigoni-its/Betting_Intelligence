"""Importer for Football-Data.co.uk historical CSV files."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

import requests
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import (
    Bookmaker,
    Competition,
    HistoricalDataImport,
    HistoricalOddSnapshot,
    Match,
    Sport,
    Team,
)


FOOTBALL_DATA_BASE_URL = "https://www.football-data.co.uk/mmz4281"


@dataclass(frozen=True, slots=True)
class FootballDataImportConfig:
    """Configuration for one Football-Data CSV import."""

    season_code: str
    division_code: str
    competition_name: str
    country: str
    season_label: str
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class FootballDataImportResult:
    """Summary of one historical CSV import."""

    source_name: str
    dataset_name: str
    rows_seen: int
    matches_imported: int
    odds_imported: int
    skipped_rows: int


class FootballDataImporter:
    """Import historical match results and Bet365 1X2 odds."""

    SOURCE_NAME = "football-data.co.uk"
    SPORT_NAME = "football"
    SPORT_TYPE = "team_sport"
    BOOKMAKER_NAME = "Bet365"

    def __init__(self, session: Session) -> None:
        self._session = session

    def import_from_url(self, config: FootballDataImportConfig) -> FootballDataImportResult:
        """Download a Football-Data CSV file and import it."""

        url = config.source_url or self._build_url(config)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return self.import_from_csv_text(config=config, csv_text=response.text, source_url=url)

    def import_from_csv_text(
        self,
        *,
        config: FootballDataImportConfig,
        csv_text: str,
        source_url: str | None = None,
    ) -> FootballDataImportResult:
        """Import matches and closing odds from CSV text."""

        sport = self._get_or_create_sport()
        competition = self._get_or_create_competition(config, sport.id)
        bookmaker = self._get_or_create_bookmaker()

        rows = list(csv.DictReader(io.StringIO(csv_text)))
        matches_imported = 0
        odds_imported = 0
        skipped_rows = 0

        for row in rows:
            if not self._is_complete_result_row(row):
                skipped_rows += 1
                continue

            try:
                home_team = self._get_or_create_team(
                    name=row["HomeTeam"].strip(),
                    sport_id=sport.id,
                    country=config.country,
                )
                away_team = self._get_or_create_team(
                    name=row["AwayTeam"].strip(),
                    sport_id=sport.id,
                    country=config.country,
                )
                match = self._get_or_create_match(
                    competition_id=competition.id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    match_date=self._normalize_date(row["Date"]),
                    score_home_ft=int(row["FTHG"]),
                    score_away_ft=int(row["FTAG"]),
                    source_url=source_url,
                )
                if match.id is None:
                    self._session.flush()
                    matches_imported += 1

                odds_imported += self._import_bet365_1x2_odds(
                    match_id=match.id,
                    bookmaker_id=bookmaker.id,
                    row=row,
                    snapshot_time=match.match_date,
                    source_url=source_url,
                )
            except (KeyError, TypeError, ValueError, IntegrityError):
                self._session.rollback()
                skipped_rows += 1

        import_record = HistoricalDataImport(
            source_name=self.SOURCE_NAME,
            dataset_name=f"{config.competition_name} {config.season_label}",
            matches_imported=matches_imported,
            odds_imported=odds_imported,
            ratings_imported=0,
            notes=f"{config.division_code} {config.season_code}",
        )
        self._session.add(import_record)
        self._session.commit()

        return FootballDataImportResult(
            source_name=self.SOURCE_NAME,
            dataset_name=import_record.dataset_name,
            rows_seen=len(rows),
            matches_imported=matches_imported,
            odds_imported=odds_imported,
            skipped_rows=skipped_rows,
        )

    def _import_bet365_1x2_odds(
        self,
        *,
        match_id: int,
        bookmaker_id: int,
        row: dict[str, str],
        snapshot_time: str,
        source_url: str | None,
    ) -> int:
        odds_map = {
            "HOME": row.get("B365H"),
            "DRAW": row.get("B365D"),
            "AWAY": row.get("B365A"),
        }
        if any(not self._has_value(value) for value in odds_map.values()):
            return 0

        decimal_odds = {
            selection: float(value)
            for selection, value in odds_map.items()
            if value is not None
        }
        implied_probs = {
            selection: 1.0 / odd
            for selection, odd in decimal_odds.items()
        }
        implied_prob_total = sum(implied_probs.values())
        fair_probs = {
            selection: implied_prob / implied_prob_total
            for selection, implied_prob in implied_probs.items()
        }
        overround_pct = (implied_prob_total - 1.0) * 100.0
        imported = 0

        for selection, odd_value in decimal_odds.items():
            exists = (
                self._session.query(HistoricalOddSnapshot)
                .filter(
                    HistoricalOddSnapshot.match_id == match_id,
                    HistoricalOddSnapshot.bookmaker_id == bookmaker_id,
                    HistoricalOddSnapshot.market_type == "1X2",
                    HistoricalOddSnapshot.selection == selection,
                    HistoricalOddSnapshot.snapshot_time == snapshot_time,
                )
                .one_or_none()
            )
            if exists is not None:
                continue

            self._session.add(
                HistoricalOddSnapshot(
                    match_id=match_id,
                    bookmaker_id=bookmaker_id,
                    source_name=self.SOURCE_NAME,
                    market_level=1,
                    market_type="1X2",
                    market_category="match_result",
                    selection=selection,
                    odd_value=odd_value,
                    implied_prob=implied_probs[selection],
                    fair_prob=fair_probs[selection],
                    overround_pct=overround_pct,
                    snapshot_time=snapshot_time,
                    is_opening=False,
                    is_closing=True,
                    source_url=source_url,
                )
            )
            imported += 1

        self._session.flush()
        return imported

    def _get_or_create_match(
        self,
        *,
        competition_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        score_home_ft: int,
        score_away_ft: int,
        source_url: str | None,
    ) -> Match:
        match = (
            self._session.query(Match)
            .filter(
                Match.competition_id == competition_id,
                Match.home_team_id == home_team_id,
                Match.away_team_id == away_team_id,
                Match.match_date == match_date,
            )
            .one_or_none()
        )
        if match is not None:
            match.score_home_ft = score_home_ft
            match.score_away_ft = score_away_ft
            match.status = "finished"
            return match

        match = Match(
            competition_id=competition_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            match_date=match_date,
            score_home_ft=score_home_ft,
            score_away_ft=score_away_ft,
            status="finished",
            source_url=source_url,
        )
        self._session.add(match)
        return match

    def _get_or_create_sport(self) -> Sport:
        sport = (
            self._session.query(Sport)
            .filter(func.lower(Sport.name) == self.SPORT_NAME)
            .first()
        )
        if sport is not None:
            return sport

        sport = Sport(name=self.SPORT_NAME, type=self.SPORT_TYPE)
        self._session.add(sport)
        self._session.flush()
        return sport

    def _get_or_create_competition(self, config: FootballDataImportConfig, sport_id: int) -> Competition:
        competition = (
            self._session.query(Competition)
            .filter(
                Competition.sport_id == sport_id,
                Competition.name == config.competition_name,
                Competition.season == config.season_label,
            )
            .one_or_none()
        )
        if competition is not None:
            return competition

        competition = Competition(
            sport_id=sport_id,
            name=config.competition_name,
            short_name=config.division_code,
            type="league",
            season=config.season_label,
            region=config.country,
            is_active=False,
        )
        self._session.add(competition)
        self._session.flush()
        return competition

    def _get_or_create_team(self, *, name: str, sport_id: int, country: str) -> Team:
        canonical_name = self._canonicalize_team_name(name)
        team = (
            self._session.query(Team)
            .filter(
                Team.sport_id == sport_id,
                Team.canonical_name == canonical_name,
                Team.type == "club_team",
            )
            .one_or_none()
        )
        if team is not None:
            return team

        team = Team(
            sport_id=sport_id,
            name=name,
            canonical_name=canonical_name,
            short_name=None,
            country=country,
            country_code=None,
            iso_code_2=None,
            fifa_code=None,
            type="club_team",
            confederation="UEFA",
            fifa_ranking=None,
            elo_rating=None,
            is_fifa_member=False,
            is_active=True,
            source_name=self.SOURCE_NAME,
            source_team_name=name,
            founded_year=None,
        )
        self._session.add(team)
        self._session.flush()
        return team

    def _get_or_create_bookmaker(self) -> Bookmaker:
        bookmaker = (
            self._session.query(Bookmaker)
            .filter(Bookmaker.name == self.BOOKMAKER_NAME)
            .one_or_none()
        )
        if bookmaker is not None:
            return bookmaker

        bookmaker = Bookmaker(
            name=self.BOOKMAKER_NAME,
            country=None,
            url="https://www.bet365.com",
            scraping_method="historical_csv",
            api_key_env=None,
            is_active=True,
            notes="Imported from Football-Data historical CSV columns B365H/B365D/B365A.",
        )
        self._session.add(bookmaker)
        self._session.flush()
        return bookmaker

    @staticmethod
    def _build_url(config: FootballDataImportConfig) -> str:
        return f"{FOOTBALL_DATA_BASE_URL}/{config.season_code}/{config.division_code}.csv"

    @staticmethod
    def _canonicalize_team_name(name: str) -> str:
        return " ".join(name.strip().split())

    @staticmethod
    def _is_complete_result_row(row: dict[str, str]) -> bool:
        required_fields = ("Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR")
        return all(FootballDataImporter._has_value(row.get(field)) for field in required_fields)

    @staticmethod
    def _has_value(raw_value: str | None) -> bool:
        return raw_value is not None and raw_value.strip() != ""

    @staticmethod
    def _normalize_date(raw_date: str) -> str:
        cleaned_date = raw_date.strip()
        for date_format in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(cleaned_date, date_format).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"Unsupported date format: {raw_date}")
