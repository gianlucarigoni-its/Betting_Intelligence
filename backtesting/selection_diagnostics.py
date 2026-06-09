"""Print betting selection diagnostics for one or more backtest runs."""

from __future__ import annotations

import argparse

from database.base import SessionLocal
from database.models import BacktestBet


def _metrics(bets: list[BacktestBet]) -> dict[str, float | int | None]:
    staked = sum(bet.stake for bet in bets)
    profit_loss = sum(bet.profit_loss or 0.0 for bet in bets)
    wins = sum(1 for bet in bets if bet.result == "won")
    return {
        "bets": len(bets),
        "wins": wins,
        "stake": round(staked, 2),
        "pl": round(profit_loss, 2),
        "roi": round((profit_loss / staked) * 100.0, 2) if staked else None,
        "edge": round(sum(b.edge_pct for b in bets) / len(bets), 2) if bets else 0,
        "odds": round(sum(b.bookmaker_odds for b in bets) / len(bets), 2) if bets else 0,
        "prob": round(sum(b.model_probability for b in bets) / len(bets), 3) if bets else 0,
    }


def _parse_run_ids(value: str) -> list[int]:
    run_ids: list[int] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", maxsplit=1)
            run_ids.extend(range(int(start), int(end) + 1))
        else:
            run_ids.append(int(chunk))
    return run_ids


def _print_group(title: str, rows: list[tuple[str, list[BacktestBet]]]) -> None:
    print(f"\n{title}")
    for label, bets in rows:
        if bets:
            print(f"{label:<16} {_metrics(bets)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, help="Run ids, e.g. 114-138 or 114,115")
    args = parser.parse_args()

    run_ids = _parse_run_ids(args.runs)
    with SessionLocal() as session:
        bets = (
            session.query(BacktestBet)
            .filter(
                BacktestBet.backtest_run_id.in_(run_ids),
                BacktestBet.is_bet.is_(True),
            )
            .all()
        )

    print("TOTAL", _metrics(bets))

    selections = sorted({bet.selection for bet in bets})
    _print_group(
        "BY SELECTION",
        [(selection, [bet for bet in bets if bet.selection == selection]) for selection in selections],
    )

    odds_bins = ((0.0, 1.4), (1.4, 1.6), (1.6, 1.8), (1.8, 2.0), (2.0, 99.0))
    _print_group(
        "BY ODDS",
        [
            (f"{low:.1f}-{high:.1f}", [bet for bet in bets if low <= bet.bookmaker_odds < high])
            for low, high in odds_bins
        ],
    )

    edge_bins = ((0.0, 4.0), (4.0, 5.0), (5.0, 6.0), (6.0, 8.0), (8.0, 10.0), (10.0, 99.0))
    _print_group(
        "BY EDGE",
        [
            (f"{low:.1f}-{high:.1f}", [bet for bet in bets if low <= bet.edge_pct < high])
            for low, high in edge_bins
        ],
    )

    _print_group(
        "BY SELECTION + ODDS",
        [
            (
                f"{selection} {low:.1f}-{high:.1f}",
                [bet for bet in bets if bet.selection == selection and low <= bet.bookmaker_odds < high],
            )
            for selection in selections
            for low, high in odds_bins
        ],
    )

    _print_group(
        "BY SELECTION + EDGE",
        [
            (
                f"{selection} {low:.1f}-{high:.1f}",
                [bet for bet in bets if bet.selection == selection and low <= bet.edge_pct < high],
            )
            for selection in selections
            for low, high in edge_bins
        ],
    )


if __name__ == "__main__":
    main()
