# Betting Intelligence Engine - Stato del progetto

## Obiettivo
Costruire un tool locale, gratuito e scritto in Python per l'analisi statistica delle scommesse calcistiche, con focus iniziale sui Mondiali FIFA 2026. Il progetto deve essere scalabile verso altri tornei, club e sport.

## Stack attuale
- Python 3.12.x
- WSL2 Ubuntu
- SQLite
- SQLAlchemy
- Alembic
- Streamlit
- Plotly

## Cose già fatte
- Creata la cartella progetto in `~/Personal/Betting_Intelligence`.
- Inizializzato Git.
- Creati `README.md` e `.gitignore`.
- Creato il virtual environment `.venv`.
- Creato `config/settings.py` e verificato il percorso del database.
- Installate le dipendenze principali nel venv.

## Layer database
- Creato `database/base.py` con:
  - `engine`
  - `SessionLocal`
  - `Base`
  - `get_db()`
- Creato `database/models.py` con i primi modelli ORM:
  - `Sport`
  - `Competition`
  - `Team`
  - `Match`
  - `MatchStat`
  - `Bookmaker`
  - `Odd`
  - `Prediction`
  - `ScrapingLog`
  - `ApiCache`
- Creato `database/__init__.py`.
- Inizializzato Alembic in `database/migrations`.
- Configurato `alembic.ini`.
- Corretto `database/migrations/env.py` aggiungendo la root del progetto a `sys.path`.
- Creata e applicata con successo la migration iniziale.

## Seed e test
- Creato `database/seed.py` per popolare il DB.
- Creato `database/db_read_test.py` per verificare la lettura dei dati.
- Seed previsto:
  - sport `Football`
  - competizione `FIFA World Cup 2026`

## Problemi già risolti
- Errore Alembic per `sqlalchemy.url` duplicato in `alembic.ini`.
- Errore `ModuleNotFoundError: No module named 'database'` in Alembic.
- Errore di import anche nello script `database/seed.py`.
- Problemi con l'estensione SQLite di VS Code in WSL non bloccanti per il progetto.

## Stato attuale
- La base del progetto è pronta.
- Il database è versionato con Alembic.
- La prossima fase è verificare seed e test DB, poi iniziare lo scraper base o il modello Poisson.

## Prossimo step consigliato
1. Eseguire con successo il seed del database. - GIA FATTO!
2. Eseguire con successo il test di lettura del database. - GIA FATTO!
3. Creare la base dello scraper.
4. Iniziare il modulo `poisson_model.py`.

## Nota per una nuova chat
Se apri una nuova conversazione, puoi ripartire da qui: il database è già impostato, Alembic funziona e siamo pronti per la parte di scraping o modellazione predittiva.
