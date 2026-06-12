# Recommendation Band Walk-Forward Report

## Objective

Validate recommendation bands without temporal leakage and block any band that does not pass capital-readiness criteria.

## Changes

- Added temporal walk-forward scoring for recommendation bands.
- Derived confidence from out-of-sample meta-model probability.
- Added a hard gate that prevents low-confidence opportunities from entering actionable bands.
- Added CLV-positive training as the default market-competitiveness target.
- Required minimum volume plus positive ROI and CLV confidence-interval lower bounds before promotion.

## Evidence

Dataset: O/U 2.5 opening runs `640-689`, five recent seasons, minimum three training seasons.

Win-target validation after the safety gate:

- AGGRESSIVE: 21 bets, ROI -11.67%, average CLV +2.03%, failed volume and confidence intervals.
- BALANCED: 90 bets, ROI -9.59%, average CLV -0.27%, failed.
- Promoted bands: none.

CLV-positive target validation:

- All 530 holdout opportunities were classified as NO_BET.
- Promoted bands: none.
- Capital ready: no.

## Assessment

The new gate is safer and more honest than edge-only classification. It prevents the engine from presenting an unvalidated high-edge opportunity as actionable. Current O/U data do not contain enough stable out-of-sample market-beating signal for any recommendation band.

## Next priorities

1. Expand genuine opening/closing odds coverage beyond five seasons and beyond five club leagues.
2. Add international/national-team odds; match results alone cannot validate betting recommendations.
3. Calibrate the meta-model probability temporally before defining confidence thresholds.
4. Validate selection-specific models rather than pooling OVER and UNDER.
5. Keep every actionable band disabled until its ROI and CLV lower confidence bounds are positive.
