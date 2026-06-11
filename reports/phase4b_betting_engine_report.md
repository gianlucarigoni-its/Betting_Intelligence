# Phase 4B Betting Engine Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Executive Summary

Phase 4B improved the engine from threshold tuning toward probabilistic signal evaluation. The project now has historical pre-match ELO, robust form features, a selection meta-model, explicit HOME/DRAW/AWAY policies, opening-vs-closing odds support, CLV diagnostics, and Poisson probabilities for O/U 2.5 and BTTS.

After the decisive reimport and validation, the engine shows a promising but still unproven opening-price signal. Opening 1X2 HOME bets produced positive ROI and positive average CLV, but the sample is very small and the meta-model did not improve selection yet.

Detailed validation report:

```text
reports/opening_clv_meta_walkforward_report.md
```

## Implemented Commits In This Phase

```text
ac2d8d7 docs: plan probabilistic signal improvement phase
c1132ae feat: add historical elo and robust form features
69793eb feat: add selection meta model gate
ad4c8f7 feat: add opening odds and stability diagnostics
8f243f3 feat: add poisson over under and btts markets
503d768 docs: add phase 4b betting engine report
```

Additional commits for the decisive validation are listed in git history after this report update.

## Current Engine State

```text
Historical ELO pre-match: implemented
Robust 5/10 match form: implemented
Selection meta-model: implemented, not promoted as active default
HOME/DRAW/AWAY separate policy: implemented
Opening/closing odds: implemented and reimported
CLV stability report: implemented
O/U 2.5 probabilities and odds import: implemented
BTTS probabilities: implemented
BTTS odds import: supported but current CSVs provide no usable rows
```

## Decisive Validation Results

Opening odds backtest, runs 265-314:

```text
bets: 21
hit rate: 0.810
ROI: +39.00%
P&L: +81.90
max drawdown: 10.00
avg CLV: +1.41%
selection: HOME only
```

Closing odds backtest, runs 315-339:

```text
bets: 17
hit rate: 0.706
ROI: +20.59%
P&L: +35.00
max drawdown: 20.50
avg CLV: 0.00% closing-vs-closing
selection: HOME only
```

Meta-model walk-forward on opening runs:

```text
min_train_seasons=3: 15 baseline bets, 15 meta bets, ROI +38.93%
min_train_seasons=2: 18 baseline bets, 18 meta bets, ROI +42.72%
Brier range: 0.2106 - 0.2168
```

Interpretation:

```text
The opening signal is better than closing and has positive average CLV.
The meta-model currently keeps every selected policy bet, so it has no proven incremental value yet.
The signal remains too low-volume for production confidence.
```

## Data State After Reimport

```text
Batch reimport: 50/50 successful
Existing odds updated to true closing: 25,667
1X2 opening odds: 26,850
1X2 closing odds: 54,249
OU_2_5 opening odds: 17,892
OU_2_5 closing odds: 17,906
BTTS odds: 0
```

## Quality Assessment

Quality as a research/backtesting engine: good.

```text
- Leakage-safe temporal features are in place.
- Opening and closing prices are stored distinctly.
- Reimport is idempotent and can update stale snapshots.
- Stability reporting includes ROI, hit rate, drawdown and CLV.
- Walk-forward meta-model validation exists.
- Test suite passes: 72 passed.
```

Main quality gaps:

```text
- Backtest feature payloads are still stored in reason text.
- Meta-model thresholds are simple and not yet useful.
- O/U 2.5 has data and probabilities but no validated betting policy.
- BTTS cannot be evaluated from the current CSV data.
```

## Reliability Assessment

Reliability as a research engine: medium-good.
Reliability as a betting engine: low-to-medium.

Reason:

```text
Positive: opening ROI +39.00%, average CLV +1.41%, max drawdown lower than closing.
Negative: only 21 opening bets, all HOME, mixed CLV by season/league, no meta-model uplift.
```

Minimum gates before considering the engine reliable for capital:

```text
- materially higher bet count
- positive CLV in most seasons and leagues
- controlled drawdown by time window
- meta-model must reject bad bets without deleting all volume
- O/U 2.5 must be tested with opening and closing odds
```

## Market Competitiveness

Competitiveness is not proven.

The engine has a potentially real signal because it finds some value at opening prices before the closing market. That matters more than ROI alone. But the sample is too small and too concentrated on HOME selections to call it market-competitive.

Current market verdict:

```text
Interesting research signal, not yet a production betting edge.
```

## What Works Well

```text
- HOME opening signal is the strongest current 1X2 slice.
- Opening odds outperform closing odds in ROI and drawdown.
- CLV is now measurable and positive overall.
- The codebase supports repeatable walk-forward validation.
- O/U 2.5 is ready for the next policy test.
```

## What Is Bad

```text
- Bet volume is too low.
- AWAY remains closed and unproven.
- DRAW remains unproven.
- Meta-model does not yet improve selection.
- 1X2 remains a very efficient market.
```

## High Priority Next Changes

1. Validate O/U 2.5 opening/closing policy with CLV and stability by season/league.
2. Improve meta-model selectivity and report kept-bet vs rejected-bet ROI.
3. Store feature payloads as structured JSON/columns instead of parsing reason text.
4. Add ROI/CLV confidence intervals or bootstrap diagnostics.
5. Require minimum bet volume before accepting any policy slice.

## Lower Priority Next Changes

1. Look for a reliable free BTTS odds source.
2. Add Asian handicap and double chance after O/U 2.5.
3. Optimize rolling feature computation.
4. Build dashboard only after betting policies are more reliable.
5. Add model artifact/version registry.

## Final Verdict

The project is stronger and more honest than before Phase 4B: it can now test whether a signal beats the market before closing. The current opening HOME signal is promising, but not enough to declare the betting engine competitive. The next efficient step is O/U 2.5 opening/closing validation, not more 1X2 threshold tuning.
