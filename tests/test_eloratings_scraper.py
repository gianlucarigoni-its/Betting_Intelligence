from __future__ import annotations

from scrapers.eloratings_scraper import EloRatingsScraper, EloTeamRecord


def test_parse_row_returns_record_for_valid_row() -> None:
    scraper = EloRatingsScraper()

    row = [
        "1",
        "1",
        "ES",
        "2155",
        "1",
        "2189",
    ]

    record = scraper._parse_row(row)

    assert record == EloTeamRecord(
        rank=1,
        country_code="ES",
        elo_rating=2155,
    )


def test_parse_row_returns_none_for_short_row() -> None:
    scraper = EloRatingsScraper()

    record = scraper._parse_row(["1", "ES"])

    assert record is None


def test_parse_row_returns_none_for_invalid_country_code() -> None:
    scraper = EloRatingsScraper()

    row = [
        "1",
        "1",
        "ESP",
        "2155",
    ]

    record = scraper._parse_row(row)

    assert record is None


def test_parse_row_returns_none_for_non_positive_rank() -> None:
    scraper = EloRatingsScraper()

    row = [
        "0",
        "1",
        "ES",
        "2155",
    ]

    record = scraper._parse_row(row)

    assert record is None


def test_parse_row_returns_none_for_non_positive_elo() -> None:
    scraper = EloRatingsScraper()

    row = [
        "1",
        "1",
        "ES",
        "0",
    ]

    record = scraper._parse_row(row)

    assert record is None


def test_parse_tsv_returns_multiple_records() -> None:
    scraper = EloRatingsScraper()

    tsv_content = "\n".join(
        [
            "1\t1\tES\t2155\t1\t2189",
            "2\t2\tAR\t2114\t1\t2172",
            "3\t3\tFR\t2062\t1\t2135",
        ]
    )

    records = scraper.parse_tsv(tsv_content)

    assert len(records) == 3
    assert records[0] == EloTeamRecord(rank=1, country_code="ES", elo_rating=2155)
    assert records[1] == EloTeamRecord(rank=2, country_code="AR", elo_rating=2114)
    assert records[2] == EloTeamRecord(rank=3, country_code="FR", elo_rating=2062)


def test_parse_tsv_raises_when_no_valid_records_exist() -> None:
    scraper = EloRatingsScraper()

    tsv_content = "\n".join(
        [
            "bad\tdata",
            "x\ty\tzzz\tnope",
        ]
    )

    try:
        scraper.parse_tsv(tsv_content)
        assert False, "Expected ValueError to be raised for invalid TSV content."
    except ValueError as exc:
        assert str(exc) == "No team records were extracted from World.tsv."