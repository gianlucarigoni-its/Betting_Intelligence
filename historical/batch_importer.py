# historical/batch_importer.py
"""
Batch importer per dati storici da football-data.co.uk.

Scarica e importa più leghe e stagioni in un'unica esecuzione,
rispettando i rate limit e garantendo l'idempotenza.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from database.base import SessionLocal
from historical.football_data_importer import (
    FootballDataImportConfig,
    FootballDataImportResult,
    FootballDataImporter,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catalogo leghe — aggiungi/rimuovi liberamente
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LeagueConfig:
    """Configurazione di una singola lega."""

    code: str                    # Codice football-data.co.uk (es. "E0", "SP1")
    label: str                   # Nome leggibile (es. "Premier League")
    country: str                 # Paese (es. "England")
    seasons: tuple[str, ...]     # Codici stagione (es. ("2324", "2223"))


# Formato stagione: AABB dove AA = anno inizio (YY), BB = anno fine (YY)
# Esempio: "2324" → stagione 2023/24
LEAGUE_CATALOG: list[LeagueConfig] = [
    LeagueConfig(
        code="E0",
        label="Premier League",
        country="England",
        seasons=(
            "2324", "2223", "2122", "2021", "1920",
            "1819", "1718", "1617", "1516", "1415",
        ),
    ),
    LeagueConfig(
        code="SP1",
        label="La Liga",
        country="Spain",
        seasons=(
            "2324", "2223", "2122", "2021", "1920",
            "1819", "1718", "1617", "1516", "1415",
        ),
    ),
    LeagueConfig(
        code="D1",
        label="Bundesliga",
        country="Germany",
        seasons=(
            "2324", "2223", "2122", "2021", "1920",
            "1819", "1718", "1617", "1516", "1415",
        ),
    ),
    LeagueConfig(
        code="I1",
        label="Serie A",
        country="Italy",
        seasons=(
            "2324", "2223", "2122", "2021", "1920",
            "1819", "1718", "1617", "1516", "1415",
        ),
    ),
    LeagueConfig(
        code="F1",
        label="Ligue 1",
        country="France",
        seasons=(
            "2324", "2223", "2122", "2021", "1920",
            "1819", "1718", "1617", "1516", "1415",
        ),
    ),
]

_DEFAULT_DELAY_SECONDS = 2.5   # rispetta il rate limit del sito


# ---------------------------------------------------------------------------
# Result objects — trasparenti e loggabili
# ---------------------------------------------------------------------------

@dataclass
class SingleImportResult:
    """Esito dell'import di una singola (lega, stagione)."""

    league_code: str
    league_label: str
    season_code: str
    season_label: str
    matches_imported: int = 0
    odds_imported: int = 0
    skipped_rows: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class BatchImportSummary:
    """Sommario aggregato dell'intera sessione batch."""

    results: list[SingleImportResult] = field(default_factory=list)

    @property
    def successful(self) -> list[SingleImportResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> list[SingleImportResult]:
        return [r for r in self.results if not r.ok]

    @property
    def total_matches(self) -> int:
        return sum(r.matches_imported for r in self.successful)

    @property
    def total_odds(self) -> int:
        return sum(r.odds_imported for r in self.successful)

    def print_report(self) -> None:
        """Stampa un riepilogo leggibile a schermo."""
        divider = "=" * 65
        print(f"\n{divider}")
        print("  BATCH IMPORT — RIEPILOGO")
        print(divider)
        print(f"  Import riusciti : {len(self.successful)}/{len(self.results)}")
        print(f"  Match totali    : {self.total_matches:,}")
        print(f"  Quote totali    : {self.total_odds:,}")

        if self.failed:
            print(f"\n  ⚠ Falliti ({len(self.failed)}):")
            for r in self.failed:
                print(f"    [{r.league_code}] {r.season_label} → {r.error}")

        if self.successful:
            print(f"\n  Dettaglio per lega/stagione:")
            for r in self.successful:
                print(
                    f"    ✓ {r.league_label:<18} {r.season_label}  "
                    f"| match: {r.matches_imported:>3}  "
                    f"| quote: {r.odds_imported:>4}  "
                    f"| skip:  {r.skipped_rows:>2}"
                )
        print(divider + "\n")


# ---------------------------------------------------------------------------
# Funzioni pure di supporto
# ---------------------------------------------------------------------------

def _season_label(season_code: str) -> str:
    """
    Converte il codice stagione nel formato leggibile.

    Examples:
        >>> _season_label("2324")
        '2023/24'
        >>> _season_label("1920")
        '2019/20'
    """
    return f"20{season_code[:2]}/20{season_code[2:]}"


def _import_single(
    league: LeagueConfig,
    season_code: str,
) -> SingleImportResult:
    """
    Crea config + session + importer e delega il lavoro a FootballDataImporter.

    La session viene aperta e chiusa qui: ogni import è una transazione
    indipendente, quindi un fallimento non compromette gli altri.

    Args:
        league: Configurazione della lega.
        season_code: Codice stagione (es. "2324").

    Returns:
        SingleImportResult con statistiche o messaggio di errore.
    """
    season_label = _season_label(season_code)
    result = SingleImportResult(
        league_code=league.code,
        league_label=league.label,
        season_code=season_code,
        season_label=season_label,
    )

    config = FootballDataImportConfig(
        season_code=season_code,
        division_code=league.code,
        competition_name=league.label,
        country=league.country,
        season_label=season_label,
        # source_url=None → l'importer costruisce l'URL da season_code + division_code
    )

    try:
        with SessionLocal() as session:
            importer = FootballDataImporter(session)
            fd_result: FootballDataImportResult = importer.import_from_url(config)
            session.commit()

        result.matches_imported = fd_result.matches_imported
        result.odds_imported    = fd_result.odds_imported
        result.skipped_rows     = fd_result.skipped_rows

    except Exception as exc:
        logger.error(
            "Errore import [%s] %s: %s",
            league.code, season_label, exc,
            exc_info=True,
        )
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def run_batch_import(
    leagues: Optional[list[LeagueConfig]] = None,
    delay_seconds: float = _DEFAULT_DELAY_SECONDS,
) -> BatchImportSummary:
    """
    Esegue l'import batch di tutte le leghe e stagioni configurate.

    Args:
        leagues: Lista di leghe da importare. Default: LEAGUE_CATALOG.
        delay_seconds: Pausa tra ogni chiamata HTTP (rispetta il rate limit).

    Returns:
        BatchImportSummary con tutti i risultati aggregati.
    """
    target_leagues = leagues or LEAGUE_CATALOG
    summary = BatchImportSummary()

    total = sum(len(lg.seasons) for lg in target_leagues)
    logger.info("Avvio batch import: %d combinazioni lega/stagione", total)

    counter = 0
    for league in target_leagues:
        for season_code in league.seasons:
            counter += 1
            season_label = _season_label(season_code)

            logger.info(
                "[%d/%d] %s %s …",
                counter, total, league.label, season_label,
            )

            result = _import_single(league, season_code)
            summary.results.append(result)

            if result.ok:
                logger.info(
                    "  ✓ %d match, %d quote, %d skip",
                    result.matches_imported,
                    result.odds_imported,
                    result.skipped_rows,
                )
            else:
                logger.warning("  ✗ %s", result.error)

            time.sleep(delay_seconds)

    logger.info(
        "Batch completato: %d/%d ok | %d match | %d quote",
        len(summary.successful),
        len(summary.results),
        summary.total_matches,
        summary.total_odds,
    )
    return summary
