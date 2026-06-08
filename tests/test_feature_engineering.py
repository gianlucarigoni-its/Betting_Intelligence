"""
Test automatici per models/feature_engineering.py

Coprono:
- Formula ELO: correttezza probabilità, somma = 1.0, casi limite
- Confidenza: soglie MIN_MATCHES corrette
- FeatureExtractor: squadra trovata, squadra mancante, ELO mancante
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.feature_engineering import (
    MatchFeatures,
    ModelType,
    ConfidenceLevel,
    FeatureExtractor,
    compute_elo_win_probability,
    _confidence_from_matches,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_team(
    team_id: int,
    name: str,
    elo: float | None = 1800.0,
) -> MagicMock:
    """Crea un mock di Team con i campi minimi necessari."""
    team = MagicMock()
    team.id = team_id
    team.name = name
    team.canonical_name = name
    team.elo_rating = elo
    return team


# ── Test: compute_elo_win_probability ─────────────────────────────────────────

class TestComputeEloWinProbability:
    """La formula ELO deve produrre probabilità coerenti."""

    def test_somma_uguale_a_uno(self) -> None:
        """p_home + p_away + p_draw deve essere esattamente 1.0."""
        p_home, p_away, p_draw = compute_elo_win_probability(2000.0, 1800.0)
        assert abs(p_home + p_away + p_draw - 1.0) < 1e-6

    def test_squadra_piu_forte_ha_prob_maggiore(self) -> None:
        """La squadra con ELO più alto deve avere probabilità di vittoria > 0.5."""
        p_home, p_away, _ = compute_elo_win_probability(2100.0, 1700.0)
        assert p_home > p_away

    def test_squadre_pari_prob_simmetrica(self) -> None:
        """Con ELO identici p_home e p_away devono essere uguali."""
        p_home, p_away, _ = compute_elo_win_probability(1900.0, 1900.0)
        assert abs(p_home - p_away) < 1e-4

    def test_pareggio_massimo_con_squadre_pari(self) -> None:
        """Il pareggio è più probabile quando le squadre sono equilibrate."""
        _, _, draw_pari = compute_elo_win_probability(1900.0, 1900.0)
        _, _, draw_sbilanciato = compute_elo_win_probability(2200.0, 1400.0)
        assert draw_pari > draw_sbilanciato

    def test_home_advantage_aumenta_prob_casa(self) -> None:
        """Il bonus campo deve aumentare la probabilità della squadra di casa."""
        p_senza, _, _ = compute_elo_win_probability(1900.0, 1900.0, home_advantage=0.0)
        p_con, _, _ = compute_elo_win_probability(1900.0, 1900.0, home_advantage=100.0)
        assert p_con > p_senza

    def test_probabilita_sempre_tra_zero_e_uno(self) -> None:
        """Ogni probabilità deve essere compresa tra 0 e 1."""
        for elo_diff in [0, 100, 300, 600, 1000]:
            p_home, p_away, p_draw = compute_elo_win_probability(
                1800.0 + elo_diff, 1800.0
            )
            for p in (p_home, p_away, p_draw):
                assert 0.0 <= p <= 1.0


# ── Test: _confidence_from_matches ────────────────────────────────────────────

class TestConfidenceFromMatches:
    """Le soglie di confidenza devono rispettare le regole del sistema prompt."""

    def test_zero_partite_elo_only_low(self) -> None:
        model, conf = _confidence_from_matches(0, 0)
        assert model == ModelType.ELO_ONLY
        assert conf == ConfidenceLevel.LOW

    def test_sotto_soglia_elo_only(self) -> None:
        """4 partite (sotto MIN=5) → ELO_ONLY, LOW."""
        model, conf = _confidence_from_matches(4, 10)
        assert model == ModelType.ELO_ONLY
        assert conf == ConfidenceLevel.LOW

    def test_soglia_minima_poisson_medium(self) -> None:
        """5 partite per entrambe → POISSON, MEDIUM."""
        model, conf = _confidence_from_matches(5, 5)
        assert model == ModelType.POISSON
        assert conf == ConfidenceLevel.MEDIUM

    def test_tra_5_e_9_medium(self) -> None:
        model, conf = _confidence_from_matches(9, 9)
        assert model == ModelType.POISSON
        assert conf == ConfidenceLevel.MEDIUM

    def test_dieci_partite_high(self) -> None:
        """10+ partite → POISSON, HIGH."""
        model, conf = _confidence_from_matches(10, 10)
        assert model == ModelType.POISSON
        assert conf == ConfidenceLevel.HIGH

    def test_usa_il_minimo_tra_le_due(self) -> None:
        """Se una squadra ha 3 partite e l'altra 20 → conta il minimo (3 → LOW)."""
        model, conf = _confidence_from_matches(3, 20)
        assert model == ModelType.ELO_ONLY
        assert conf == ConfidenceLevel.LOW


