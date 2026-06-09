"""Diagnostics for backtest runs."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import BacktestBet, BacktestRun


@dataclass(frozen=True, slots=True)
class BacktestGroupMetrics:
    """Aggregate metrics for one backtest slice."""

    label: str
    bets: int
    wins: int
    avg_model_probability: float
    actual_win_rate: float
    avg_bookmaker_probability: float
    avg_odds: float
    avg_edge_pct: float
    profit_loss: float
    roi_pct: float | None


@dataclass(frozen=True, slots=True)
class BacktestDiagnosticsReport:
    """Diagnostic report for one backtest run."""

    run_id: int
    total_bets: int
    profit_loss: float
    roi_pct: float | None
    by_selection: tuple[BacktestGroupMetrics, ...]
    by_odds: tuple[BacktestGroupMetrics, ...]
    by_edge: tuple[BacktestGroupMetrics, ...]


class BacktestDiagnostics:
    """Build diagnostic summaries for stored backtest runs."""

    ODDS_BINS = ((1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 100.0))
    EDGE_BINS = ((0.0, 3.0), (3.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, 999.0))

    def __init__(self, session: Session) -> None:
        self._session = session

    def build_report(self, run_id: int) -> BacktestDiagnosticsReport:
        """Return grouped diagnostics for a stored run."""

        run = self._session.get(BacktestRun, run_id)
        if run is None:
            raise ValueError(f"Backtest run id={run_id} not found")

        bets = (
            self._session.query(BacktestBet)
            .filter(
                BacktestBet.backtest_run_id == run_id,
                BacktestBet.is_bet.is_(True),
            )
            .all()
        )

        selections = tuple(sorted({bet.selection for bet in bets}))
        return BacktestDiagnosticsReport(
            run_id=run.id,
            total_bets=run.total_bets,
            profit_loss=run.profit_loss,
            roi_pct=run.roi_pct,
            by_selection=tuple(
                self._metrics_for(label=selection, bets=[bet for bet in bets if bet.selection == selection])
                for selection in selections
            ),
            by_odds=tuple(
                self._metrics_for(
                    label=f"{low:.1f}-{high:.1f}",
                    bets=[bet for bet in bets if low <= bet.bookmaker_odds < high],
                )
                for low, high in self.ODDS_BINS
            ),
            by_edge=tuple(
                self._metrics_for(
                    label=f"{low:.1f}-{high:.1f}",
                    bets=[bet for bet in bets if low <= bet.edge_pct < high],
                )
                for low, high in self.EDGE_BINS
            ),
        )

    @staticmethod
    def _metrics_for(*, label: str, bets: list[BacktestBet]) -> BacktestGroupMetrics:
        if not bets:
            return BacktestGroupMetrics(
                label=label,
                bets=0,
                wins=0,
                avg_model_probability=0.0,
                actual_win_rate=0.0,
                avg_bookmaker_probability=0.0,
                avg_odds=0.0,
                avg_edge_pct=0.0,
                profit_loss=0.0,
                roi_pct=None,
            )

        wins = sum(1 for bet in bets if bet.result == "won")
        staked = sum(bet.stake for bet in bets)
        profit_loss = sum(bet.profit_loss or 0.0 for bet in bets)
        return BacktestGroupMetrics(
            label=label,
            bets=len(bets),
            wins=wins,
            avg_model_probability=sum(bet.model_probability for bet in bets) / len(bets),
            actual_win_rate=wins / len(bets),
            avg_bookmaker_probability=sum(bet.bookmaker_probability for bet in bets) / len(bets),
            avg_odds=sum(bet.bookmaker_odds for bet in bets) / len(bets),
            avg_edge_pct=sum(bet.edge_pct for bet in bets) / len(bets),
            profit_loss=profit_loss,
            roi_pct=(profit_loss / staked) * 100.0 if staked > 0 else None,
        )
