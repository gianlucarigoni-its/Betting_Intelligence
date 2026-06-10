"""Tests for Football-Data historical CSV importer."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import HistoricalDataImport, HistoricalOddSnapshot, Match, Team
from historical.football_data_importer import FootballDataImportConfig, FootballDataImporter


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_import_from_csv_text_creates_matches_teams_and_closing_odds() -> None:
    session = build_session()
    importer = FootballDataImporter(session)
    csv_text = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A\n"
        "E0,11/08/2023,Burnley,Man City,0,3,A,8.00,5.50,1.33\n"
        "E0,12/08/2023,Arsenal,Nott'm Forest,2,1,H,1.18,7.00,13.00\n"
    )

    result = importer.import_from_csv_text(
        config=FootballDataImportConfig(
            season_code="2324",
            division_code="E0",
            competition_name="English Premier League",
            country="England",
            season_label="2023/2024",
        ),
        csv_text=csv_text,
        source_url="https://example.test/E0.csv",
    )

    assert result.rows_seen == 2
    assert result.matches_imported == 2
    assert result.odds_imported == 6
    assert session.query(Team).count() == 4
    assert session.query(Match).count() == 2
    assert session.query(HistoricalOddSnapshot).count() == 6
    assert session.query(HistoricalDataImport).one().matches_imported == 2


def test_import_is_idempotent_for_matches_and_odds() -> None:
    session = build_session()
    importer = FootballDataImporter(session)
    config = FootballDataImportConfig(
        season_code="2324",
        division_code="E0",
        competition_name="English Premier League",
        country="England",
        season_label="2023/2024",
    )
    csv_text = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A\n"
        "E0,11/08/2023,Burnley,Man City,0,3,A,8.00,5.50,1.33\n"
    )

    importer.import_from_csv_text(config=config, csv_text=csv_text)
    second_result = importer.import_from_csv_text(config=config, csv_text=csv_text)

    assert second_result.matches_imported == 0
    assert second_result.odds_imported == 0
    assert session.query(Match).count() == 1
    assert session.query(HistoricalOddSnapshot).count() == 3


def test_import_from_csv_text_splits_opening_and_closing_odds() -> None:
    session = build_session()
    importer = FootballDataImporter(session)
    csv_text = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,B365CH,B365CD,B365CA\n"
        "E0,11/08/2023,Burnley,Man City,0,3,A,8.00,5.50,1.33,9.00,5.80,1.30\n"
    )

    result = importer.import_from_csv_text(
        config=FootballDataImportConfig(
            season_code="2324",
            division_code="E0",
            competition_name="English Premier League",
            country="England",
            season_label="2023/2024",
        ),
        csv_text=csv_text,
    )

    snapshots = session.query(HistoricalOddSnapshot).all()
    opening = [snapshot for snapshot in snapshots if snapshot.is_opening]
    closing = [snapshot for snapshot in snapshots if snapshot.is_closing]

    assert result.odds_imported == 6
    assert len(opening) == 3
    assert len(closing) == 3
    assert {snapshot.selection for snapshot in opening} == {"HOME", "DRAW", "AWAY"}
    assert next(snapshot for snapshot in opening if snapshot.selection == "HOME").odd_value == 8.00
    assert next(snapshot for snapshot in closing if snapshot.selection == "HOME").odd_value == 9.00


def test_import_from_csv_text_imports_ou25_and_btts_when_available() -> None:
    session = build_session()
    importer = FootballDataImporter(session)
    csv_text = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,B365CH,B365CD,B365CA,B365>2.5,B365<2.5,B365C>2.5,B365C<2.5,B365GG,B365NG,B365CGG,B365CNG\n"
        "E0,11/08/2023,Burnley,Man City,0,3,A,8.00,5.50,1.33,9.00,5.80,1.30,1.90,1.95,1.85,2.00,1.80,2.05,1.75,2.10\n"
    )

    result = importer.import_from_csv_text(
        config=FootballDataImportConfig(
            season_code="2324",
            division_code="E0",
            competition_name="English Premier League",
            country="England",
            season_label="2023/2024",
        ),
        csv_text=csv_text,
    )

    snapshots = session.query(HistoricalOddSnapshot).all()

    assert result.odds_imported == 14
    assert {snapshot.market_type for snapshot in snapshots} == {"1X2", "OU_2_5", "BTTS"}
    assert {snapshot.selection for snapshot in snapshots if snapshot.market_type == "OU_2_5"} == {"OVER_2_5", "UNDER_2_5"}
    assert {snapshot.selection for snapshot in snapshots if snapshot.market_type == "BTTS"} == {"BTTS_YES", "BTTS_NO"}
