"""Importer for men's senior international football results."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from database.models import Competition, HistoricalDataImport, Match, Sport, Team


DEFAULT_RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


@dataclass(frozen=True, slots=True)
class InternationalResultsImportResult:
    rows_seen: int
    matches_imported: int
    teams_created: int
    competitions_created: int
    skipped_rows: int


class InternationalResultsImporter:
    SOURCE_NAME = "martj42/international_results"

    def __init__(self, session: Session) -> None:
        self.session = session

    def import_from_url(self, url: str = DEFAULT_RESULTS_URL, *, min_date: str | None = None) -> InternationalResultsImportResult:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return self.import_from_csv_text(response.text, source_url=url, min_date=min_date)

    def import_from_csv_text(
        self,
        csv_text: str,
        *,
        source_url: str = DEFAULT_RESULTS_URL,
        min_date: str | None = None,
    ) -> InternationalResultsImportResult:
        sport = self._get_or_create_sport()
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        matches_imported = 0
        teams_created = 0
        competitions_created = 0
        skipped_rows = 0

        team_cache: dict[str, Team] = {}
        competition_cache: dict[tuple[str, str], Competition] = {}
        seen_matches: set[tuple[int, int, int, str]] = set()
        for row in rows:
            try:
                match_date = datetime.strptime(row["date"].strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
                if min_date is not None and match_date < min_date:
                    continue
                home_name = row["home_team"].strip()
                away_name = row["away_team"].strip()
                tournament = row["tournament"].strip() or "International Friendly"
                if not home_name or not away_name:
                    raise ValueError("missing team")
                home, home_created = self._get_or_create_team(home_name, sport.id, team_cache)
                away, away_created = self._get_or_create_team(away_name, sport.id, team_cache)
                teams_created += int(home_created) + int(away_created)
                season = match_date[:4]
                competition, competition_created = self._get_or_create_competition(
                    tournament, season, sport.id, competition_cache
                )
                competitions_created += int(competition_created)
                exists = (
                    self.session.query(Match)
                    .filter(
                        Match.competition_id == competition.id,
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date == match_date,
                    )
                    .one_or_none()
                )
                match_key = (competition.id, home.id, away.id, match_date)
                if exists is not None or match_key in seen_matches:
                    continue
                seen_matches.add(match_key)
                neutral = row.get("neutral", "FALSE").strip().upper() == "TRUE"
                self.session.add(
                    Match(
                        competition_id=competition.id,
                        home_team_id=home.id,
                        away_team_id=away.id,
                        match_date=match_date,
                        venue="NEUTRAL" if neutral else None,
                        city=(row.get("city") or "").strip() or None,
                        country=(row.get("country") or "").strip() or None,
                        stage=tournament,
                        score_home_ft=int(row["home_score"]),
                        score_away_ft=int(row["away_score"]),
                        status="finished",
                        source_url=source_url,
                    )
                )
                matches_imported += 1
            except (KeyError, TypeError, ValueError):
                skipped_rows += 1

        self.session.add(
            HistoricalDataImport(
                source_name=self.SOURCE_NAME,
                dataset_name=f"Men international results from {min_date or '1872'}",
                matches_imported=matches_imported,
                odds_imported=0,
                ratings_imported=0,
                notes=source_url,
            )
        )
        self.session.commit()
        return InternationalResultsImportResult(
            rows_seen=len(rows),
            matches_imported=matches_imported,
            teams_created=teams_created,
            competitions_created=competitions_created,
            skipped_rows=skipped_rows,
        )

    def _get_or_create_sport(self) -> Sport:
        sport = self.session.query(Sport).filter(Sport.name == "football").one_or_none()
        if sport is None:
            sport = Sport(name="football", type="team_sport")
            self.session.add(sport)
            self.session.flush()
        return sport

    def _get_or_create_team(self, name: str, sport_id: int, cache: dict[str, Team]) -> tuple[Team, bool]:
        key = name.casefold()
        if key in cache:
            return cache[key], False
        team = (
            self.session.query(Team)
            .filter(Team.canonical_name == name, Team.type == "national_team")
            .order_by(Team.id.asc())
            .first()
        )
        created = False
        if team is None:
            team = Team(
                sport_id=sport_id,
                name=name,
                canonical_name=name,
                short_name=None,
                country=name,
                type="national_team",
                confederation=None,
                is_fifa_member=True,
                is_active=True,
                source_name=self.SOURCE_NAME,
                source_team_name=name,
            )
            self.session.add(team)
            self.session.flush()
            created = True
        cache[key] = team
        return team, created

    def _get_or_create_competition(
        self,
        tournament: str,
        season: str,
        sport_id: int,
        cache: dict[tuple[str, str], Competition],
    ) -> tuple[Competition, bool]:
        key = (tournament, season)
        if key in cache:
            return cache[key], False
        competition = (
            self.session.query(Competition)
            .filter(Competition.name == tournament, Competition.season == season, Competition.type == "international")
            .one_or_none()
        )
        created = False
        if competition is None:
            competition = Competition(
                sport_id=sport_id,
                name=tournament,
                short_name=tournament[:50],
                type="international",
                season=season,
                region="World",
                is_active=False,
            )
            self.session.add(competition)
            self.session.flush()
            created = True
        cache[key] = competition
        return competition, created
