# Betting Intelligence Engine - Stato progetto

## Obiettivo
Costruire un tool locale e gratuito in Python per l'analisi statistica delle scommesse calcistiche, con focus iniziale sulle nazionali FIFA World Cup 2026 e con architettura pronta per scalare verso club, altri tornei e altri sport.

## Stack attuale
- Python 3.12.x.
- WSL2 Ubuntu.
- SQLite.
- SQLAlchemy.
- Alembic.
- pytest.
- requests.
- BeautifulSoup4.
- Streamlit.
- Plotly.

## Architettura
Il progetto segue un'architettura a layer:
- `config/` per configurazione ambiente e percorsi.
- `database/` per base SQLAlchemy, engine, modelli, seed e migrazioni.
- `scrapers/` per la sola raccolta dati.
- `services/` per orchestrazione, mapping e sincronizzazione.
- `models/` per i modelli predittivi e statistici futuri.
- `recommendation/` per la logica di raccomandazione delle scommesse.
- `dashboard/` per l'interfaccia Streamlit.
- `chatbot/` per l'integrazione locale con Ollama.
- `tests/` per la validazione automatica.

## Struttura progetto
La root del repository include attualmente:
- `.env`
- `README.md`
- `.gitignore`
- `requirements.txt`
- `requirements-lock.txt`
- `alembic.ini`
- `pytest.ini`
- `progress_it.md`
- `config/`
- `database/`
- `scrapers/`
- `services/`
- `models/`
- `recommendation/`
- `dashboard/`
- `chatbot/`
- `tests/`
- `data/`
- `logs/`

## Milestone completate
### Ambiente e repository
- Creata la cartella progetto in `~/Personal/Betting_Intelligence`.
- Inizializzato Git.
- Creati `README.md` e `.gitignore`.
- Creato il virtual environment `.venv`.
- Installate le dipendenze principali nel venv.
- Creato `config/settings.py` per centralizzare i percorsi base e il path del database.
- Verificato il percorso SQLite del database.

### Layer database
- Creato `database/base.py` con:
  - `engine`
  - `SessionLocal`
  - `Base`
  - `get_db()`
- Creato `database/models.py` con le prime entità ORM:
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
- Aggiornato `database/migrations/env.py` aggiungendo la root del progetto a `sys.path`.
- Creata e applicata con successo la migration iniziale.

### Seed e validazione DB
- Creato `database/seed.py` per popolare il database con dati di riferimento.
- Creato `database/db_read_test.py` per verificare la lettura dal database.
- Eseguito con successo il seed del database.
- Eseguito con successo il test di lettura del database.
- Il seed attuale include:
  - sport: `Football`
  - competizione: `FIFA World Cup 2026`

### Layer scraping ELO
- Creato `scrapers/base_scraper.py` come base HTTP riutilizzabile con:
  - sessione persistente
  - header realistici
  - retry automatici
  - delay randomico tra le richieste
- Creato `scrapers/eloratings_scraper.py` per leggere `https://eloratings.net/World.tsv`.
- Implementato il parsing TSV in record strutturati `EloTeamRecord`.
- Corretto un filtro ELO troppo aggressivo che faceva scendere i record validi da 244 a 185.
- Validato il parser sul feed reale e confermato il totale corretto di 244 record.
- Creato `scrapers/debug_eloratings_response.py` per ispezionare la risposta grezza del TSV durante il debug.

### Layer service ELO
- Creato `services/eloratings_sync_service.py`.
- Integrato il mapper reale `services/mappers/country_code_mapper.py`.
- Allineato il service allo schema ORM reale della tabella `teams`.
- Implementata la creazione automatica dello sport `football` se assente.
- Implementata la logica di sync con contatori per:
  - `created`
  - `updated`
  - `unchanged`
  - `skipped`
  - `failed`
- Separati chiaramente i campi:
  - `country_code` come codice sorgente ELO
  - `iso_code_2` come normalizzazione ISO
  - `fifa_code` come identificatore calcistico stabile
- Il layer di ingestione e sincronizzazione ELO è considerato stabile per lo schema attuale.

### Test automatici
- Creato `pytest.ini` per mantenere stabile il `pythonpath` durante i test.
- Creato `tests/test_eloratings_scraper.py`.
- Creato `tests/test_eloratings_sync_service.py`.
- Verificati con successo i casi principali del parser:
  - riga valida
  - riga corta
  - country code invalido
  - rank non valido
  - ELO non valido
  - parsing TSV multiplo
  - errore su TSV senza record validi
