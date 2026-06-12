"""Tests for national-team ELO snapshot persistence."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Competition, Match, Sport, Team, TeamRatingSnapshot
from historical.national_elo_snapshot_builder import NationalEloSnapshotBuilder


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_builds_idempotent_pre_match_snapshots() -> None:
    session = _session()
    sport = Sport(name="football", type="team_sport")
    session.add(sport)
    session.flush()
    home = Team(sport_id=sport.id, name="A", canonical_name="A", country="A", type="national_team")
    away = Team(sport_id=sport.id, name="B", canonical_name="B", country="B", type="national_team")
    comp = Competition(sport_id=sport.id, name="Friendly", type="international", season="2024")
    session.add_all([home, away, comp])
    session.flush()
    session.add_all([
        Match(competition_id=comp.id, home_team_id=home.id, away_team_id=away.id, match_date="2024-01-01", score_home_ft=2, score_away_ft=0, status="finished"),
        Match(competition_id=comp.id, home_team_id=home.id, away_team_id=away.id, match_date="2024-02-01", score_home_ft=0, score_away_ft=0, status="finished"),
    ])
    session.commit()

    first = NationalEloSnapshotBuilder(session).build()
    second = NationalEloSnapshotBuilder(session).build()

    assert first.matches_seen == 2
    assert first.snapshots_created == 4
    assert second.snapshots_created == 0
    assert session.query(TeamRatingSnapshot).count() == 4
    second_match_home = (
        session.query(TeamRatingSnapshot)
        .filter(TeamRatingSnapshot.team_id == home.id, TeamRatingSnapshot.snapshot_date == "2024-02-01")
        .one()
    )
    assert second_match_home.rating_value > 1500.0


def test_skips_duplicate_team_date_snapshots_in_one_transaction() -> None:
    session = _session()
    sport = Sport(name="football", type="team_sport")
    session.add(sport)
    session.flush()
    team_a = Team(sport_id=sport.id, name="A", canonical_name="A", country="A", type="national_team")
    team_b = Team(sport_id=sport.id, name="B", canonical_name="B", country="B", type="national_team")
    team_c = Team(sport_id=sport.id, name="C", canonical_name="C", country="C", type="national_team")
    comp = Competition(sport_id=sport.id, name="Friendly", type="international", season="2024")
    session.add_all([team_a, team_b, team_c, comp])
    session.flush()
    session.add_all([
        Match(competition_id=comp.id, home_team_id=team_a.id, away_team_id=team_b.id, match_date="2024-01-01", score_home_ft=1, score_away_ft=0, status="finished"),
        Match(competition_id=comp.id, home_team_id=team_a.id, away_team_id=team_c.id, match_date="2024-01-01", score_home_ft=1, score_away_ft=0, status="finished"),
    ])
    session.commit()

    result = NationalEloSnapshotBuilder(session).build()

    assert result.snapshots_created == 3
    assert session.query(TeamRatingSnapshot).count() == 3
