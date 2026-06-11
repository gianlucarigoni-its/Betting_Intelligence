# O/U 2.5 Corrected Poisson and Slice Readiness Report

Date: 2026-06-11
Project path: /home/rigoni_g/Personal/Betting_Intelligence
Runtime note: commands were executed directly inside the WSL Linux project path because the Codex shell is already attached to WSL; the equivalent Windows wrapper is `wsl -d Ubuntu --cd /home/rigoni_g/Personal/Betting_Intelligence -- <command>`.

## Purpose

This cycle re-tested O/U 2.5 after finding a probability bug in the Poisson natural markets and added a slice-level capital-readiness validator with temporal checks.

## Code Changes

- Fixed `models/poisson_markets.py`: `over_25`, `under_25`, `btts_yes` and `btts_no` are now computed from exact Poisson formulas, not from the truncated score grid used for 1X2.
- Added regression tests proving O/U and BTTS probabilities do not depend on `max_goals` truncation.
- Added `backtesting.run_policy_slice_readiness_report` to validate a filtered policy slice by run ids, league, selection, market, edge range, model probability, odds cap, ROI CI, drawdown and per-season stability.

## Verification

```text
.venv/bin/python -m py_compile models/poisson_markets.py tests/test_poisson_markets.py backtesting/run_policy_slice_readiness_report.py
.venv/bin/python -m pytest -q -s
80 passed in 2.84s
```

The plain `pytest -q` command hit a pytest capture temp-file error before collecting tests. Re-running with `-s` completed successfully.

## Corrected Broad O/U Results

Opening odds, corrected runs 440-464:

```text
bets: 1764
ROI: -6.78%
ROI CI: [-11.17%, -2.40%]
CLV: -0.36%
CLV CI: [-0.64%, -0.09%]
Capital readiness: FAIL
```

Closing odds, corrected runs 465-489:

```text
bets: 1738
ROI: -4.95%
ROI CI: [-9.42%, -0.62%]
Capital readiness: FAIL
```

Interpretation: the broad O/U policy is rejected. The exact probability fix did not create a robust broad-market edge.

## Narrow OVER-Only Tests

Opening OVER-only, runs 490-514, edge 5-8, model probability >= 0.55:

```text
bets: 339
ROI: +10.28%
ROI CI: [+1.33%, +19.59%]
CLV: -1.35%
CLV CI: [-2.00%, -0.76%]
Capital readiness: FAIL because CLV is materially negative
```

Closing OVER-only, runs 515-539, same filter:

```text
bets: 347
ROI: +6.04%
ROI CI: [-2.90%, +15.79%]
Capital readiness: FAIL because ROI CI low is negative
```

Interpretation: historical ROI exists in some OVER slices, but the opening signal does not beat closing. That is not competitive enough for real capital.

## Bundesliga Closing Slice

Candidate from corrected broad closing runs 465-489:

```text
league: Bundesliga
selection: OVER_2_5
edge: [5.0, 9.0)
model_probability: >= 0.55
bookmaker_odds: <= 2.00
snapshot: closing
```

Minimal closing-only gate:

```text
CAPITAL_READINESS=PASS
bets=112
ROI=+15.06%
ROI CI=[+0.54%, +29.13%]
drawdown_pct_of_stake=5.36%
```

Per-season stability:

```text
2019/2020: bets=23, ROI=+16.13%
2020/2021: bets=15, ROI=+1.80%
2021/2022: bets=22, ROI=+30.91%
2022/2023: bets=28, ROI=+21.50%
2023/2024: bets=24, ROI=+0.29%
```

Strict temporal gate with minimum season ROI 2.0%:

```text
CAPITAL_READINESS=FAIL
failures:
- season 2020/2021 ROI +1.80% < 2.00%
- season 2023/2024 ROI +0.29% < 2.00%
```

Opening version of the same slice, runs 440-464:

```text
CAPITAL_READINESS=FAIL
bets=96
ROI=+1.68%
ROI CI=[-14.83%, +18.52%]
CLV=-1.43%
CLV CI=[-2.53%, -0.25%]
negative seasons: 2020/2021, 2021/2022, 2023/2024
```

Search result: scanning Bundesliga OVER closing grids found zero candidates with at least 100 total bets, at least 15 bets per season, positive aggregate ROI CI, and every season ROI >= 2.0%.

## Capital Readiness Verdict

The engine is still not ready for real-capital deployment.

Why:

- Broad O/U remains negative.
- The best opening OVER slice has positive historical ROI but materially negative CLV.
- The best closing Bundesliga OVER slice is interesting, but too fragile by season and not supported at opening odds.
- No tested O/U candidate currently satisfies both volume and temporal robustness under stricter criteria.

Current usable status:

```text
1X2 HOME opening: research candidate only, low volume
O/U 2.5 broad: rejected
O/U 2.5 Bundesliga OVER closing: research candidate only, not capital-ready
BTTS: blocked by missing historical odds source
AWAY/DRAW: not proven for live use
```

## Next High-Priority Production Steps

1. Add an automated opening-first policy search that requires positive CLV CI, positive ROI CI and per-season stability before showing any candidate.
2. Add walk-forward slice selection: choose thresholds on past seasons only, then validate on the next unseen season.
3. Persist feature payloads per bet or prediction: lambda, ELO, form windows, market probability, bookmaker probability and selected policy flags.
4. Train market-specific meta-models for O/U and 1X2 separately, then compare kept-bet vs rejected-bet ROI/CLV.
5. Increase historical market data coverage, especially more O/U seasons and a BTTS source, because current robust candidates are volume-limited.
