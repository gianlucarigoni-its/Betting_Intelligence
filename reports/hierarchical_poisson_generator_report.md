# Hierarchical Poisson Generator Audit

## Structural Problem

The corrected meta-model showed that the main bottleneck is not threshold selection. The baseline Poisson generator was using venue-specific team samples only, which are small and noisy. That structure is fragile for totals markets.

## Change

Added `overall_strength_weight` to the historical Poisson generator.

The new generator blends:

- venue-specific home/away attack and defense strength
- overall team attack and defense strength across all recent matches

The blend is geometric and leakage-safe because it only uses matches before the target match.

## O/U Opening Evaluation

New runs: `590-614`, five leagues, five seasons, opening odds, O/U 2.5, `overall_strength_weight=0.35`.

Raw stability:

- Bets: 1162
- ROI: -4.05%
- ROI CI: [-9.19%, +1.92%]
- CLV: -0.18%
- CLV CI: [-0.53%, +0.16%]

Previous raw O/U opening baseline (`440-464`):

- Bets: 1153
- ROI: -6.13%
- CLV: -0.36%

Nested meta-model on `590-614`:

- Bets: 693
- ROI: -1.04%
- ROI CI: [-7.50%, +5.89%]
- CLV: +0.08%
- CLV CI: [-0.34%, +0.55%]

## Market Slices

- `OVER_2_5`: ROI +2.32%, CLV -1.09%.
- `UNDER_2_5`: ROI -12.17%, CLV +0.99%.

This is not production-ready. Positive ROI without CLV is not reliable, and positive CLV with negative ROI is not enough without more evidence and better selection.

## BTTS Finding

BTTS backtests still generated zero records because the database currently has no BTTS odds snapshots. Snapshot counts only contain `1X2` and `OU_2_5`.

BTTS is therefore blocked by data availability, not model selection.

## Verdict

The hierarchical generator is a real structural improvement, but insufficient for capital readiness. It should remain as an experimental parameter, not a production default yet.

Next high-priority structural work:

1. Import real BTTS odds if Football-Data columns are available for the target seasons.
2. Add selection-specific O/U policy: OVER and UNDER must not share promotion logic.
3. Build a production candidate registry that refuses deployment unless latest fold ROI, CLV CI, and minimum volume gates all pass.