# ── Test: FeatureExtractor ────────────────────────────────────────────────────

class TestFeatureExtractor:
    """FeatureExtractor deve produrre MatchFeatures coerenti dal DB."""

    def _make_extractor_with_teams(
        self,
        home: MagicMock,
        away: MagicMock,
        match_count: int = 0,
    ) -> FeatureExtractor:
        """
        Costruisce un FeatureExtractor con session mockata.
        Query .first() restituisce home poi away in sequenza.
        """
        session = MagicMock()

        # Simuliamo query().filter().first() → home, poi away
        query_mock = MagicMock()
        session.query.return_value = query_mock
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.side_effect = [home, away]
        filter_mock.count.return_value = match_count

        return FeatureExtractor(session)

    def test_extract_base_spain_germany(self) -> None:
        """Feature estratte per Spagna vs Germania devono essere coerenti."""
        spain = _make_team(1, "Spain", elo=2155.0)
        germany = _make_team(2, "Germany", elo=1932.0)
        extractor = self._make_extractor_with_teams(spain, germany)

        features = extractor.extract("Spain", "Germany")

        assert features.home_team_name == "Spain"
        assert features.away_team_name == "Germany"
        assert features.home_elo == 2155.0
        assert features.away_elo == 1932.0
        assert features.elo_diff == pytest.approx(223.0)
        assert features.is_neutral_venue is True

    def test_somma_prob_uguale_uno(self) -> None:
        """La somma delle tre probabilità deve essere 1.0."""
        home = _make_team(1, "Brazil", elo=1991.0)
        away = _make_team(2, "France", elo=2062.0)
        extractor = self._make_extractor_with_teams(home, away)

        features = extractor.extract("Brazil", "France")

        total = (
            features.home_elo_win_prob
            + features.away_elo_win_prob
            + features.draw_prob_elo
        )
        assert abs(total - 1.0) < 1e-6

    def test_squadra_non_trovata_raise(self) -> None:
        """Se una squadra non è nel DB deve sollevare ValueError."""
        session = MagicMock()
        query_mock = MagicMock()
        session.query.return_value = query_mock
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        # Entrambe le query (canonical_name e name) restituiscono None
        filter_mock.first.return_value = None

        extractor = FeatureExtractor(session)

        with pytest.raises(ValueError, match="non trovata nel DB"):
            extractor.extract("Squadra Fantasma", "Germany")

    def test_elo_mancante_raise(self) -> None:
        """Se una squadra ha ELO=None deve sollevare ValueError."""
        home = _make_team(1, "Spain", elo=None)
        away = _make_team(2, "Germany", elo=1932.0)
        extractor = self._make_extractor_with_teams(home, away)

        with pytest.raises(ValueError, match="ELO mancante"):
            extractor.extract("Spain", "Germany")

    def test_senza_partite_model_elo_only(self) -> None:
        """Con 0 partite nel DB il model_type deve essere ELO_ONLY."""
        home = _make_team(1, "Argentina", elo=2114.0)
        away = _make_team(2, "Colombia", elo=1982.0)
        extractor = self._make_extractor_with_teams(home, away, match_count=0)

        features = extractor.extract("Argentina", "Colombia")

        assert features.model_type == ModelType.ELO_ONLY
        assert features.confidence == ConfidenceLevel.LOW