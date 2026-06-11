# Opening Odds, CLV and Meta-Model Walk-Forward Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Executive Summary

The decisive test was completed: historical odds were reimported with separated opening and true closing prices, the 1X2 policy was backtested at opening odds, CLV was measured against closing odds, and the selection meta-model was validated walk-forward across seasons.

Result: the engine shows a promising opening-price signal, but it is not yet a proven competitive betting engine. The strongest current evidence is positive ROI at opening odds and positive average CLV. The main weakness is very low volume: 21 opening bets across 5 leagues and 5 recent seasons, all HOME selections.

## Changes Completed

```text
- Reimported Football-Data historical CSVs for 50 league-season combinations.
- Updated importer to reject invalid odds values <= 1.0.
- Updated importer to upsert existing historical snapshots instead of skipping stale closing rows.
- Corrected old closing snapshots that had been populated from opening Bet365 columns.
- Added a regression test for true closing snapshot update on reimport.
- Added walk-forward CLI for the selection meta-model.
- Saved final opening meta-model artifact: config/selection_meta_opening.pkl.
- Re-ran opening and closing backtests after data correction.
```

## Data State

```text
Batch reimport success: 50/50
Existing odds updated to true closing: 25,667
1X2 opening odds: 26,850
1X2 closing odds: 54,249
1X2 total odds: 81,099
OU_2_5 opening odds: 17,892
OU_2_5 closing odds: 17,906
OU_2_5 total odds: 35,798
BTTS odds: 0
```

BTTS remains unsupported by the available Football-Data CSV columns in the imported datasets. The code can load BTTS if those columns exist, but the current source files do not provide them.

## Opening Backtest

Command:

```bash
.venv/bin/python -m backtesting.run_calibration --skip-import --odds-snapshot-type opening --policy-file config/league_backtest_policy.json
.venv/bin/python -m backtesting.run_stability_report --runs 265-314 --min-bets 1
```

Summary:

```text
runs: 265-314
predictions: 18,573
bets: 21
hit rate: 0.810
ROI: +39.00%
P&L: +81.90
max drawdown: 10.00
avg CLV: +1.41%
selection: HOME only
```

By season:

```text
2019/2020  bets=2  hit=0.500  ROI=-12.50%  CLV=-5.34%
2020/2021  bets=1  hit=1.000  ROI=+75.00%  CLV=-2.78%
2021/2022  bets=3  hit=1.000  ROI=+61.67%  CLV=-0.17%
2022/2023  bets=9  hit=0.778  ROI=+51.22%  CLV=+1.99%
2023/2024  bets=6  hit=0.667  ROI=+20.50%  CLV=+4.28%
```

By league:

```text
Bundesliga       bets=3  hit=0.667  ROI=+13.33%  CLV=-3.74%
La Liga          bets=6  hit=0.833  ROI=+38.67%  CLV=+6.21%
Premier League   bets=7  hit=0.857  ROI=+41.14%  CLV=+0.58%
Serie A          bets=5  hit=0.800  ROI=+51.80%  CLV=-0.09%
```

## Closing Backtest

Command:

```bash
.venv/bin/python -m backtesting.run_calibration --skip-import --seasons 1920,2021,2122,2223,2324 --odds-snapshot-type closing --policy-file config/league_backtest_policy.json
.venv/bin/python -m backtesting.run_stability_report --runs 315-339 --min-bets 1
```

Summary:

```text
runs: 315-339
predictions: 18,576
bets: 17
hit rate: 0.706
ROI: +20.59%
P&L: +35.00
max drawdown: 20.50
avg CLV: 0.00% closing-vs-closing
selection: HOME only
```

By season:

```text
2019/2020  bets=1  hit=1.000  ROI=+80.00%
2020/2021  bets=2  hit=1.000  ROI=+75.50%
2021/2022  bets=2  hit=1.000  ROI=+70.00%
2022/2023  bets=7  hit=0.571  ROI=-4.43%
2023/2024  bets=5  hit=0.600  ROI=+2.00%
```

By league:

```text
Bundesliga       bets=2  hit=0.500  ROI=-10.00%
La Liga          bets=3  hit=1.000  ROI=+74.33%
Premier League   bets=4  hit=0.750  ROI=+19.00%
Serie A          bets=8  hit=0.625  ROI=+8.88%
```

## Opening vs Closing Interpretation

```text
opening bets: 21
closing bets: 17
overlap: 3
opening-only: 18
closing-only: 14
overlap opening P&L: +21.40
overlap closing P&L: +21.40
overlap average price CLV: 0.00%
```

The important point is that opening and closing do not just change payout. They change which matches pass the edge policy. The model is selecting more opportunities at opening odds, and the opening set has higher ROI and lower drawdown.

This is encouraging, but not conclusive. The sample is too small, and the average CLV is positive mainly because the latest two seasons are positive while earlier seasons are flat or negative.

## Meta-Model Walk-Forward

Command:

```bash
.venv/bin/python -m backtesting.run_selection_meta_walkforward --runs 265-314 --min-train-seasons 3 --output-model config/selection_meta_opening.pkl
.venv/bin/python -m backtesting.run_selection_meta_walkforward --runs 265-314 --min-train-seasons 2
```

