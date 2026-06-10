"""Train and persist a lightweight selection meta-model from backtest history."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from backtesting.selection_meta_model import SelectionMetaModel
from database.base import SessionLocal

LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT = Path("config/selection_meta_model.pkl")


def _parse_run_ids(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    run_ids: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", maxsplit=1)
            run_ids.extend(range(int(start), int(end) + 1))
        else:
            run_ids.append(int(chunk))
    return run_ids or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", help="Run ids, e.g. 205-259 or 205,206")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    run_ids = _parse_run_ids(args.runs)

    with SessionLocal() as session:
        samples = SelectionMetaModel.load_training_samples(session, run_ids=run_ids)
        LOGGER.info("Training samples loaded: %d", len(samples))
        model = SelectionMetaModel.train(samples)
        model.save(args.output)
        LOGGER.info("Selection meta-model saved to %s", args.output)


if __name__ == "__main__":
    main()
