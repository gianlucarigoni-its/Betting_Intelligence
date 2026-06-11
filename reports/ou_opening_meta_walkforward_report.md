# O/U Opening Meta-Model Walk-Forward Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence

## Purpose

This cycle tested whether the selection meta-model can improve the O/U opening signal after being enriched with market metadata and odds-snapshot metadata.

## Changes

- Added `market_type` and `odds_snapshot_type` to the meta-model feature set.
- `odds_snapshot_type` is parsed from backtest run notes (`opening` or `closing`).
- Updated walk-forward validation to preserve market/snapshot metadata.
- Added threshold sweep support to the walk-forward CLI.

## Verification

```text
.venv/bin/python -m pytest -q -s
81 passed in 2.17s
```

## Dataset

Opening O/U runs: 440-464

Baseline, all bets in the broad run:

```text
baseline_bets=1153
baseline_roi=-6.13%
baseline_clv=-0.36%
```

## Walk-Forward Results

Meta threshold sweep:

```text
0.550 -> meta_bets 309, meta_roi -2.77%, meta_clv -0.45%
0.580 -> meta_bets 145, meta_roi +3.62%, meta_clv +0.08%
0.590 -> meta_bets 120, meta_roi +7.59%, meta_clv +0.37%
0.600 -> meta_bets 95,  meta_roi +5.61%, meta_clv +0.59%
0.605 -> meta_bets 86,  meta_roi +11.13%, meta_clv +0.51%
0.610 -> meta_bets 79,  meta_roi +9.25%, meta_clv +0.67%
0.615 -> meta_bets 59,  meta_roi +12.20%, meta_clv +1.16%
0.620 -> meta_bets 52,  meta_roi +15.31%, meta_clv +0.68%
```

Best balance found so far:

```text
threshold 0.605
folds: 3
meta_bets: 86
meta_roi: +11.13%
meta_clv: +0.51%
```

Per-fold at threshold 0.605:

```text
2021/2022: 22 bets, ROI +19.95%, CLV -0.13%
2022/2023: 23 bets, ROI +17.13%, CLV +0.82%
2023/2024: 41 bets, ROI +3.02%, CLV +0.69%
```

## Verdict

The enriched meta-model is better than the raw O/U opening filter: it improves ROI and CLV compared with the baseline.

It is still not capital-ready because:

- Volume remains below the 100-bet floor on the best stable thresholds.
- Lower thresholds reach volume, but lose seasonal stability and/or CLV quality.
- The choice of threshold is still retrospective; it must be selected only on training seasons and validated on untouched seasons.

## Next Step

1. Turn the threshold sweep into a proper nested walk-forward selector: choose the threshold on training folds only, then lock it for the next holdout season.
2. Add a dedicated O/U meta-model label for CLV-positive reliability, not just win/loss.
3. Re-test with more O/U seasons so the 100-bet floor can be reached without weakening the gate.
