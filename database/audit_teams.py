"""
Audit dei record squadra nel database.

Controlla: totale squadre, campi critici mancanti,
duplicati potenziali e copertura delle 48 nazionali
qualificate al FIFA World Cup 2026.
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- path setup (stesso pattern di pytest.ini) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.base import SessionLocal
from database.models import Team


# Le 48 nazionali qualificate al Mondiale 2026
# Fonte: FIFA (aggiornato a marzo 2025)
FIFA_WC_2026_TEAMS: list[str] = [
    # CONMEBOL (6)
    "Argentina", "Brazil", "Colombia", "Uruguay", "Ecuador", "Venezuela",
    # UEFA (16)
    "Germany", "Spain", "France", "England", "Portugal", "Netherlands",
    "Belgium", "Italy", "Switzerland", "Croatia", "Austria", "Serbia",
    "Denmark", "Turkey", "Scotland", "Czech Republic",
    # CONCACAF (6 + host USA, Canada, Mexico)
    "United States", "Mexico", "Canada", "Panama", "Costa Rica", "Honduras",
    # AFC (8)
    "Japan", "South Korea", "Iran", "Saudi Arabia",
    "Australia", "Qatar", "Uzbekistan", "Jordan",
    # CAF (9)
    "Morocco", "Senegal", "Egypt", "Nigeria", "Cameroon",
    "Mali", "Ivory Coast", "South Africa", "Algeria",
    # OFC (1)
    "New Zealand",
    # Playoff/intercontinentale (2 posti ancora da assegnare - placeholder)
    # Non inclusi per non falsare la copertura
]


def _section(title: str) -> None:
    """Stampa un'intestazione di sezione leggibile."""
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


def audit_teams() -> None:
    """
    Esegue l'audit completo della tabella teams e stampa
    un report su console con tutti i controlli rilevanti.
    """
    session = SessionLocal()

    try:
        all_teams: list[Team] = session.query(Team).all()
        total = len(all_teams)

        # ── 1. Totale record ──────────────────────────────────
        _section("1. TOTALE RECORD")
        print(f"  Squadre nel DB  : {total}")
        print(f"  Attese da ELO   : 244")
        diff = total - 244
        if diff == 0:
            print("  ✅ Nessuna discrepanza")
        elif diff < 0:
            print(f"  ⚠️  Mancano {abs(diff)} squadre rispetto al feed ELO")
        else:
            print(f"  ⚠️  {diff} squadre in più rispetto al feed ELO")

        # ── 2. Campi critici NULL ─────────────────────────────
        _section("2. CAMPI CRITICI — VALORI NULL")
        critical_fields = [
            ("elo_rating",    lambda t: t.elo_rating),
            ("canonical_name",lambda t: t.canonical_name),
            ("country_code",  lambda t: t.country_code),
            ("iso_code_2",    lambda t: t.iso_code_2),
            ("fifa_code",     lambda t: t.fifa_code),
        ]
        for field_name, getter in critical_fields:
            null_teams = [t for t in all_teams if getter(t) is None]
            status = "✅" if not null_teams else "❌"
            print(f"  {status} {field_name:<18}: {len(null_teams)} NULL", end="")
            if null_teams:
                sample = ", ".join(
                    t.canonical_name or t.name or "???"
                    for t in null_teams[:3]
                )
                print(f"  → es: {sample}", end="")
            print()

        # ── 3. Duplicati potenziali ───────────────────────────
        _section("3. DUPLICATI POTENZIALI")
        from collections import Counter

        name_counts = Counter(
            t.canonical_name for t in all_teams if t.canonical_name
        )
        duplicates = {k: v for k, v in name_counts.items() if v > 1}

        if not duplicates:
            print("  ✅ Nessun duplicato su canonical_name")
        else:
            print(f"  ❌ {len(duplicates)} nomi duplicati:")
            for name, count in sorted(duplicates.items(), key=lambda x: -x[1]):
                print(f"     • {name}: {count}x")

        country_counts = Counter(
            t.country_code for t in all_teams if t.country_code
        )
        dup_codes = {k: v for k, v in country_counts.items() if v > 1}
        if not dup_codes:
            print("  ✅ Nessun duplicato su country_code")
        else:
            print(f"  ❌ {len(dup_codes)} country_code duplicati:")
            for code, count in sorted(dup_codes.items(), key=lambda x: -x[1]):
                print(f"     • {code}: {count}x")

        # ── 4. Copertura Mondiale 2026 ────────────────────────
        _section("4. COPERTURA FIFA WORLD CUP 2026 (48 squadre)")

        canonical_names_in_db = {
            (t.canonical_name or "").lower() for t in all_teams
        }
        team_names_in_db = {
            (t.name or "").lower() for t in all_teams
        }
        all_names_in_db = canonical_names_in_db | team_names_in_db

        found: list[str] = []
        missing: list[str] = []
        for team in FIFA_WC_2026_TEAMS:
            if team.lower() in all_names_in_db:
                found.append(team)
            else:
                missing.append(team)

        print(f"  ✅ Trovate  : {len(found)}/{len(FIFA_WC_2026_TEAMS)}")
        if missing:
            print(f"  ❌ Mancanti : {len(missing)}")
            for name in missing:
                print(f"     • {name}")
        else:
            print("  ✅ Tutte le nazionali del Mondiale sono presenti")

        # ── 5. Top 10 per ELO ────────────────────────────────
        _section("5. TOP 10 PER ELO RATING (sanity check)")
        top10 = sorted(
            [t for t in all_teams if t.elo_rating],
            key=lambda t: t.elo_rating,
            reverse=True,
        )[:10]
        for i, team in enumerate(top10, 1):
            print(f"  {i:>2}. {(team.canonical_name or team.name):<25} ELO: {team.elo_rating}")

        # ── 6. Distribuzione ELO ─────────────────────────────
        _section("6. DISTRIBUZIONE ELO RATING")
        elos = [t.elo_rating for t in all_teams if t.elo_rating]
        if elos:
            print(f"  Min : {min(elos):.0f}")
            print(f"  Max : {max(elos):.0f}")
            print(f"  Media: {sum(elos)/len(elos):.0f}")
            buckets = [(2200, "∞"), (2000, 2200), (1800, 2000),
                       (1600, 1800), (0, 1600)]
            for low, high in buckets:
                count = sum(1 for e in elos if e >= low and (high == "∞" or e < high))
                label = f"{low}–{high}" if high != "∞" else f"{low}+"
                bar = "█" * (count // 3)
                print(f"  {label:<12}: {count:>3}  {bar}")

        print(f"\n{'='*55}")
        print("  AUDIT COMPLETATO")
        print(f"{'='*55}\n")

    finally:
        session.close()


if __name__ == "__main__":
    audit_teams()