- Verificati con successo i casi principali del sync service:
  - creazione nuova squadra
  - aggiornamento squadra esistente
  - nessuna modifica
  - skip quando mancano i metadati
  - fallback tramite `fifa_code`
- Stato test attuale:
  - `tests/test_eloratings_scraper.py` → `7 passed`
  - `tests/test_eloratings_sync_service.py` → `5 passed`

## File chiave e responsabilità
### `database/models.py`
Definisce lo schema ORM completo per sport, competizioni, squadre, partite, statistiche match, bookmaker, quote, previsioni, log di scraping e cache API. È la sorgente di verità per la persistenza e contiene già campi pensati per i layer predittivi e di raccomandazione futuri.

### `config/settings.py`
Centralizza directory base del progetto, directory dati, path del database e directory log. Crea anche le cartelle necessarie se non esistono.

### `scrapers/base_scraper.py`
Fornisce un layer HTTP riutilizzabile con riuso della sessione, retry, header realistici e pacing anti-bot. Tutti i futuri scraper dovrebbero ereditare da questa base invece di duplicare la logica di richiesta.

### `scrapers/debug_eloratings_response.py`
Utility di debug usata per ispezionare la risposta grezza dell'endpoint TSV ELO e capire esattamente cosa restituisce il servizio remoto.

### `scrapers/eloratings_scraper.py`
Scarica e parsea il feed TSV ELO da eloratings.net. Converte le righe in record tipizzati e filtra i dati malformati prima che arrivino al layer service.

### `services/eloratings_sync_service.py`
Orchestra la sincronizzazione dai dati ELO al database. Fa matching, crea o aggiorna le squadre e mantiene una separazione pulita tra normalizzazione della sorgente e persistenza.

### `services/mappers/country_code_mapper.py`
Contiene il mapping autorevole tra i country code ELO e i metadati calcistici interni. È il layer principale di normalizzazione per mantenere coerente l'identità delle squadre tra fonti diverse.

## Decisioni tecniche
- `country_code` è trattato come identificatore della sorgente, non come primary key.
- `iso_code_2` e `fifa_code` sono salvati separatamente per migliorare il matching.
- `canonical_name` viene usato come campo stabile di normalizzazione.
- `services/` possiede orchestration e sync; `scrapers/` si occupa solo della raccolta dati.
- `database/` rimane l'unica source of truth per dashboard e chatbot.
- Logging e timestamp sono stati aggiunti per tracciare meglio i dati e facilitare il debug.
- Il layer ELO è stato completato come milestone autonoma prima di passare al predittivo.

## Problemi già risolti
- Corretto un mismatch negli import del layer service.
- Risolto un `ModuleNotFoundError` durante pytest stabilizzando i path Python.
- Corretto un parser che filtrava in modo troppo aggressivo righe ELO valide.
- Allineato il service allo schema reale del model `Team`.
- Rimossi assunti su campi che non esistono nello schema attuale.
- Confermato che il flusso ELO funziona end-to-end con il database attuale.

## Stato attuale
- Il database è stabile e versionato con Alembic.
- Il layer di scraping ELO funziona.
- Il layer di sync ELO verso il database funziona.
- I test del layer ELO sono verdi.
- La struttura del progetto è coerente ed è pronta per il layer predittivo successivo.

## Prossimi passi
1. Fare un audit dei record squadra già caricati nel database.
2. Passare al feature engineering.
3. Costruire il primo modello Poisson.
4. Aggiungere i calcoli di edge, EV e Kelly.
5. Avviare il recommendation engine e i profili di confidenza.
6. Costruire la dashboard Streamlit.

## Nota per una nuova chat
Se si apre una nuova conversazione, l'IA dovrebbe leggere prima questo file e assumere che:
- il database esiste già,
- Alembic è già configurato,
- la pipeline ELO è già funzionante,
- i test del layer ELO sono già passati,
- il prossimo passo naturale è il layer predittivo.

## Change log
- Completato lo scaffolding iniziale del progetto.
- Creato e migrato lo schema database.
- Costruito e validato lo scraper ELO.
- Costruito e validato il service di sync ELO.
- Aggiunti i test automatici e verificati come passanti.
