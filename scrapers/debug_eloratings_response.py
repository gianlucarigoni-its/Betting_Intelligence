from __future__ import annotations

import logging

from scrapers.base_scraper import BaseScraper


def main() -> None:
    """Fetch the raw response from the ELO ratings TSV endpoint and inspect it."""
    logging.basicConfig(level=logging.INFO)

    scraper = BaseScraper(base_url="https://eloratings.net")
    response = scraper.get("World.tsv")

    print("STATUS CODE:")
    print(response.status_code)
    print()

    print("FINAL URL:")
    print(response.url)
    print()

    print("CONTENT TYPE:")
    print(response.headers.get("Content-Type"))
    print()

    print("FIRST 1000 CHARS:")
    print(response.text[:1000])
    print()

    print("FIRST 20 LINES:")
    for index, line in enumerate(response.text.splitlines()[:20], start=1):
        print(f"{index:02d}: {line}")


if __name__ == "__main__":
    main()