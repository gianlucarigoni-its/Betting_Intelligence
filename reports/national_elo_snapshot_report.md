# National ELO Snapshot Report

## Objective

Prepare the engine for national-team and World Cup oriented recommendations by building leakage-safe pre-match ELO history for imported international matches.

## Changes

- Added `NationalEloSnapshotBuilder` for international matches.
- Added CLI `historical.run_national_elo_snapshot_build`.
- Persisted pre-match ratings into `team_rating_snapshots` with source `historical_international_results` and type `pre_match_elo`.
- Made the process idempotent and safe against duplicate team-date rows in the international dataset.

## Execution

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m historical.run_national_elo_snapshot_build --min-date 2000-01-01
```

Result:

- Matches seen: 25,344
- Rating snapshots created: 50,680
- Rating snapshots updated: 0

## Assessment

This improves the national-team signal layer but does not make the betting engine capital-ready because international betting odds are still absent in the local database.

Current international odds coverage: 0 snapshots.

## Next priorities

1. Import national-team opening/closing odds or create a dedicated odds ingestion path for World Cup/international fixtures.
2. Build national-team feature export using these ELO snapshots plus recent form.
3. Only after odds coverage exists: run opening-vs-closing CLV validation for national-team recommendations.
