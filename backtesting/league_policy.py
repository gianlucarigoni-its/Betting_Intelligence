"""League-specific betting policy storage.

This allows tuning to produce a stable per-league selection policy that can be
reused by calibration and holdout validation runners.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LeagueBettingPolicy:
    allow_home_bets: bool = True
    allow_draw_bets: bool = False
    min_edge_pct: float = 5.0
    max_edge_pct: float = 6.0
    min_model_probability: float = 0.55
    max_bookmaker_odds: float = 1.8
    home_min_form_goal_diff_delta: float | None = None
    draw_min_edge_pct: float = 4.0
    draw_max_edge_pct: float | None = 9.0
    draw_min_model_probability: float = 0.24
    draw_max_bookmaker_odds: float = 4.2
    draw_max_lambda_gap: float | None = 0.25
    draw_max_abs_form_goal_diff_delta: float | None = 0.35
    away_min_edge_pct: float = 99.0
    away_min_model_probability: float = 0.58
    away_max_bookmaker_odds: float = 1.8
    allow_away_bets: bool = False
    min_prior_matches: int = 5
    shrinkage_matches: int = 10
    recent_form_half_life_matches: float = 0.0
    home_lambda_multiplier: float = 1.0
    away_lambda_multiplier: float = 1.0


class LeaguePolicyStore:
    """Load and save league policies from a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, LeagueBettingPolicy]:
        if not self.path.exists():
            return {}

        data = json.loads(self.path.read_text(encoding="utf-8"))
        policies: dict[str, LeagueBettingPolicy] = {}
        for league_label, payload in data.items():
            policies[league_label] = LeagueBettingPolicy(**payload)
        return policies

    def save(self, policies: dict[str, LeagueBettingPolicy]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {league_label: asdict(policy) for league_label, policy in policies.items()}
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

