# O/U Data Coverage Expansion

## Goal

Expand the hierarchical O/U opening backtest from five seasons to ten seasons to see whether the promising selection-specific signal scales above capital-readiness volume.

## Execution

Created runs `640-689` for five leagues and seasons `1415` through `2324`.

Only runs for seasons `1920` through `2324` produced O/U predictions and bets. Seasons `1415` through `1819` produced zero O/U bets because the database has no O/U odds snapshots for those seasons.

## Coverage Finding

Current odds snapshot coverage:

- `1X2`: available from 2014/2015.
- `OU_2_5`: available only from 2019/2020 onward.
- `BTTS`: absent from the database.

Therefore the historical expansion did not add O/U validation volume. It reproduced the five-season dataset.

## Validation Results

Selection-specific nested walk-forward on runs `640-689` matched the prior `590-614` result:

- Quality combined: 71 bets, ROI +9.21%, CLV +0.49%, readiness FAIL.
- Joint win+CLV combined: 13 bets, ROI +34.54%, CLV +2.01%, readiness FAIL.

Capital readiness on raw runs `640-689`:

- 1162 bets
- ROI -4.05%, ROI CI [-9.19%, +1.92%]
- CLV -0.18%, CLV CI [-0.53%, +0.16%]

## Verdict

Not capital-ready.

The current blocker is data coverage, not another threshold. The engine cannot statistically validate the rare high-quality subset until O/U/BTTS historical odds coverage is expanded or another reliable odds source is imported.

## Next Cycle

Add a market coverage diagnostic/guardrail and investigate/import additional O/U/BTTS odds data. Without more market data, further model tuning risks overfitting the 2019-2024 sample.
