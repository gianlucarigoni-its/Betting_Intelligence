# O/U 2.5 Market Validation Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Executive Summary

O/U 2.5 has been brought into the production backtesting pipeline with separated opening and closing prices, explicit OVER/UNDER policy branches, and bootstrap confidence intervals for ROI and CLV.

The market is measurable and volume-rich, but it is not yet competitive enough for real capital. Opening odds underperform closing odds on ROI and CLV, and the closing version is only less bad, not genuinely profitable.

## Implemented Changes

```text
- Backtester now supports market_type=1X2 and market_type=OU_2_5.
- OVER_2_5 and UNDER_2_5 have separate policy thresholds.
- run_calibration exposes CLI options for O/U bet activation and thresholds.
- Stability report now prints bootstrap confidence intervals for ROI and CLV.
- Added tests for O/U selection and bootstrap interval helpers.
- BTTS has been removed from the public CLI until a real source/policy exists.
```

## Opening Backtest

Command:

```bash
.venv/bin/python -m backtesting.run_calibration --skip-import --market-type OU_2_5 --odds-snapshot-type opening --allow-over-bets --allow-under-bets --over-min-edge-pct 3.0 --over-max-edge-pct 10.0 --over-min-model-probability 0.50 --over-max-bookmaker-odds 2.6 --under-min-edge-pct 3.0 --under-max-edge-pct 10.0 --under-min-model-probability 0.50 --under-max-bookmaker-odds 2.6
.venv/bin/python -m backtesting.run_stability_report --runs 340-389 --min-bets 1
```

Summary:

```text
bets: 1756
ROI: -7.09%
roi_ci: [-11.56%, -2.91%]
avg CLV: -0.34%
clv_ci: [-0.62%, -0.04%]
```

By selection:

```text
OVER_2_5  bets=985  ROI=-2.99%  CLV=-1.17%
UNDER_2_5 bets=771  ROI=-12.33% CLV=+0.73%
```

Interpretation:

```text
OVER is less bad than UNDER, but still negative.
UNDER has positive CLV but poor realized ROI, which means the policy is not translating price quality into winning bets.
```

## Closing Backtest

Command:

```bash
.venv/bin/python -m backtesting.run_calibration --skip-import --market-type OU_2_5 --odds-snapshot-type closing --allow-over-bets --allow-under-bets --over-min-edge-pct 3.0 --over-max-edge-pct 10.0 --over-min-model-probability 0.50 --over-max-bookmaker-odds 2.6 --under-min-edge-pct 3.0 --under-max-edge-pct 10.0 --under-min-model-probability 0.50 --under-max-bookmaker-odds 2.6
.venv/bin/python -m backtesting.run_stability_report --runs 390-439 --min-bets 1
```

Summary:

```text
bets: 1730
ROI: -4.64%
roi_ci: [-9.69%, -0.29%]
avg CLV: 0.00%
```

By selection:

```text
OVER_2_5  bets=988  ROI=-1.42%
UNDER_2_5 bets=742  ROI=-8.94%
```

## Quality Assessment

Positive:

```text
- O/U is now fully supported by the backtest pipeline.
- ROI and CLV uncertainty are visible instead of hidden behind a single aggregate number.
- Tests pass: 76 passed.
```

Negative:

```text
- O/U does not beat the market in the tested configuration.
- Opening is worse than closing on both ROI and CLV.
- UNDER is especially weak on realized return.
```

## Reliability and Competitiveness Verdict

Reliability for real capital: not sufficient.
Competitiveness: not proven.

The market is now production-ready as an evaluation path, but not production-ready as a capital deployment path. It should stay in research/validation mode until a stricter policy or a different market version proves positive ROI with non-overlapping confidence intervals.
