"""Build national-team pre-match ELO snapshots from imported international results."""

from __future__ import annotations

import argparse

from database.base import SessionLocal
from historical.national_elo_snapshot_builder import NationalEloSnapshotBuilder
from models.historical_elo import HistoricalEloConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-date")
    parser.add_argument("--initial-rating", type=float, default=1500.0)
    parser.add_argument("--k-factor", type=float, default=24.0)
    parser.add_argument("--home-advantage", type=float, default=45.0)
    parser.add_argument("--season-regression", type=float, default=0.05)
    args = parser.parse_args()
    config = HistoricalEloConfig(
        initial_rating=args.initial_rating,
        k_factor=args.k_factor,
        home_advantage=args.home_advantage,
        season_regression=args.season_regression,
    )
    with SessionLocal() as session:
        result = NationalEloSnapshotBuilder(session, config).build(min_date=args.min_date)
    print(result)


if __name__ == "__main__":
    main()
