from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import SessionLocal, Sport, Competition


def main() -> None:
    with SessionLocal() as db:
        sports = db.query(Sport).all()
        competitions = db.query(Competition).all()

        print(f"Sports: {len(sports)}")
        for sport in sports:
            print(f"- {sport.id}: {sport.name} ({sport.type})")

        print(f"Competitions: {len(competitions)}")
        for competition in competitions:
            print(f"- {competition.id}: {competition.name} | sport_id={competition.sport_id}")


if __name__ == "__main__":
    main()