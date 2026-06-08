from __future__ import annotations

import csv
import io
import logging
from dataclasses import asdict, dataclass
from typing import List, Optional

from scrapers.base_scraper import BaseScraper


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EloTeamRecord:
    """Structured representation of one national team's ELO row."""

    rank: int
    country_code: str
    elo_rating: int


class EloRatingsScraper(BaseScraper):
    """Scraper for extracting national team ELO ratings from eloratings.net."""

    TSV_PATH = "World.tsv"

    def __init__(self) -> None:
        super().__init__(base_url="https://eloratings.net")

    def fetch_tsv(self) -> str:
        """Download the TSV content containing world national team ratings."""
        response = self.get(self.TSV_PATH)
        return response.text

    def scrape_team_ratings(self) -> List[EloTeamRecord]:
        """Fetch and parse ELO ratings in one step."""
        tsv_content = self.fetch_tsv()
        return self.parse_tsv(tsv_content)

    def parse_tsv(self, tsv_content: str) -> List[EloTeamRecord]:
        """Parse TSV content into structured ELO team records."""
        records: List[EloTeamRecord] = []
        reader = csv.reader(io.StringIO(tsv_content), delimiter="\t")

        for row in reader:
            parsed_record = self._parse_row(row)
            if parsed_record is not None:
                records.append(parsed_record)

        if not records:
            raise ValueError("No team records were extracted from World.tsv.")

        LOGGER.info("Extracted %s ELO team records.", len(records))
        return records

    def to_dict_list(self, records: List[EloTeamRecord]) -> List[dict]:
        """Convert dataclass records to serializable dictionaries."""
        return [asdict(record) for record in records]

    def _parse_row(self, row: List[str]) -> Optional[EloTeamRecord]:
        """Parse a single TSV row into a structured record."""
        if len(row) < 4:
            return None

        rank_value = self._safe_parse_int(row[0])
        country_code = row[2].strip().upper()
        elo_value = self._safe_parse_int(row[3])

        if rank_value is None or not country_code or elo_value is None:
            return None

        if len(country_code) != 2:
            return None

        return EloTeamRecord(
            rank=rank_value,
            country_code=country_code,
            elo_rating=elo_value,
        )

    @staticmethod
    def _safe_parse_int(raw_value: str) -> Optional[int]:
        """Safely parse an integer, returning None when invalid."""
        cleaned_value = raw_value.replace(",", "").strip()
        if not cleaned_value.isdigit():
            return None
        return int(cleaned_value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    scraper = EloRatingsScraper()
    team_ratings = scraper.scrape_team_ratings()

    for record in team_ratings[:10]:
        print(record)