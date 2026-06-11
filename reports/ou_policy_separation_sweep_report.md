# O/U Policy Separation Sweep

## Purpose

Check whether separating `OVER_2_5` and `UNDER_2_5` selection rules can recover a capital-ready policy on the hierarchical O/U generator runs `590-614`.

## Observation

The O/U market now behaves asymmetrically:

- `OVER_2_5` can reach positive ROI, but CLV remains negative.
- `UNDER_2_5` can reach positive CLV, but ROI remains negative.

A combined policy sweep over the run history did not produce a capital-ready policy under the current thresholds.

## Practical Conclusion

This is structural, not just tuning noise.

The current generator and selector can produce either:

- apparent price capture without market confirmation, or
- market confirmation without profit conversion.

That means the next useful modification is not another threshold sweep on the same feature set. It is a stronger market-aware selection layer with explicit separation of OVER and UNDER promotion logic, plus a stricter deployment gate that refuses policies when the latest fold or CLV confidence interval is weak.

## Status

Not capital-ready.
