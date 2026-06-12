# Recommendation Band Selection Walk-Forward Report

## Objective

Test whether selection-specific meta-models produce any promotable recommendation band without leakage.

## Changes

- Separated walk-forward training by selection instead of pooling OVER and UNDER.
- Kept low-confidence opportunities blocked.
- Retained CLV-positive as the default label target.
- Promoted only bands that pass minimum bets, minimum CLV count, and positive lower confidence bounds.

## Evidence

Dataset: O/U 2.5 opening runs `640-689`, five recent seasons.

Selection-specific CLV-positive validation:

- OVER_2_5:AGGRESSIVE: 1 bet, ROI -100.00%, CLV +10.78%, failed volume.
- OVER_2_5:BALANCED: 2 bets, ROI +58.50%, CLV +1.41%, failed volume and CLV lower bound.
- OVER_2_5:NO_BET: 268 bets, ROI +3.35%, CLV -1.22%, failed.
- UNDER_2_5:AGGRESSIVE: 6 bets, ROI -67.50%, CLV +2.37%, failed.
- UNDER_2_5:BALANCED: 21 bets, ROI -4.48%, CLV +2.33%, failed.
- UNDER_2_5:NO_BET: 232 bets, ROI -10.86%, CLV +0.71%, failed.

Promoted bands: none.
Capital ready: no.

## Assessment

Selection separation is the correct structure, but the underlying sample still does not support a capital-ready recommendation engine. The model can find isolated pockets with positive point estimates, but not enough stable volume or confidence to promote.

## Next priorities

1. Expand opening/closing coverage and diversity of leagues/competitions.
2. Validate the national-team dataset now that the importer works.
3. Build dedicated selection-specific policies for 1X2, O/U, BTTS, and future markets.
4. Require positive ROI CI and CLV CI per selection before any band is shown as actionable.
