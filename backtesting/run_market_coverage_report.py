"""Report historical odds coverage by market and season."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import func

from database.base import SessionLocal
from database.models import Competition, HistoricalOddSnapshot, Match


@dataclass(frozen=True, slots=True)
class MarketCoverageRow:
    season: str
    market_type: str
    opening_snapshots: int
    closing_snapshots: int


@dataclass(frozen=True, slots=True)
class MarketCoverageSummary:
    market_type: str
    seasons_with_opening: int
    seasons_with_closing: int
    opening_snapshots: int
    closing_snapshots: int


def _load_coverage_rows(session) -> list[MarketCoverageRow]:
    query = (
        session.query(
            Competition.season,
            HistoricalOddSnapshot.market_type,
            func.sum(func.cast(HistoricalOddSnapshot.is_opening, __import__("sqlalchemy").Integer)),
            func.sum(func.cast(HistoricalOddSnapshot.is_closing, __import__("sqlalchemy").Integer)),
        )
        .join(Match, Match.competition_id == Competition.id)
        .join(HistoricalOddSnapshot, HistoricalOddSnapshot.match_id == Match.id)
        .group_by(Competition.season, HistoricalOddSnapshot.market_type)
        .order_by(Competition.season, HistoricalOddSnapshot.market_type)
    )
    return [
        MarketCoverageRow(
            season=season,
            market_type=market_type,
            opening_snapshots=int(opening or 0),
            closing_snapshots=int(closing or 0),
        )
        for season, market_type, opening, closing in query.all()
    ]


def _summaries(rows: list[MarketCoverageRow]) -> list[MarketCoverageSummary]:
    markets = sorted({row.market_type for row in rows})
    summaries: list[MarketCoverageSummary] = []
    for market in markets:
        market_rows = [row for row in rows if row.market_type == market]
        summaries.append(
            MarketCoverageSummary(
                market_type=market,
                seasons_with_opening=sum(1 for row in market_rows if row.opening_snapshots > 0),
                seasons_with_closing=sum(1 for row in market_rows if row.closing_snapshots > 0),
                opening_snapshots=sum(row.opening_snapshots for row in market_rows),
                closing_snapshots=sum(row.closing_snapshots for row in market_rows),
            )
        )
    return summaries


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-type", help="Optional market to gate, e.g. OU_2_5")
    parser.add_argument("--min-opening-seasons", type=int, default=5)
    parser.add_argument("--min-closing-seasons", type=int, default=5)
    parser.add_argument("--min-opening-snapshots", type=int, default=1000)
    parser.add_argument("--min-closing-snapshots", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    with SessionLocal() as session:
        rows = _load_coverage_rows(session)

    print("BY_SEASON")
    for row in rows:
        print(
            f"{row.season:<10} {row.market_type:<8} "
            f"opening={row.opening_snapshots:<5} closing={row.closing_snapshots:<5}"
        )

    print("\nSUMMARY")
    selected_summary: MarketCoverageSummary | None = None
    for summary in _summaries(rows):
        print(
            f"{summary.market_type:<8} opening_seasons={summary.seasons_with_opening:<3} "
            f"closing_seasons={summary.seasons_with_closing:<3} "
            f"opening={summary.opening_snapshots:<6} closing={summary.closing_snapshots:<6}"
        )
        if summary.market_type == args.market_type:
            selected_summary = summary

    if args.market_type:
        if selected_summary is None:
            print(f"\nCOVERAGE_GATE=FAIL market {args.market_type} not found")
            return
        failures: list[str] = []
        if selected_summary.seasons_with_opening < args.min_opening_seasons:
            failures.append(
                f"opening seasons {selected_summary.seasons_with_opening} < {args.min_opening_seasons}"
            )
        if selected_summary.seasons_with_closing < args.min_closing_seasons:
            failures.append(
                f"closing seasons {selected_summary.seasons_with_closing} < {args.min_closing_seasons}"
            )
        if selected_summary.opening_snapshots < args.min_opening_snapshots:
            failures.append(
                f"opening snapshots {selected_summary.opening_snapshots} < {args.min_opening_snapshots}"
            )
        if selected_summary.closing_snapshots < args.min_closing_snapshots:
            failures.append(
                f"closing snapshots {selected_summary.closing_snapshots} < {args.min_closing_snapshots}"
            )
        print(f"\nCOVERAGE_GATE={'FAIL' if failures else 'PASS'}")
        for failure in failures:
            print(f"- {failure}")


if __name__ == "__main__":
    main()
