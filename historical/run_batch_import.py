"""CLI wrapper for the football-data batch importer."""

from __future__ import annotations

import argparse
import logging

from dataclasses import replace

from historical.batch_importer import LEAGUE_CATALOG, run_batch_import


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--leagues",
        help="Codici lega separati da virgola (es. E0,SP1). Default: tutte.",
    )
    parser.add_argument(
        "--seasons",
        help="Codici stagione separati da virgola (es. 1819,1718). Default: tutte.",
    )
    parser.add_argument("--delay-seconds", type=float, default=2.5)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    args = _parse_args()
    league_codes = [c.strip() for c in args.leagues.split(",")] if args.leagues else None
    season_codes = [s.strip() for s in args.seasons.split(",")] if args.seasons else None

    leagues = []
    for league in LEAGUE_CATALOG:
        if league_codes and league.code not in league_codes:
            continue
        seasons = (
            tuple(season for season in league.seasons if season in season_codes)
            if season_codes
            else league.seasons
        )
        if seasons:
            leagues.append(replace(league, seasons=seasons))

    summary = run_batch_import(leagues=leagues, delay_seconds=args.delay_seconds)
    summary.print_report()


if __name__ == "__main__":
    main()
