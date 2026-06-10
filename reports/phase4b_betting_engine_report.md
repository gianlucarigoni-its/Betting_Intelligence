# Phase 4B Betting Engine Report

Date: 2026-06-11

## Executive Summary

The engine is materially stronger than the previous threshold-only phase: it now has historical pre-match ELO, robust 5/10-match form features, an optional selection meta-model, explicit HOME/DRAW/AWAY selection policies, opening-vs-closing support, stability/CLV diagnostics, and Poisson probabilities for Over/Under 2.5 and BTTS.

The betting engine is not yet market-competitive as a production betting system. It is a research/backtesting engine with better signal instrumentation. The current profitable slices are low-volume and fragile, and the existing database still has only closing odds, so CLV is not yet informative.

## Implemented Changes

Commits completed in this phase:

```text
ac2d8d7 docs: plan probabilistic signal improvement phase
c1132ae feat: add historical elo and robust form features
69793eb feat: add selection meta model gate
ad4c8f7 feat: add opening odds and stability diagnostics
8f243f3 feat: add poisson over under and btts markets
```

### 1. Historical ELO

Implemented leakage-safe pre-match ELO reconstruction:

```text
- chronological update after each match
- home/away rating before match
- elo_diff available per prediction
- optional ELO lambda correction
- season regression toward mean
```

Default remains neutral:

```text
elo_lambda_weight = 0.0
```

Reason: ELO correction is implemented but not yet walk-forward promoted.

### 2. Robust Form Features

Added pre-match form features from previous matches only:

```text
- 5-match and 10-match windows
- points per match
- goal difference per match
- goals for/conceded
- clean sheet rate
- conceded trend
- venue-aware expected strength
```

These are persisted in backtest reason strings and available to the meta-model.

### 3. Selection Meta-Model

Added a lightweight logistic-regression selector above Poisson predictions.

Inputs:

```text
selection
league
edge_pct
bookmaker_odds
model_probability
bookmaker_probability
model_market_distance
lambda_home
lambda_away
lambda_gap
```

New CLI:

```bash
python -m backtesting.run_selection_meta_training --runs 210-259 --output config/selection_meta_model.pkl
```

The backtester can use it with:

```bash
python -m backtesting.run_calibration --selection-meta-model-path config/selection_meta_model.pkl
```

Current status: available but not default.

### 4. Separate Selection Policy

HOME, DRAW and AWAY are now evaluated through explicit selection-specific gates inside the backtester.

Current policy state:

```text
HOME: active under tuned policy
DRAW: supported but not promoted
AWAY: disabled by default
```

AWAY should only be reopened with dedicated thresholds and walk-forward proof.

### 5. Opening vs Closing Odds and CLV

Importer now separates opening and closing odds when Football-Data provides Bet365 closing columns:

```text
Opening: B365H / B365D / B365A
Closing: B365CH / B365CD / B365CA
```

Backtester supports:

```bash
--odds-snapshot-type opening
--odds-snapshot-type closing
```

New stability report:

```bash
python -m backtesting.run_stability_report --runs 260-264 --min-bets 1
```

Important data status:

```text
Current DB has 1X2 closing odds only.
Opening odds count: 0
Closing odds count: 54,237
```

Therefore CLV is currently 0.00% because the historical DB has not yet been reimported with opening/closing separation.

### 6. Stability Diagnostics

The stability report now exposes:

```text
ROI
hit rate
profit/loss
max drawdown
average CLV
bets per season
bets per league
bets per selection
```

Recent DB metrics:

Holdout 2023/24 runs 260-264:

```text
bets: 6
hit rate: 0.667
ROI: +20.50%
P&L: +12.30
max drawdown: 10.00
CLV: 0.00% (opening odds unavailable)
```

Recent walk-forward block 210-259:

```text
bets: 32
hit rate: 0.781
ROI: +28.91%
P&L: +92.50
max drawdown: 20.00
CLV: 0.00% (opening odds unavailable)
```

Global stored real bets in DB:

```text
bets: 1,515
stake: 15,150.00
P&L: -1,480.00
ROI: -9.77%
hit rate: 0.450
```

By selection over all stored real bets:

```text
HOME: 1,029 bets | ROI -4.37%  | hit rate 0.521
AWAY:   467 bets | ROI -21.79% | hit rate 0.304
DRAW:    19 bets | ROI -6.58%  | hit rate 0.158
```

