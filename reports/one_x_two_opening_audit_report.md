# 1X2 Opening Audit

## Purpose

Test whether the more liquid 1X2 market could provide a capital-ready path once HOME, DRAW and AWAY policies are exposed explicitly.

## Execution

Backtest runs `690-714` on seasons `1920,2021,2122,2223,2324`, opening odds, with HOME/DRAW/AWAY enabled and hierarchical strength blending set to `0.35`.

## Results

Calibration:

- Bets: 791
- ROI: -8.45%
- ROI CI: [-17.62%, +0.11%]
- CLV: -0.42%
- CLV CI: [-1.04%, +0.13%]
- ECE: 0.0089
- Brier: 0.2001

Selection readiness:

- AWAY: 418 bets, ROI -5.65%, CLV -1.27%
- DRAW: 9 bets, ROI -58.33%, CLV -0.22%
- HOME: 364 bets, ROI -10.43%, CLV +0.55%

## Verdict

Not capital-ready.

The calibration is not the issue anymore. The problem is structural market asymmetry: HOME is the only slice with positive average CLV, but it still loses money; AWAY and DRAW fail both stability and profitability.

This confirms that 1X2 is not a production candidate under the current Poisson generator and selector. The next useful move is not more threshold tuning.

## Next Step

Either import richer data/markets or add a market-aware promotion layer that can reject whole slices permanently instead of testing them as one blended market family.
