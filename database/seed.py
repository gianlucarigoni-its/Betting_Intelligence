from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal, Sport, Competition, Team


def seed_reference_data(db: Session) -> None:
    if db.query(Sport).count() > 0:
        return

    football = Sport(name="Football", type="team")
    db.add(football)
    db.flush()

    world_cup = Competition(
        sport_id=football.id,
        name="FIFA World Cup 2026",
        short_name="WC2026",
        type="national",
        season="2026",
        region="World",
        is_active=True,
    )
    db.add(world_cup)

    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_reference_data(db)


if __name__ == "__main__":
    main()