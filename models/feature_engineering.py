"""
Feature engineering per il modello Poisson bivariato.

Responsabilità: leggere dal DB i dati grezzi di squadre e partite
e restituire un oggetto MatchFeatures pronto per il layer predittivo.

Layer 3 — legge solo dal DB, non scrive mai.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models import Team, Match, MatchStat


# ── Costanti ──────────────────────────────────────────────────────────────────

# Vantaggio campo in punti ELO. Per WC2026 (campo neutro) usa 0.
# Per partite in casa vera usa 100 (valore standard ELO calcio).
HOME_ADVANTAGE_ELO: float = 0.0

# Soglia minima di partite per usare il modello Poisson completo.
# Sotto questa soglia → fallback a "elo_only".
MIN_MATCHES_FOR_POISSON: int = 5


# ── Enumerazioni ──────────────────────────────────────────────────────────────

class ModelType(str, Enum):
    """Tipo di modello usato per la predizione."""
    POISSON = "poisson"
    ELO_ONLY = "elo_only"


class ConfidenceLevel(str, Enum):
    """Livello di confidenza della predizione."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ── Dataclass output ──────────────────────────────────────────────────────────

@dataclass
class MatchFeatures:
    """
    Rappresenta tutte le feature estratte per una singola partita.

    Questo oggetto è l'interfaccia tra il layer dati (DB) e
    il layer predittivo (Poisson model). Il modello Poisson
    consuma solo questo oggetto, mai il DB direttamente.
    """

    # Identità squadre
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str

    # Feature ELO (sempre disponibili)
    home_elo: float
    away_elo: float
    elo_diff: float                  # home_elo - away_elo (positivo = home favorita)
    home_elo_win_prob: float         # probabilità vittoria home da ELO
    away_elo_win_prob: float         # probabilità vittoria away da ELO
    draw_prob_elo: float             # probabilità pareggio stimata da ELO

    # Feature Poisson da storico partite (None se dati insufficienti)
    home_attack_strength: Optional[float] = None   # forza attacco casa vs media
    home_defense_strength: Optional[float] = None  # forza difesa casa vs media
    away_attack_strength: Optional[float] = None
    away_defense_strength: Optional[float] = None
    league_avg_goals_home: Optional[float] = None  # media gol casa nel torneo
    league_avg_goals_away: Optional[float] = None  # media gol away nel torneo

    # Metadati qualità dato
    home_matches_count: int = 0
    away_matches_count: int = 0
    model_type: ModelType = ModelType.ELO_ONLY
    confidence: ConfidenceLevel = ConfidenceLevel.LOW

    # Venue
    is_neutral_venue: bool = True


# ── Funzioni pure ELO ─────────────────────────────────────────────────────────

def compute_elo_win_probability(
    elo_home: float,
    elo_away: float,
    home_advantage: float = HOME_ADVANTAGE_ELO,
) -> tuple[float, float, float]:
    """
    Calcola le probabilità di vittoria/pareggio/sconfitta da ELO rating.

    La formula ELO standard dà P(home vince) rispetto a P(away vince).
    Il pareggio viene stimato con un'approssimazione basata sulla
    vicinanza tra le due squadre: più sono equilibrate, più è probabile
    il pareggio.

    Args:
        elo_home: ELO rating squadra di casa.
        elo_away: ELO rating squadra ospite.
        home_advantage: bonus ELO per il fattore campo (0 = campo neutro).

    Returns:
        Tupla (p_home, p_away, p_draw) che somma a 1.0.

    Esempio:
        >>> compute_elo_win_probability(2155, 1932)
        (0.63, 0.27, 0.10)  # circa
    """
    # Formula ELO standard
    # Il 400 è la scala ELO: una differenza di 400 punti = ~91% di vittoria
    expected_home = 1.0 / (
        1.0 + math.pow(10, (elo_away - elo_home - home_advantage) / 400.0)
    )
    expected_away = 1.0 - expected_home

    # Stima probabilità pareggio:
    # Più le squadre sono vicine (diff ~0), più il pareggio è probabile.
    # Formula empirica calibrata sul calcio internazionale:
    # draw_base = 0.30 quando diff = 0, scende verso 0 con diff grande
    elo_diff = abs(elo_home - elo_away)
    draw_base = 0.30 * math.exp(-elo_diff / 600.0)

    # Ridistribuiamo la probabilità di pareggio sottraendola a home e away
    # proporzionalmente al loro peso relativo
    p_draw = draw_base
    p_home = expected_home * (1.0 - p_draw)
    p_away = expected_away * (1.0 - p_draw)

    # Normalizziamo per garantire che la somma sia esattamente 1.0
    total = p_home + p_away + p_draw
    return round(p_home / total, 4), round(p_away / total, 4), round(p_draw / total, 4)


