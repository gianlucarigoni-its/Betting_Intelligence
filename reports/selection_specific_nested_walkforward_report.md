# Selection-Specific Nested Walk-Forward

## Structural Change

Added a nested walk-forward runner that:

- trains threshold selection separately for each market side
- evaluates each selection independently
- applies capital-readiness gates per selection
- applies a final combined portfolio gate

This removes the shared O/U threshold assumption.

## Hierarchical O/U Runs

Dataset: runs `590-614`, five leagues, five seasons, opening odds.

### Quality Objective

- OVER: 47 bets, ROI +12.53%, CLV -0.49%.
- UNDER: 24 bets, ROI +2.71%, CLV +2.40%.
- Combined: 71 bets, ROI +9.21%, CLV +0.49%.
- Result: FAIL due volume and confidence intervals.

### Volume-First Objective

- OVER: 408 bets, ROI +6.98%, CLV -1.21%.
- UNDER: 371 bets, ROI -10.40%, CLV +1.10%.
- Combined: 779 bets, ROI -1.30%, CLV -0.11%.
- Result: FAIL.

### Joint Win + Positive CLV Target

- OVER: 11 bets, ROI +45.91%, CLV +1.40%.
- UNDER: 2 bets, ROI -28.00%, CLV +5.38%.
- Combined: 13 bets, ROI +34.54%, CLV +2.01%.
- Result: FAIL due extremely low volume.

## Interpretation

Selection separation is necessary and materially improves the quality-focused portfolio. The strongest signal is the joint win/CLV OVER subset, but five seasons do not provide enough independent bets to validate it.

The next cycle must expand the historical window before changing the model again.
