# Capital Readiness Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Purpose

This report adds a hard gate between research backtests and real-capital usage. A strategy must pass minimum requirements on volume, CLV coverage, ROI confidence interval, CLV confidence interval and drawdown before it can be considered deployable.

## Implemented Gate

CLI:

```bash
.venv/bin/python -m backtesting.run_capital_readiness_report --runs <ids>
```

Default criteria:

```text
min_bets: 100
min_clv_count: 100
min_roi_ci_low_pct: 0.0
min_clv_ci_low_pct: 0.0
max_drawdown_pct_of_stake: 20.0
```

## 1X2 Opening HOME Signal

Command:

```bash
.venv/bin/python -m backtesting.run_capital_readiness_report --runs 265-314 --min-bets 100 --min-clv-count 20 --min-roi-ci-low-pct 0.0 --min-clv-ci-low-pct 0.0 --max-drawdown-pct-of-stake 20.0
```

Result:

```text
CAPITAL_READINESS=FAIL
bets=21
clv_count=21
roi=+39.00%
roi_ci=[+9.14%, +64.33%]
clv=+1.41%
clv_ci=[-1.88%, +4.47%]
drawdown_pct_of_stake=4.76%
```

Failures:

```text
- bets 21 < min_bets 100
- clv_ci_low -1.88 < min_clv_ci_low 0.0
```

Interpretation: the 1X2 opening HOME signal is promising but not capital-ready. ROI is strong, but volume is too low and CLV uncertainty still crosses below zero.

## O/U 2.5 Opening Signal

Command:

```bash
.venv/bin/python -m backtesting.run_capital_readiness_report --runs 340-389 --min-bets 100 --min-clv-count 100 --min-roi-ci-low-pct 0.0 --min-clv-ci-low-pct 0.0 --max-drawdown-pct-of-stake 20.0
```

Result:

```text
CAPITAL_READINESS=FAIL
bets=1756
clv_count=1756
roi=-7.09%
roi_ci=[-11.56%, -2.91%]
clv=-0.34%
clv_ci=[-0.62%, -0.04%]
drawdown_pct_of_stake=7.47%
```

Failures:

```text
- roi_ci_low -11.56 < min_roi_ci_low 0.0
- clv_ci_low -0.62 < min_clv_ci_low 0.0
```

Interpretation: O/U has enough volume, but it is negative and should not be used with real capital.

## Final Capital Verdict

The engine is not yet reliable or competitive enough for real-money deployment.

Current deployable status:

```text
1X2 HOME opening: research candidate only
O/U 2.5: rejected for capital deployment
DRAW: not proven
AWAY: closed
BTTS: no usable data source yet
```

## Required Next Production Steps

1. Build a stricter OVER-only O/U policy and validate it walk-forward.
2. Improve meta-model selectivity and report kept-bet versus rejected-bet ROI/CLV.
3. Add structured feature payload storage for lambda, ELO, form and market metadata.
4. Run capital readiness after every candidate policy; no policy is live unless it passes.
5. Search for a reliable BTTS source only after O/U policy improves.
