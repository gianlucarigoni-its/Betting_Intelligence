# Market Coverage Guardrail

## Problem

The engine was able to run model experiments on O/U and BTTS, but the database coverage was not explicit enough to prevent invalid capital-readiness claims.

## Change

Added `backtesting.run_market_coverage_report`.

The report prints odds coverage by season and market, then applies a coverage gate for a requested market.

## Current Coverage

- `1X2`: closing data across 10 seasons, opening data across 5 seasons.
- `OU_2_5`: opening/closing data across 5 seasons only, from 2019/2020 to 2023/2024.
- `BTTS`: no odds snapshots in the database.

## Gate Results

O/U with 8-season minimum:

- FAIL: opening seasons 5 < 8.
- FAIL: closing seasons 5 < 8.

BTTS:

- FAIL: market not found.

## Verdict

Not capital-ready.

The blocker is now explicit: the promising O/U subset cannot be validated to production standard without more O/U history, and BTTS cannot be evaluated until odds are imported from a source that actually contains it.
