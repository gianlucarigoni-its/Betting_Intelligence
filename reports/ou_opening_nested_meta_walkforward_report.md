# O/U Opening Nested Meta-Model Walk-Forward Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Purpose

The previous threshold sweep was useful but retrospective. This cycle added a nested walk-forward validator: for every outer holdout season, the meta-model threshold is selected only from earlier training seasons, then frozen for the next season.

## Changes

- Added `backtesting.run_selection_meta_nested_walkforward`.
- The runner selects thresholds using only inner train folds.
- The selected threshold is then applied to the next untouched outer holdout season.
- Added capital-readiness output directly to the nested validator.
- Added tests for threshold-selection ranking.

## Verification

```text
.venv/bin/python -m pytest -q -s
83 passed in 1.94s
```

## Default Quality Grid

Command shape:

```bash
.venv/bin/python -m backtesting.run_selection_meta_nested_walkforward --runs 440-464 --min-train-seasons 2 --min-inner-train-seasons 1 --min-meta-bets 20 --min-total-bets 100
```

Selected thresholds and outer folds:

```text
2021/2022: threshold 0.620, 13 bets, ROI +9.31%,  CLV -0.45%
2022/2023: threshold 0.610, 19 bets, ROI +9.37%,  CLV +0.95%
2023/2024: threshold 0.620, 26 bets, ROI +14.15%, CLV +0.86%
```

Aggregate:

```text
baseline: 1153 bets, ROI -6.13%, CLV -0.36%
meta: 58 bets, ROI +11.50%, CLV +0.59%
CAPITAL_READINESS=FAIL
ROI CI: [-5.55%, +26.78%]
CLV CI: [-0.92%, +2.06%]
```

Failure reasons:

```text
- volume below 100 bets
- ROI confidence interval crosses below zero
- CLV confidence interval crosses below zero
```

## Volume-Friendlier Grid

Command shape:

```bash
.venv/bin/python -m backtesting.run_selection_meta_nested_walkforward --runs 440-464 --thresholds 0.55,0.58,0.59,0.60 --min-train-seasons 2 --min-inner-train-seasons 1 --min-meta-bets 20 --min-total-bets 100
```

Selected thresholds and outer folds:

```text
2021/2022: threshold 0.600, 25 bets, ROI +18.12%, CLV -0.03%
2022/2023: threshold 0.600, 26 bets, ROI +9.85%,  CLV +0.95%
2023/2024: threshold 0.590, 55 bets, ROI -2.69%,  CLV +0.09%
```

Aggregate:

```text
baseline: 1153 bets, ROI -6.13%, CLV -0.36%
meta: 106 bets, ROI +5.29%, CLV +0.27%
CAPITAL_READINESS=FAIL
ROI CI: [-7.94%, +18.19%]
CLV CI: [-0.72%, +1.20%]
```

Failure reasons:

```text
- volume is enough, but ROI confidence interval crosses below zero
- CLV confidence interval crosses below zero
- latest outer fold is negative on ROI
```

## Verdict

The nested validator confirms that the enriched meta-model is directionally useful: it turns a negative broad O/U opening baseline into positive ROI and positive average CLV.

It is still not reliable enough for real capital:

- High-quality thresholds produce too little volume.
- Volume-friendly thresholds weaken ROI stability.
- CLV average is positive but not statistically robust.
- The 2023/2024 fold remains fragile when volume is increased.

Capital status:

```text
NOT CAPITAL READY
NOT MARKET COMPETITIVE ENOUGH FOR REAL MONEY
RESEARCH CANDIDATE ONLY
```

## Next High-Priority Step

The current meta-model label is win/loss. That is not aligned with the market-competitiveness objective. The next cycle should add a CLV-aware reliability label or scorer so the selector is trained to prefer bets that beat closing price, not only bets that happened to win.
