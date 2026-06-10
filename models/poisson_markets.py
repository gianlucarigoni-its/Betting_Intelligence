"""Poisson-derived probabilities for natural football betting markets."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import poisson


@dataclass(frozen=True, slots=True)
class PoissonMarketProbabilities:
    home: float
    draw: float
    away: float
    over_25: float
    under_25: float
    btts_yes: float
    btts_no: float


def calculate_poisson_market_probabilities(
    lambda_home: float,
    lambda_away: float,
    *,
    max_goals: int = 10,
) -> PoissonMarketProbabilities:
    if lambda_home <= 0 or lambda_away <= 0:
        raise ValueError("lambda_home and lambda_away must be positive")
    if max_goals < 3:
        raise ValueError("max_goals must be at least 3")

    home = 0.0
    draw = 0.0
    away = 0.0
    over_25 = 0.0
    btts_yes = 0.0

    for home_goals in range(max_goals + 1):
        home_prob = poisson.pmf(home_goals, lambda_home)
        for away_goals in range(max_goals + 1):
            probability = home_prob * poisson.pmf(away_goals, lambda_away)
            if home_goals > away_goals:
                home += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away += probability
            if home_goals + away_goals >= 3:
                over_25 += probability
            if home_goals > 0 and away_goals > 0:
                btts_yes += probability

    total_1x2 = home + draw + away
    if total_1x2 <= 0:
        raise ValueError("poisson probability mass is zero")

    home /= total_1x2
    draw /= total_1x2
    away /= total_1x2
    over_25 = min(max(over_25, 0.0), 1.0)
    btts_yes = min(max(btts_yes, 0.0), 1.0)

    return PoissonMarketProbabilities(
        home=home,
        draw=draw,
        away=away,
        over_25=over_25,
        under_25=1.0 - over_25,
        btts_yes=btts_yes,
        btts_no=1.0 - btts_yes,
    )