def _confidence_from_matches(
    home_count: int,
    away_count: int,
) -> tuple[ModelType, ConfidenceLevel]:
    """
    Determina tipo di modello e confidenza in base ai dati disponibili.

    Regola (da system prompt):
        < 5 partite per una squadra → elo_only, confidenza LOW
        5-9 partite → poisson, confidenza MEDIUM
        10+ partite → poisson, confidenza HIGH
    """
    min_count = min(home_count, away_count)

    if min_count < MIN_MATCHES_FOR_POISSON:
        return ModelType.ELO_ONLY, ConfidenceLevel.LOW
    elif min_count < 10:
        return ModelType.POISSON, ConfidenceLevel.MEDIUM
    else:
        return ModelType.POISSON, ConfidenceLevel.HIGH


# ── Feature extractor principale ─────────────────────────────────────────────

class FeatureExtractor:
    """
    Estrae le feature necessarie al modello Poisson dal database.

    Uso:
        extractor = FeatureExtractor(session)
        features = extractor.extract("Spain", "Germany")
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def _get_team_by_name(self, name: str) -> Team:
        """
        Cerca una squadra per canonical_name o name (case-insensitive).

        Raises:
            ValueError: se la squadra non è trovata nel DB.
        """
        team = (
            self.session.query(Team)
            .filter(Team.canonical_name.ilike(name))
            .first()
        )
        if team is None:
            team = (
                self.session.query(Team)
                .filter(Team.name.ilike(name))
                .first()
            )
        if team is None:
            raise ValueError(
                f"Squadra '{name}' non trovata nel DB. "
                f"Verifica il canonical_name nella tabella teams."
            )
        return team

    def _count_matches(self, team_id: int) -> int:
        """Conta le partite disputate da una squadra (home + away)."""
        return (
            self.session.query(Match)
            .filter(
                (Match.home_team_id == team_id) |
                (Match.away_team_id == team_id)
            )
            .count()
        )

    def extract(
        self,
        home_team_name: str,
        away_team_name: str,
        is_neutral_venue: bool = True,
    ) -> MatchFeatures:
        """
        Punto di ingresso principale. Estrae tutte le feature per una partita.

        Args:
            home_team_name: Nome della squadra di casa (o designata come tale).
            away_team_name: Nome della squadra ospite.
            is_neutral_venue: True per WC2026 (campo neutro).

        Returns:
            MatchFeatures pronto per il modello Poisson.

        Raises:
            ValueError: se una delle squadre non è nel DB o manca l'ELO.
        """
        home_team = self._get_team_by_name(home_team_name)
        away_team = self._get_team_by_name(away_team_name)

        if home_team.elo_rating is None:
            raise ValueError(f"ELO mancante per {home_team_name}")
        if away_team.elo_rating is None:
            raise ValueError(f"ELO mancante per {away_team_name}")

        # Vantaggio campo: 0 su campo neutro, HOME_ADVANTAGE_ELO altrimenti
        advantage = 0.0 if is_neutral_venue else HOME_ADVANTAGE_ELO

        p_home, p_away, p_draw = compute_elo_win_probability(
            elo_home=home_team.elo_rating,
            elo_away=away_team.elo_rating,
            home_advantage=advantage,
        )

        home_count = self._count_matches(home_team.id)
        away_count = self._count_matches(away_team.id)
        model_type, confidence = _confidence_from_matches(home_count, away_count)

        # TODO (FASE 3): quando avremo lo storico partite, aggiungere qui
        # il calcolo di attack_strength e defense_strength da xG/goals.

        return MatchFeatures(
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            home_team_name=home_team.canonical_name or home_team.name,
            away_team_name=away_team.canonical_name or away_team.name,
            home_elo=home_team.elo_rating,
            away_elo=away_team.elo_rating,
            elo_diff=round(home_team.elo_rating - away_team.elo_rating, 1),
            home_elo_win_prob=p_home,
            away_elo_win_prob=p_away,
            draw_prob_elo=p_draw,
            home_matches_count=home_count,
            away_matches_count=away_count,
            model_type=model_type,
            confidence=confidence,
            is_neutral_venue=is_neutral_venue,
        )