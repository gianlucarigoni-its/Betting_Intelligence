# O/U Dual Nested Meta-Model Walk-Forward Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Purpose

This cycle tested whether a dual meta-model can improve the signal further by combining a win-model and a CLV-positive model instead of using a single win/loss target.

## Changes

- Added `--use-dual-model` to the nested validator.
- The dual mode trains a win model and a CLV-positive model on the same training rows.
- The outer score can combine the two probabilities by mean or min.
- Added tests for the dual probability combiner.

## Verification

```text
.venv/bin/python -m pytest -q -s
87 passed in 1.87s
```

## Best Result So Far

Command shape:

```bash
.venv/bin/python -m backtesting.run_selection_meta_nested_walkforward --runs 440-464 --min-train-seasons 2 --min-inner-train-seasons 1 --min-meta-bets 20 --min-total-bets 100 --thresholds 0.55,0.58,0.59,0.60,0.605,0.61 --selection-objective volume_first --use-dual-model --dual-combination mean
```

Result:

```text
2021/2022: threshold 0.550, 36 bets, ROI +13.08%, CLV -0.65%
2022/2023: threshold 0.580, 7 bets, ROI +21.57%,  CLV +0.47%
2023/2024: threshold 0.580, 17 bets, ROI +23.82%, CLV +1.77%
```

Aggregate:

```text
meta bets: 60
meta ROI: +17.12%
meta CLV: +0.17%
ROI CI: [+1.07%, +30.38%]
CLV CI: [-0.97%, +1.46%]
drawdown_pct_of_stake: 4.12%
CAPITAL_READINESS=FAIL
```

Failure reasons:

```text
- volume below 100 bets
- CLV confidence interval crosses below zero
```

## Lower-Threshold Volume Test

Command shape:

```bash
.venv/bin/python -m backtesting.run_selection_meta_nested_walkforward --runs 440-464 --min-train-seasons 2 --min-inner-train-seasons 1 --min-meta-bets 20 --min-total-bets 100 --thresholds 0.50,0.52,0.54,0.55,0.56,0.58 --selection-objective volume_first --use-dual-model --dual-combination mean
```

Aggregate:

```text
meta bets: 191
meta ROI: +1.20%
meta CLV: -0.40%
ROI CI: [-10.79%, +10.64%]
CLV CI: [-1.26%, +0.42%]
CAPITAL_READINESS=FAIL
```

Interpretation:

- The dual model is the strongest signal so far on a quality basis.
- It still does not satisfy the volume floor and CLV confidence requirements at the same time.
- Lower thresholds buy volume, but the edge collapses into noise.

## Verdict

The engine is still not capital ready.

Current status:

```text
Best current signal: dual mean, but volume too low.
Volume-rich signal: not profitable enough.
```

## Next High-Priority Step

The next cycle should stop treating the selector as a binary classifier only. The promising direction is a ranker or calibrated ensemble that directly optimizes a joint target for ROI and CLV, or additional O/U seasons to give the nested selector enough sample size to reach the 100-bet floor without losing signal.
