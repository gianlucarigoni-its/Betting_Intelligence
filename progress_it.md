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
- pytest
- requests
- BeautifulSoup4

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

## Seed e test database
- Creato `database/seed.py` per popolare il DB.
- Creato `database/db_read_test.py` per verificare la lettura dei dati.
- Eseguito con successo il seed del database.
- Eseguito con successo il test di lettura del database.
- Seed previsto:
  - sport `Football`
  - competizione `FIFA World Cup 2026`

## Layer scraping ELO completato
- Creato `scrapers/base_scraper.py` come base riutilizzabile per richieste HTTP con:
  - sessione persistente
  - header realistici
  - retry automatici
  - delay randomico tra richieste
- Creato `scrapers/eloratings_scraper.py` per leggere `https://eloratings.net/World.tsv`.
- Implementato il parser TSV con output strutturato in `EloTeamRecord`.
- Corretto un filtro troppo aggressivo sull'ELO che faceva scendere i record da 244 a 185.
- Validato il parser sul feed reale: il totale corretto è tornato a `244` record.

## Layer service ELO completato
- Creato `services/eloratings_sync_service.py`.
- Integrato il mapper reale `services/mappers/country_code_mapper.py`.
- Allineato il service allo schema ORM reale della tabella `teams`.
- Gestita la creazione automatica dello sport `football` se assente.
- Implementata la logica di sync con conteggi di:
  - `created`
  - `updated`
  - `unchanged`
  - `skipped`
  - `failed`
- Distinti correttamente i campi:
  - `country_code` come codice sorgente ELO
  - `iso_code_2` come normalizzazione ISO
  - `fifa_code` come identificatore calcistico stabile
- Confermato che il layer ELO attuale è chiuso per la struttura corrente del progetto.

## Test automatici completati
- Creato `pytest.ini` per rendere stabile il `pythonpath` durante i test.
- Creato `tests/test_eloratings_scraper.py`.
- Creato `tests/test_eloratings_sync_service.py`.
- Verificati con successo i casi principali del parser:
  - riga valida
  - riga corta
  - country code invalido
  - rank non valido
  - ELO non valido
  - parsing multiplo TSV
  - errore su TSV senza record validi
- Verificati con successo i casi principali del sync service:
  - creazione nuova squadra
  - aggiornamento squadra esistente
  - nessuna modifica
  - skip su metadata mancanti
  - fallback via `fifa_code`
- Stato test attuale:
  - `tests/test_eloratings_scraper.py` → `7 passed`
  - `tests/test_eloratings_sync_service.py` → `5 passed`

## Problemi risolti oggi
- Import errato verso `services.team_name_mapper`.
- Mismatch tra nomi del mapper ipotizzati e quelli realmente presenti nel progetto.
- `ModuleNotFoundError: No module named 'scrapers'` durante l'esecuzione di pytest.
- Parser ELO troppo restrittivo che scartava righe valide del feed.
- Mismatch tra `services/eloratings_sync_service.py` e il model ORM `Team`.
- Uso errato del campo `is_national_team`, non presente nello schema reale.

## Stato attuale
- Il database è stabile e versionato con Alembic.
- Il layer di scraping ELO è funzionante.
- Il layer di sincronizzazione ELO verso il database è funzionante.
- I test automatici del layer ELO sono verdi.
- Per la struttura attuale del progetto, questo layer può considerarsi chiuso e non va riaperto salvo:
  - modifiche allo schema del database
  - cambi al feed TSV di ELO Ratings
  - nuove regole di mapping o normalizzazione
  - cambi architetturali del progetto

## File principali aggiunti o aggiornati oggi
- `scrapers/base_scraper.py`
- `scrapers/eloratings_scraper.py`
- `services/eloratings_sync_service.py`
- `tests/test_eloratings_scraper.py`
- `tests/test_eloratings_sync_service.py`
- `pytest.ini`

## Prossimo step consigliato
1. Eseguire un audit finale dei dati caricati nel DB per le nazionali ELO.
2. Passare al layer successivo:
   - feature engineering
   - modello Poisson
   - calcolo edge / EV / Kelly

## Nota per una nuova chat
Se apri una nuova conversazione, puoi ripartire da qui: database e layer ELO sono operativi, testati e allineati allo schema reale. Il prossimo passo naturale è il layer predittivo.