### 7. Additional Markets

Poisson probabilities added for:

```text
OVER_2_5
UNDER_2_5
BTTS_YES
BTTS_NO
```

Importer can now load Bet365 O/U 2.5 and BTTS when columns exist:

```text
B365>2.5 / B365<2.5
B365C>2.5 / B365C<2.5
B365GG / B365NG
B365CGG / B365CNG
```

Current status: probability and data support exist; no default betting policy is promoted for these markets yet.

## Quality Assessment

Code quality improved.

Positive:

```text
- Leakage-safe temporal ELO implementation.
- Form features use only prior matches.
- Meta-model is optional and reproducible via persisted file.
- Opening/closing distinction is now represented in importer and backtester.
- Stability metrics are separated from aggregate ROI.
- Tests increased to 71 passing.
```

Remaining concerns:

```text
- Backtester still performs repeated prior-match queries and can be optimized with temporal caches.
- Feature payload is stored in reason strings, not structured columns.
- Meta-model has training infrastructure but no walk-forward training/evaluation loop yet.
- Current DB needs reimport to populate opening odds and new markets.
```

## Reliability Assessment

Reliability is improved but not sufficient for real-money confidence.

Current reliability level: medium as a research engine, low as a live betting engine.

Why:

```text
- Positive holdout ROI exists but only on 6 bets.
- Walk-forward recent block has 32 bets, still low volume.
- Global stored history remains negative ROI.
- CLV cannot yet validate whether the model beats market movement.
- HOME-only profitability may be sampling noise until opening/CLV and larger OOS windows confirm it.
```

Minimum reliability gates before promotion:

```text
- opening-odds backtest over all 10 seasons
- CLV positive on average
- minimum bets per season/league
- positive or controlled drawdown in multiple seasons
- no hidden dependency on a single league or season
- meta-model evaluated strictly walk-forward
```

## Market Competitiveness

Current competitiveness: not proven.

The engine can identify narrow positive historical slices, but the betting market competitiveness is still unverified because:

```text
- 1X2 is highly efficient.
- Existing profitable slices have low volume.
- Existing CLV is unavailable because DB currently has closing-only odds.
- AWAY is structurally weak and should remain closed.
- DRAW support exists but has not proven stable.
```

The most promising path is not broader 1X2 threshold tuning. It is:

```text
1. reimport opening/closing odds
2. train meta-model walk-forward
3. evaluate CLV and stability
4. test O/U 2.5 and BTTS because Poisson naturally prices them
```

## What Works Well

```text
- The data/backtest pipeline is coherent and testable.
- Poisson calibration is reasonable.
- HOME-specific narrow policy can produce positive OOS slices.
- League-specific policy avoids forcing volume in weak leagues.
- New ELO/form/meta features create a better feature surface for selection.
- Stability report now reveals whether ROI depends on time/league/selection.
```

## What Is Bad

```text
- Overall historical betting ROI is still negative.
- AWAY is materially bad: -21.79% ROI over stored real bets.
- DRAW has too little volume and poor hit rate in stored bets.
- Current profitable results are too low-volume to trust.
- No usable CLV yet on the current DB.
- New O/U and BTTS markets are not yet backtested as betting policies.
```

## High Priority Next Changes

1. Reimport historical CSVs to populate opening/closing odds and O/U-BTTS columns.
2. Run opening-vs-closing calibration and stability reports over 10 seasons.
3. Train the selection meta-model on older seasons and validate on later seasons only.
4. Add structured feature columns or JSON metadata for backtest_bets instead of parsing reason text.
5. Add walk-forward evaluation for O/U 2.5 and BTTS with separate policies.
6. Keep AWAY disabled until a dedicated AWAY policy has positive OOS ROI and non-negative CLV.

## Lower Priority Changes

1. Optimize temporal feature computation with cached rolling state.
2. Add Asian handicap and double chance after O/U and BTTS are validated.
3. Add dashboard views only after CLV and stability are meaningful.
4. Add model artifact registry for meta-model versions.
5. Add richer calibration plots by market and selection.

## Final Verdict

The project is in a stronger engineering state, but not yet a competitive betting engine.

The next decisive test is not another threshold search. It is an opening-odds, walk-forward, CLV-aware validation over multiple seasons and leagues. If that shows positive CLV, controlled drawdown and enough volume, the engine becomes genuinely interesting. Without that, the current positive ROI slices should be treated as fragile research signals.
