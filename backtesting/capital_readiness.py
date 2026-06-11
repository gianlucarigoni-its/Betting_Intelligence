"""Capital readiness gate for betting backtest stability reports."""

from __future__ import annotations

from dataclasses import dataclass

from backtesting.stability_report import StabilitySliceMetrics


@dataclass(frozen=True, slots=True)
class CapitalReadinessCriteria:
    min_bets: int = 100
    min_clv_count: int = 100
    min_roi_ci_low_pct: float = 0.0
    min_clv_ci_low_pct: float = 0.0
    max_drawdown_pct_of_stake: float = 20.0


@dataclass(frozen=True, slots=True)
class CapitalReadinessResult:
    passed: bool
    failures: tuple[str, ...]
    drawdown_pct_of_stake: float | None


def evaluate_capital_readiness(
    metrics: StabilitySliceMetrics,
    criteria: CapitalReadinessCriteria | None = None,
) -> CapitalReadinessResult:
    criteria = criteria or CapitalReadinessCriteria()
    failures: list[str] = []

    if metrics.bets < criteria.min_bets:
        failures.append(f"bets {metrics.bets} < min_bets {criteria.min_bets}")
    if metrics.clv_count < criteria.min_clv_count:
        failures.append(f"clv_count {metrics.clv_count} < min_clv_count {criteria.min_clv_count}")
    if metrics.roi_ci_low_pct is None or metrics.roi_ci_low_pct < criteria.min_roi_ci_low_pct:
        failures.append(
            f"roi_ci_low {metrics.roi_ci_low_pct} < min_roi_ci_low {criteria.min_roi_ci_low_pct}"
        )
    if metrics.clv_ci_low_pct is None or metrics.clv_ci_low_pct < criteria.min_clv_ci_low_pct:
        failures.append(
            f"clv_ci_low {metrics.clv_ci_low_pct} < min_clv_ci_low {criteria.min_clv_ci_low_pct}"
        )

    drawdown_pct = None
    if metrics.total_staked > 0:
        drawdown_pct = (metrics.max_drawdown / metrics.total_staked) * 100.0
        if drawdown_pct > criteria.max_drawdown_pct_of_stake:
            failures.append(
                f"drawdown_pct {drawdown_pct:.2f} > max_drawdown_pct {criteria.max_drawdown_pct_of_stake:.2f}"
            )
    else:
        failures.append("total_staked is zero")

    return CapitalReadinessResult(
        passed=not failures,
        failures=tuple(failures),
        drawdown_pct_of_stake=drawdown_pct,
    )


def evaluate_slice_readiness(
    metrics: StabilitySliceMetrics,
    criteria: CapitalReadinessCriteria | None = None,
) -> CapitalReadinessResult:
    return evaluate_capital_readiness(metrics, criteria)
