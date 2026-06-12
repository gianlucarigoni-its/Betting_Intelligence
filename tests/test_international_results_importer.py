"""Tests for international results importer."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Competition, Match, Team
from historical.international_results_importer import InternationalResultsImporter


def test_imports_international_results_and_neutral_flag() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    csv_text = (
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2022-12-18,Argentina,France,3,3,FIFA World Cup,Lusail,Qatar,TRUE\n"
        "2023-03-23,Italy,England,1,2,UEFA Euro qualification,Naples,Italy,FALSE\n"
    )

    result = InternationalResultsImporter(session).import_from_csv_text(csv_text, min_date="2020-01-01")

    assert result.matches_imported == 2
    assert result.teams_created == 4
    assert session.query(Team).filter(Team.type == "national_team").count() == 4
    assert session.query(Competition).filter(Competition.type == "international").count() == 2
    final = session.query(Match).filter(Match.stage == "FIFA World Cup").one()
    assert final.venue == "NEUTRAL"


def test_prefers_existing_national_team_when_name_is_duplicated() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    from database.models import Sport
    sport = Sport(name="football", type="team_sport")
    session.add(sport)
    session.flush()
    session.add(Team(sport_id=sport.id, name="France", canonical_name="France", country="France", type="club", is_fifa_member=False, is_active=True))
    session.add(Team(sport_id=sport.id, name="France", canonical_name="France", country="France", type="national_team", is_fifa_member=True, is_active=True))
    session.commit()
    csv_text = (
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2022-12-18,Argentina,France,3,3,FIFA World Cup,Lusail,Qatar,TRUE\n"
    )
    result = InternationalResultsImporter(session).import_from_csv_text(csv_text, min_date="2020-01-01")
    assert result.matches_imported == 1
    assert session.query(Team).filter(Team.canonical_name == "France", Team.type == "national_team").count() == 1
