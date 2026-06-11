# Selection-Specific Readiness Gate

## Problem

The O/U market showed asymmetric behavior:

- `OVER_2_5` can look profitable but lose CLV.
- `UNDER_2_5` can look market-consistent but lose ROI.

A total-level capital-readiness gate can hide this mismatch.

## Change

Added a selection-specific readiness evaluation path to the capital-readiness report.

Now the deployment report prints readiness for:

- TOTAL
- each selection slice in `BY_SELECTION`

This makes it harder to promote a blended policy that hides a weak leg.

## Validation

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_capital_readiness.py tests/test_stability_report.py -q -s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_selection_meta_model.py tests/test_selection_meta_nested_walkforward.py -q -s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -s`

## Verdict

This is a structural improvement to the promotion workflow, not a full solution.

The engine is still not capital-ready, but the readiness gate is now aligned with the observed market asymmetry.
