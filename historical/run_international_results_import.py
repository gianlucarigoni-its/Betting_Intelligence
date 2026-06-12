"""Import men's senior international results into the local database."""

from __future__ import annotations

import argparse

from database.base import SessionLocal
from historical.international_results_importer import DEFAULT_RESULTS_URL, InternationalResultsImporter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_RESULTS_URL)
    parser.add_argument("--min-date", default="2000-01-01")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = InternationalResultsImporter(session).import_from_url(args.url, min_date=args.min_date)
    print(result)


if __name__ == "__main__":
    main()
