from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Sport, Team
from scrapers.eloratings_scraper import EloTeamRecord
from services.eloratings_sync_service import EloRatingsSyncService


@dataclass(frozen=True, slots=True)
class FakeCountryMetadata:
    canonical_name: str
    iso_code_2: str | None
    fifa_code: str | None
    confederation: str | None
    is_fifa_member: bool


class FakeScraper:
    def __init__(self, records: list[EloTeamRecord]) -> None:
        self._records = records

    def scrape_team_ratings(self) -> list[EloTeamRecord]:
        return self._records


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _create_football_sport(session) -> Sport:
    sport = Sport(name="football", type="team_sport")
    session.add(sport)
    session.commit()
    return sport


def test_create_team_from_elo_record(monkeypatch) -> None:
    session = _build_session()
    _create_football_sport(session)

    records = [EloTeamRecord(rank=1, country_code="ES", elo_rating=2155)]
    scraper = FakeScraper(records)
    service = EloRatingsSyncService(db_session=session, scraper=scraper)

    monkeypatch.setattr(
        "services.eloratings_sync_service.get_country_metadata_from_elo_code",
        lambda code: FakeCountryMetadata(
            canonical_name="Spain",
            iso_code_2="ES",
            fifa_code="ESP",
            confederation="UEFA",
            is_fifa_member=True,
        ),
    )

    result = service.sync_team_ratings()
    team = session.query(Team).filter(Team.fifa_code == "ESP").one()

    assert result.total_records == 1
    assert result.created_teams == 1
    assert result.updated_teams == 0
    assert result.unchanged_teams == 0
    assert result.skipped_records == 0
    assert result.failed_records == 0

    assert team.name == "Spain"
    assert team.canonical_name == "Spain"
    assert team.country == "Spain"
    assert team.country_code == "ES"
    assert team.iso_code_2 == "ES"
    assert team.fifa_code == "ESP"
    assert team.type == "national_team"
    assert team.confederation == "UEFA"
    assert team.elo_rating == 2155.0
    assert team.source_name == "eloratings"
    assert team.source_team_name == "Spain"
    assert team.is_fifa_member is True
    assert team.is_active is True
    assert team.last_synced_at is not None


def test_update_existing_team_elo(monkeypatch) -> None:
    session = _build_session()
    football_sport = _create_football_sport(session)

    existing_team = Team(
        sport_id=football_sport.id,
        name="Spain",
        canonical_name="Spain",
        short_name="ESP",
        country="Spain",
        country_code="ES",
        iso_code_2="ES",
        fifa_code="ESP",
        type="national_team",
        confederation="UEFA",
        fifa_ranking=None,
        elo_rating=2000.0,
        is_fifa_member=True,
        is_active=True,
        source_name="eloratings",
        source_team_name="Spain",
        founded_year=None,
        last_synced_at=None,
    )
    session.add(existing_team)
    session.commit()

    records = [EloTeamRecord(rank=1, country_code="ES", elo_rating=2155)]
    scraper = FakeScraper(records)
    service = EloRatingsSyncService(db_session=session, scraper=scraper)

    monkeypatch.setattr(
        "services.eloratings_sync_service.get_country_metadata_from_elo_code",
        lambda code: FakeCountryMetadata(
            canonical_name="Spain",
            iso_code_2="ES",
            fifa_code="ESP",
            confederation="UEFA",
            is_fifa_member=True,
        ),
    )

    result = service.sync_team_ratings()
    updated_team = session.query(Team).filter(Team.fifa_code == "ESP").one()

    assert result.total_records == 1
    assert result.created_teams == 0
    assert result.updated_teams == 1
    assert result.unchanged_teams == 0
    assert result.skipped_records == 0
    assert result.failed_records == 0

    assert updated_team.elo_rating == 2155.0
    assert updated_team.last_synced_at is not None


