"""Stability and closing-line diagnostics for backtest runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from database.models import BacktestBet, Competition, HistoricalOddSnapshot, Match


@dataclass(frozen=True, slots=True)
class StabilityBetRow:
    bet: BacktestBet
    match: Match
    competition: Competition


@dataclass(frozen=True, slots=True)
class StabilitySliceMetrics:
    label: str
    bets: int
    wins: int
    hit_rate: float
    total_staked: float
    profit_loss: float
    roi_pct: float | None
    max_drawdown: float
    avg_clv_pct: float | None
    clv_count: int


@dataclass(frozen=True, slots=True)
class BacktestStabilityReport:
    total: StabilitySliceMetrics
    by_season: tuple[StabilitySliceMetrics, ...]
    by_league: tuple[StabilitySliceMetrics, ...]
    by_selection: tuple[StabilitySliceMetrics, ...]


class BacktestStabilityAnalyzer:
    """Compute temporal and market-stability diagnostics for stored bets."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def build_report(
        self,
        *,
        run_ids: Iterable[int] | None = None,
        min_bets: int = 0,
    ) -> BacktestStabilityReport:
        rows = self._load_rows(run_ids=run_ids)
        closing_odds = self._load_closing_odds(rows)
        return BacktestStabilityReport(
            total=self._metrics_for("TOTAL", rows, closing_odds),
            by_season=self._grouped_metrics(
                rows,
                closing_odds,
                min_bets=min_bets,
                label_for=lambda row: row.competition.season,
            ),
            by_league=self._grouped_metrics(
                rows,
                closing_odds,
                min_bets=min_bets,
                label_for=lambda row: row.competition.name,
            ),
            by_selection=self._grouped_metrics(
                rows,
                closing_odds,
                min_bets=min_bets,
                label_for=lambda row: row.bet.selection,
            ),
        )

    def _load_rows(self, *, run_ids: Iterable[int] | None) -> list[StabilityBetRow]:
        query = (
            self._session.query(BacktestBet, Match, Competition)
            .join(Match, BacktestBet.match_id == Match.id)
            .join(Competition, Match.competition_id == Competition.id)
            .filter(
                BacktestBet.is_bet.is_(True),
                BacktestBet.result != "pending",
            )
            .order_by(Match.match_date.asc(), Match.id.asc(), BacktestBet.id.asc())
        )
        if run_ids is not None:
            query = query.filter(BacktestBet.backtest_run_id.in_(list(run_ids)))
        return [StabilityBetRow(bet=bet, match=match, competition=competition) for bet, match, competition in query.all()]

    def _load_closing_odds(
        self,
        rows: list[StabilityBetRow],
    ) -> dict[tuple[int, str, str, int | None], HistoricalOddSnapshot]:
        match_ids = sorted({row.bet.match_id for row in rows})
        if not match_ids:
            return {}
        snapshots = (
            self._session.query(HistoricalOddSnapshot)
            .filter(
                HistoricalOddSnapshot.match_id.in_(match_ids),
                HistoricalOddSnapshot.is_closing.is_(True),
            )
            .all()
        )
        return {
            (item.match_id, item.market_type, item.selection, item.bookmaker_id): item
            for item in snapshots
        }

    def _grouped_metrics(
        self,
        rows: list[StabilityBetRow],
        closing_odds: dict[tuple[int, str, str, int | None], HistoricalOddSnapshot],
        *,
        min_bets: int,
        label_for,
    ) -> tuple[StabilitySliceMetrics, ...]:
        labels = sorted({label_for(row) for row in rows})
        metrics = [
            self._metrics_for(label, [row for row in rows if label_for(row) == label], closing_odds)
            for label in labels
        ]
        return tuple(item for item in metrics if item.bets >= min_bets)

    @classmethod
    def _metrics_for(
        cls,
        label: str,
        rows: list[StabilityBetRow],
        closing_odds: dict[tuple[int, str, str, int | None], HistoricalOddSnapshot],
    ) -> StabilitySliceMetrics:
        if not rows:
            return StabilitySliceMetrics(label, 0, 0, 0.0, 0.0, 0.0, None, 0.0, None, 0)

        wins = sum(1 for row in rows if row.bet.result == "won")
        total_staked = sum(row.bet.stake for row in rows)
        profit_loss = sum(row.bet.profit_loss or 0.0 for row in rows)
        clv_values = [
            value
            for value in (
                cls._clv_pct(row.bet, closing_odds) for row in rows
            )
            if value is not None
        ]
        return StabilitySliceMetrics(
            label=label,
            bets=len(rows),
            wins=wins,
            hit_rate=wins / len(rows),
            total_staked=total_staked,
            profit_loss=profit_loss,
            roi_pct=(profit_loss / total_staked) * 100.0 if total_staked else None,
            max_drawdown=cls._max_drawdown([row.bet.profit_loss or 0.0 for row in rows]),
            avg_clv_pct=(sum(clv_values) / len(clv_values)) if clv_values else None,
            clv_count=len(clv_values),
        )

    @staticmethod
    def _max_drawdown(profit_loss_sequence: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for delta in profit_loss_sequence:
            equity += delta
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    @staticmethod
    def _clv_pct(
        bet: BacktestBet,
        closing_odds: dict[tuple[int, str, str, int | None], HistoricalOddSnapshot],
    ) -> float | None:
        closing = closing_odds.get((bet.match_id, bet.market_type, bet.selection, bet.bookmaker_id))
        if closing is None or closing.odd_value <= 0:
            return None
        return ((bet.bookmaker_odds / closing.odd_value) - 1.0) * 100.0
