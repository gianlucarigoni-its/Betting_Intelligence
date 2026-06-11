# Meta-Model Probability Architecture Audit

## Structural Findings

The existing meta-model had two structural defects:

1. It ignored ELO and robust form features already calculated and persisted by the Poisson backtester.
2. It used `class_weight=balanced`, so `predict_proba` was optimized for class balance rather than calibrated event probability. Thresholds such as 0.55 or 0.60 therefore had unstable probabilistic meaning.

## Changes

- Added ELO difference, 5/10-match form, recent points, conceded trend, expected strength, and clean-sheet rates to the meta-model.
- Added feature scaling.
- Removed probability-distorting balanced class weights.

## Validation

Full suite: 88 passed.

Nested O/U opening runs `440-464`:

- Single calibrated model: 718 bets, ROI -2.78%, CLV -0.11%.
- Dual calibrated model: 1152 bets, ROI -6.05%, CLV -0.37%.
- Raw baseline: 1153 bets, ROI -6.13%, CLV -0.36%.

## Conclusion

The probability layer is now structurally more correct, but it cannot rescue the underlying signal. The single model reduces losses, while the dual model mostly reproduces the losing baseline. This proves that the primary bottleneck is the Poisson probability generator, not threshold selection.

The next structural change must improve the goal-distribution model itself.