def test_keep_team_unchanged_when_nothing_changes(monkeypatch) -> None:
    session = _build_session()
    football_sport = _create_football_sport(session)

    existing_team = Team(
        sport_id=football_sport.id,
        name="Spain",
        canonical_name="Spain",
        short_name="ESP",
        country="Spain",
        country_code="ES",
        iso_code_2="ES",
        fifa_code="ESP",
        type="national_team",
        confederation="UEFA",
        fifa_ranking=None,
        elo_rating=2155.0,
        is_fifa_member=True,
        is_active=True,
        source_name="eloratings",
        source_team_name="Spain",
        founded_year=None,
        last_synced_at="2026-06-08 12:00:00",
    )
    session.add(existing_team)
    session.commit()

    records = [EloTeamRecord(rank=1, country_code="ES", elo_rating=2155)]
    scraper = FakeScraper(records)
    service = EloRatingsSyncService(db_session=session, scraper=scraper)

    monkeypatch.setattr(
        "services.eloratings_sync_service.get_country_metadata_from_elo_code",
        lambda code: FakeCountryMetadata(
            canonical_name="Spain",
            iso_code_2="ES",
            fifa_code="ESP",
            confederation="UEFA",
            is_fifa_member=True,
        ),
    )

    result = service.sync_team_ratings()

    assert result.total_records == 1
    assert result.created_teams == 0
    assert result.updated_teams == 0
    assert result.unchanged_teams == 1
    assert result.skipped_records == 0
    assert result.failed_records == 0


def test_skip_record_when_country_metadata_is_missing(monkeypatch) -> None:
    session = _build_session()
    _create_football_sport(session)

    records = [EloTeamRecord(rank=1, country_code="ZZ", elo_rating=2155)]
    scraper = FakeScraper(records)
    service = EloRatingsSyncService(db_session=session, scraper=scraper)

    monkeypatch.setattr(
        "services.eloratings_sync_service.get_country_metadata_from_elo_code",
        lambda code: None,
    )

    result = service.sync_team_ratings()
    team_count = session.query(Team).count()

    assert result.total_records == 1
    assert result.created_teams == 0
    assert result.updated_teams == 0
    assert result.unchanged_teams == 0
    assert result.skipped_records == 1
    assert result.failed_records == 0
    assert team_count == 0


def test_fallback_lookup_by_fifa_code(monkeypatch) -> None:
    session = _build_session()
    football_sport = _create_football_sport(session)

    existing_team = Team(
        sport_id=football_sport.id,
        name="England",
        canonical_name="England",
        short_name="ENG",
        country="England",
        country_code="GB",
        iso_code_2=None,
        fifa_code="ENG",
        type="national_team",
        confederation="UEFA",
        fifa_ranking=None,
        elo_rating=1900.0,
        is_fifa_member=True,
        is_active=True,
        source_name="eloratings",
        source_team_name="England",
        founded_year=None,
        last_synced_at=None,
    )
    session.add(existing_team)
    session.commit()

    records = [EloTeamRecord(rank=4, country_code="EN", elo_rating=2021)]
    scraper = FakeScraper(records)
    service = EloRatingsSyncService(db_session=session, scraper=scraper)

    monkeypatch.setattr(
        "services.eloratings_sync_service.get_country_metadata_from_elo_code",
        lambda code: FakeCountryMetadata(
            canonical_name="England",
            iso_code_2=None,
            fifa_code="ENG",
            confederation="UEFA",
            is_fifa_member=True,
        ),
    )

    result = service.sync_team_ratings()
    updated_team = session.query(Team).filter(Team.fifa_code == "ENG").one()

    assert result.total_records == 1
    assert result.created_teams == 0
    assert result.updated_teams == 1
    assert result.unchanged_teams == 0
    assert result.skipped_records == 0
    assert result.failed_records == 0
    assert updated_team.elo_rating == 2021.0
    assert updated_team.country_code == "EN"