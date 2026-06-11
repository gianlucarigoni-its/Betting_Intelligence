# O/U Opening Nested Meta-Model: Configurable CLV Label Threshold

## Scope

Cycle target: make the secondary CLV meta-model label configurable, then retest the opening-odds O/U nested walk-forward on runs `440-464`.

Command shape:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m backtesting.run_selection_meta_nested_walkforward \
  --runs 440-464 \
  --min-train-seasons 2 \
  --min-inner-train-seasons 1 \
  --min-meta-bets 20 \
  --min-total-bets 100 \
  --thresholds 0.55,0.58,0.59,0.60,0.605,0.61 \
  --selection-objective volume_first \
  --use-dual-model \
  --dual-combination mean \
  --clv-threshold-pct <value>
```

## Code Change

- Added `--clv-threshold-pct` to the nested selection meta-model runner.
- Propagated the value through label generation, inner threshold selection, outer fold scoring, and dual-model training.
- The CLV label now uses `clv_pct >= clv_threshold_pct` instead of a hard-coded positive-only rule.

## Results

Tested CLV label thresholds: `0.0` and `-0.25`.

Both produced the same selected profile on the current O/U opening data:

| Metric | Baseline | Meta selector |
|---|---:|---:|
| Bets | 1153 | 130 |
| ROI | -6.13% | +1.66% |
| Profit/Loss | -706.50 | +21.60 |
| Avg CLV | -0.36% | +0.34% |
| ROI CI | n/a | [-9.81%, +14.36%] |
| CLV CI | n/a | [-0.65%, +1.28%] |
| Drawdown / stake | n/a | 7.38% |
| Capital readiness | FAIL | FAIL |

Season folds:

| Season | Meta bets | Meta ROI | Meta CLV | Hit rate |
|---|---:|---:|---:|---:|
| 2021/2022 | 23 | +9.83% | +0.49% | 0.739 |
| 2022/2023 | 45 | +1.16% | +0.33% | 0.644 |
| 2023/2024 | 62 | -1.00% | +0.29% | 0.629 |

## Interpretation

The selector is materially better than the raw O/U opening baseline: it cuts the losing baseline from 1153 bets to 130 filtered bets and moves both ROI and CLV positive on average.

It is still not capital-ready. The failure is not drawdown or average edge; the failure is statistical stability. ROI and CLV confidence intervals still cross below zero, and the latest fold is slightly negative on ROI despite positive CLV.

## Capital Readiness Verdict

Not ready for real capital.

Current state: promising research signal, not deployable betting engine. The market-competitiveness claim is still too weak because positive average CLV is not stable enough across the available holdout folds.

## Next High-Priority Cycle

1. Add a stricter production gate that combines model probability with minimum CLV probability/rank, not only a single averaged dual probability.
2. Add fold-level rejection rules: do not promote a policy if the latest holdout fold has negative ROI or if CLV CI low is below zero.
3. Increase eligible opening O/U volume or add adjacent Poisson-native markets, especially BTTS, so the meta-model can prove stability over more independent bets.
4. Add a report command that compares candidate policies side-by-side and marks only deployable policies as production candidates.
