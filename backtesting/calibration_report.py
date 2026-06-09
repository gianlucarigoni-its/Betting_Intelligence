# backtesting/calibration_report.py
"""
Calibration report per le prediction del backtest.

Calibrazione significa: quando il modello dice "60% di probabilità",
nella realtà vince il 60% delle volte? Se sì, il modello è ben calibrato.

Questo modulo analizza TUTTE le prediction salvate (is_bet=True e False),
dando una visione completa della qualità del modello indipendente dai filtri
strategici. Un modello può avere ROI positivo ma essere mal calibrato,
o viceversa — sono due dimensioni ortogonali.

Metriche prodotte:
  - Brier Score : errore quadratico medio tra prob_modello e outcome reale
                  (0.0 = perfetto, 0.25 = modello casuale, >0.25 = peggio del caso)
  - ECE         : Expected Calibration Error, errore medio ponderato per bin
                  (0.0 = calibrazione perfetta)
  - Reliability diagram data: avg_prob vs win_rate per bin, pronto per Plotly
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from database.models import BacktestBet

# 10 bin di ampiezza uniforme 0.10 che coprono [0.0, 1.0]
_PROB_BINS: list[tuple[float, float]] = [
    (round(i * 0.1, 1), round((i + 1) * 0.1, 1)) for i in range(10)
]

_RESULT_WON = "won"


# ---------------------------------------------------------------------------
# Data classes — output del report
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """Metriche di calibrazione per un singolo bin di probabilità."""

    bin_label: str       # es. "0.40-0.50"
    bin_low: float
    bin_high: float
    n_total: int         # prediction totali nel bin (bet + non-bet)
    n_bet: int           # di cui con is_bet=True
    avg_model_prob: float    # media delle prob predette nel bin
    actual_win_rate: float   # frazione che ha effettivamente vinto
    calibration_error: float # |actual_win_rate - avg_model_prob|
    brier_score: float       # MSE per questo bin


@dataclass(frozen=True, slots=True)
class SelectionCalibration:
    """Calibrazione per una singola selezione (HOME / DRAW / AWAY)."""

    selection: str
    n_total: int
    avg_model_prob: float
    actual_win_rate: float
    brier_score: float
    bins: tuple[CalibrationBin, ...]


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Report di calibrazione completo per uno o più backtest run."""

    run_ids: tuple[int, ...]
    n_total: int         # record totali analizzati (bet + non-bet)
    n_bet: int           # solo is_bet=True
    n_non_bet: int       # solo is_bet=False
    brier_score: float   # score globale — più basso è meglio (random = 0.25)
    ece: float           # Expected Calibration Error globale
    bins: tuple[CalibrationBin, ...]
    by_selection: tuple[SelectionCalibration, ...]

    def print_summary(self) -> None:
        """Stampa un riepilogo leggibile a schermo."""
        divider = "=" * 65
        print(f"\n{divider}")
        print("  CALIBRATION REPORT")
        print(divider)
        print(f"  Run IDs       : {', '.join(str(r) for r in self.run_ids)}")
        print(f"  Prediction    : {self.n_total:,}  "
              f"(bet: {self.n_bet} | non-bet: {self.n_non_bet})")
        print(f"  Brier Score   : {self.brier_score:.4f}  "
              f"{'✓ buono' if self.brier_score < 0.20 else '⚠ da migliorare'}")
        print(f"  ECE           : {self.ece:.4f}  "
              f"{'✓ buono' if self.ece < 0.05 else '⚠ da migliorare'}")

        print(f"\n  {'Bin':<12} {'N':>5} {'Bet':>5} "
              f"{'Prob_mod':>9} {'Win_rate':>9} {'Err':>7}")
        print(f"  {'-'*12} {'-'*5} {'-'*5} {'-'*9} {'-'*9} {'-'*7}")
        for b in self.bins:
            if b.n_total == 0:
                continue
            flag = "⚠" if b.calibration_error > 0.10 else " "
            print(
                f"  {b.bin_label:<12} {b.n_total:>5} {b.n_bet:>5} "
                f"{b.avg_model_prob:>9.3f} {b.actual_win_rate:>9.3f} "
                f"{b.calibration_error:>6.3f}{flag}"
            )

        print(f"\n  Per selezione:")
        for sel in self.by_selection:
            if sel.n_total == 0:
                continue
            print(
                f"    {sel.selection:<6}  n={sel.n_total:>4}  "
                f"prob={sel.avg_model_prob:.3f}  "
                f"win={sel.actual_win_rate:.3f}  "
                f"brier={sel.brier_score:.4f}"
            )
        print(divider + "\n")


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class CalibrationReportBuilder:
    """
    Costruisce report di calibrazione dai record BacktestBet persistiti.

    Legge TUTTI i record settled (is_bet=True e False) per dare una
    visione completa della qualità delle stime probabilistiche del modello.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def build(
        self,
        run_ids: Optional[list[int]] = None,
    ) -> CalibrationReport:
        """
        Costruisce il report di calibrazione.

        Args:
            run_ids: ID dei run da includere. None = tutti i run disponibili.

        Returns:
            CalibrationReport con bin, Brier score, ECE e breakdown per selezione.

        Raises:
            ValueError: Se non ci sono prediction settled per i run richiesti.
        """
        records = self._load_settled_records(run_ids)
        if not records:
            raise ValueError(
                "Nessuna prediction settled trovata. "
                "Esegui prima un backtest con le modifiche is_bet attive."
            )

        resolved_run_ids = tuple(sorted({r.backtest_run_id for r in records}))

        bins = tuple(
            self._build_bin(records, low, high)
            for low, high in _PROB_BINS
        )

        selections = sorted({r.selection for r in records})
        by_selection = tuple(
            self._build_selection(records, sel)
            for sel in selections
        )

        n_bet = sum(1 for r in records if r.is_bet)

        return CalibrationReport(
            run_ids=resolved_run_ids,
            n_total=len(records),
            n_bet=n_bet,
            n_non_bet=len(records) - n_bet,
            brier_score=_brier_score(records),
            ece=_expected_calibration_error(bins),
            bins=bins,
            by_selection=by_selection,
        )

    # ------------------------------------------------------------------
    # Metodi privati
    # ------------------------------------------------------------------

    def _load_settled_records(
        self,
        run_ids: Optional[list[int]],
    ) -> list[BacktestBet]:
        """Carica tutti i record settled — bet e non-bet."""
        query = self._session.query(BacktestBet).filter(
            BacktestBet.result != "pending"
        )
        if run_ids:
            query = query.filter(
                BacktestBet.backtest_run_id.in_(run_ids)
            )
        return query.all()

    def _build_bin(
        self,
        records: list[BacktestBet],
        low: float,
        high: float,
    ) -> CalibrationBin:
        """Costruisce le metriche per un singolo bin di probabilità."""
        # L'ultimo bin (0.9-1.0) include il bordo superiore
        if high >= 1.0:
            subset = [r for r in records if low <= r.model_probability <= high]
        else:
            subset = [r for r in records if low <= r.model_probability < high]

        label = f"{low:.2f}-{high:.2f}"

        if not subset:
            return CalibrationBin(
                bin_label=label,
                bin_low=low,
                bin_high=high,
                n_total=0,
                n_bet=0,
                avg_model_prob=(low + high) / 2,
                actual_win_rate=0.0,
                calibration_error=0.0,
                brier_score=0.0,
            )

        outcomes = [_to_outcome(r) for r in subset]
        avg_prob = sum(r.model_probability for r in subset) / len(subset)
        win_rate = sum(outcomes) / len(outcomes)
        b_score = sum(
            (r.model_probability - o) ** 2
            for r, o in zip(subset, outcomes)
        ) / len(subset)

        return CalibrationBin(
            bin_label=label,
            bin_low=low,
            bin_high=high,
            n_total=len(subset),
            n_bet=sum(1 for r in subset if r.is_bet),
            avg_model_prob=avg_prob,
            actual_win_rate=win_rate,
            calibration_error=abs(win_rate - avg_prob),
            brier_score=b_score,
        )

    def _build_selection(
        self,
        records: list[BacktestBet],
        selection: str,
    ) -> SelectionCalibration:
        """Costruisce la calibrazione per una singola selezione."""
        subset = [r for r in records if r.selection == selection]

        if not subset:
            return SelectionCalibration(
                selection=selection,
                n_total=0,
                avg_model_prob=0.0,
                actual_win_rate=0.0,
                brier_score=0.0,
                bins=tuple(
                    CalibrationBin(
                        bin_label=f"{low:.2f}-{high:.2f}",
                        bin_low=low, bin_high=high,
                        n_total=0, n_bet=0,
                        avg_model_prob=(low + high) / 2,
                        actual_win_rate=0.0,
                        calibration_error=0.0,
                        brier_score=0.0,
                    )
                    for low, high in _PROB_BINS
                ),
            )

        outcomes = [_to_outcome(r) for r in subset]
        avg_prob = sum(r.model_probability for r in subset) / len(subset)
        win_rate = sum(outcomes) / len(outcomes)

        return SelectionCalibration(
            selection=selection,
            n_total=len(subset),
            avg_model_prob=avg_prob,
            actual_win_rate=win_rate,
            brier_score=sum(
                (r.model_probability - o) ** 2
                for r, o in zip(subset, outcomes)
            ) / len(subset),
            bins=tuple(
                self._build_bin(subset, low, high)
                for low, high in _PROB_BINS
            ),
        )


# ---------------------------------------------------------------------------
# Funzioni pure — testabili in isolamento
# ---------------------------------------------------------------------------

def _to_outcome(record: BacktestBet) -> float:
    """Converte il risultato in outcome binario (1.0 = won, 0.0 = lost/push)."""
    return 1.0 if record.result == _RESULT_WON else 0.0


def _brier_score(records: list[BacktestBet]) -> float:
    """
    Calcola il Brier score globale.

    Formula: BS = (1/N) * Σ (p_i - o_i)²
    Riferimento: 0.00 = perfetto | 0.25 = modello casuale | >0.25 = peggio del caso
    """
    if not records:
        return 0.0
    return sum(
        (r.model_probability - _to_outcome(r)) ** 2
        for r in records
    ) / len(records)


def _expected_calibration_error(bins: tuple[CalibrationBin, ...]) -> float:
    """
    Calcola l'Expected Calibration Error (ECE).

    Formula: ECE = Σ_bin (n_bin / N_totale) * |win_rate_bin - avg_prob_bin|
    Riferimento: 0.00 = calibrazione perfetta | >0.10 = sovra/sotto stima sistematica
    """
    n_total = sum(b.n_total for b in bins)
    if n_total == 0:
        return 0.0
    return sum(
        (b.n_total / n_total) * b.calibration_error
        for b in bins
    )