min_train_seasons=3:

```text
2022/2023  train_seasons=3  samples=3939  Brier=0.2168  baseline_bets=9  baseline_ROI=+51.22%  meta_bets=9  meta_ROI=+51.22%
2023/2024  train_seasons=4  samples=3747  Brier=0.2106  baseline_bets=6  baseline_ROI=+20.50%  meta_bets=6  meta_ROI=+20.50%
summary: baseline_bets=15  meta_bets=15  ROI=+38.93%  P&L=+58.40
```

min_train_seasons=2:

```text
2021/2022  Brier=0.2150  baseline_bets=3  meta_bets=3  ROI=+61.67%
2022/2023  Brier=0.2168  baseline_bets=9  meta_bets=9  ROI=+51.22%
2023/2024  Brier=0.2106  baseline_bets=6  meta_bets=6  ROI=+20.50%
summary: baseline_bets=18  meta_bets=18  ROI=+42.72%  P&L=+76.90
```

Verdict: the meta-model infrastructure works, but it currently adds no filtering value over the existing policy. It keeps every selected bet in these folds. It should not be promoted as an active gate until thresholds/features make it genuinely selective in walk-forward validation.

## Quality Assessment

Current quality as a research engine: good.

```text
- Data import is now idempotent and corrects stale snapshots.
- Opening/closing semantics are represented explicitly.
- CLV is computed against stored true closing snapshots.
- Backtests are reproducible by run id.
- Meta-model validation is walk-forward, not random split.
- Test suite passes: 72 passed.
```

Remaining quality issues:

```text
- Feature metadata is still encoded in reason strings instead of structured columns.
- The meta-model gate uses fixed thresholds and did not improve selection yet.
- O/U 2.5 odds are imported but not yet promoted to a betting policy.
- BTTS data is unavailable in current CSV source files.
- Backtest volume is too low to support strong statistical claims.
```

## Reliability Assessment

Reliability as a betting engine: not enough for real-money confidence.

Positive evidence:

```text
- Opening ROI is materially higher than closing ROI: +39.00% vs +20.59%.
- Opening max drawdown is lower: 10.00 vs 20.50.
- Average CLV at opening is positive: +1.41%.
- Latest seasons show positive CLV: +1.99% in 2022/23 and +4.28% in 2023/24.
```

Negative evidence:

```text
- Only 21 opening bets across 5 seasons and 5 leagues.
- All bets are HOME; DRAW and AWAY remain unproven.
- CLV is negative or near zero in 2019/20, 2020/21 and 2021/22.
- Bundesliga and Serie A CLV are negative or near flat.
- Meta-model does not reduce false positives yet.
```

Reliability verdict: medium for research, low-to-medium for a betting signal, not production-grade.

## Market Competitiveness

Competitiveness: promising but not proven.

The engine now has the first useful market-quality signal: it can identify some value before closing and produce positive average CLV. That is more meaningful than aggregate ROI alone.

However, a competitive betting engine needs repeated positive CLV at adequate volume. The current result is too sparse and concentrated on HOME favorites. The market can still absorb this as sampling noise until the same behavior holds across more bets, markets, and time windows.

## What Works Well

```text
- Opening odds improve both ROI and drawdown versus closing odds.
- CLV is now measurable and positive overall.
- The HOME policy remains the only defensible 1X2 selection.
- The importer can now support future O/U 2.5 validation from real odds.
- The project has a reproducible path for meta-model walk-forward tests.
```

## What Is Bad

```text
- Bet volume is far too low.
- AWAY and DRAW are still not viable.
- Meta-model has no incremental selection power yet.
- BTTS cannot be tested with the current imported source data.
- The 1X2 market remains efficient and difficult to beat robustly.
```

## High Priority Changes

1. Build and validate O/U 2.5 betting policy using the imported opening/closing odds.
2. Make the meta-model genuinely selective: tune thresholds only walk-forward and report rejected-bet ROI versus kept-bet ROI.
3. Add structured JSON or columns for lambda, ELO and form features on backtest_bets.
4. Require minimum bet counts per season/league before accepting any policy.
5. Add confidence intervals or bootstrap tests for ROI and CLV.
6. Keep AWAY closed until it has a dedicated policy with positive OOS ROI and non-negative CLV.

## Lower Priority Changes

1. Search for a reliable free BTTS historical odds source, or defer BTTS.
2. Add Asian handicap and double chance only after O/U 2.5 proves useful.
3. Optimize rolling feature computation with cached state.
4. Add dashboard views after policy reliability improves.
5. Add artifact/version registry for trained meta-models.

## Final Verdict

The engine is stronger than before this task. It now has true opening/closing data, measurable CLV, a corrected historical odds store, and a walk-forward meta-model workflow.

It is still not a proven competitive betting system. The current HOME opening signal is worth developing because it shows positive CLV and better ROI than closing, but the sample is too small and the meta-model is not yet adding value. The next best engineering move is to shift from 1X2 HOME-only validation to O/U 2.5 opening/closing validation, where the Poisson distribution should have a more natural edge surface.
