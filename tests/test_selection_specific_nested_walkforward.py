"""Tests for selection-specific nested walk-forward helpers."""

from types import SimpleNamespace

import pytest

from backtesting.run_selection_specific_nested_walkforward import _parse_selections, _rows_for_selection


def test_parse_selections_requires_non_empty_value() -> None:
    with pytest.raises(ValueError, match="at least one selection"):
        _parse_selections(" , ")


def test_rows_for_selection_filters_market_side() -> None:
    over = (SimpleNamespace(selection="OVER_2_5"), None, None, "opening")
    under = (SimpleNamespace(selection="UNDER_2_5"), None, None, "opening")

    assert _rows_for_selection([over, under], "OVER_2_5") == [over]
