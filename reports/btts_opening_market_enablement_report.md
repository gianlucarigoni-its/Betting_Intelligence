# BTTS Opening Market Enablement

## Scope

This cycle extended the historical Poisson betting pipeline to support the `BTTS` market end-to-end:

- Backtester policy wiring
- Calibration CLI defaults and arguments
- League policy persistence
- Backtester unit coverage
- Opening-odds backtest runs across five leagues and five seasons

## Code Change

- Added BTTS-specific enable flags and thresholds for `BTTS_YES` and `BTTS_NO`.
- Propagated those fields through `BacktestDefaults`, `LeagueBettingPolicy`, `HistoricalPoissonBacktestConfig`, and the backtester selector.
- Added a selector test proving the engine can choose `BTTS_YES` when the signal supports it.

## Validation

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_historical_poisson_backtester.py -q -s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -s`

## Backtest Result

Two opening-odds BTTS calibration attempts were executed on `E0,D1,SP1,I1,F1` for seasons `1920,2021,2122,2223,2324`.

Both attempts produced `0` settled bets in every run, so calibration could not evaluate ROI/CLV.

That means:

- The BTTS path is wired correctly enough to backtest.
- The current selection thresholds are too strict for this market on the available dataset, or the market is not competitive under the current signal.
- The market is not yet usable as a capital-ready deployment path.

## Verdict

BTTS is now supported in the engine, but it is not yet a trading edge. The next step is to inspect why the BTTS edge collapses to zero on real data and to compare it against looser thresholds or a different selection policy before promoting it.
