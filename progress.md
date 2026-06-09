# Betting Intelligence Engine — Progress Context

Ultimo aggiornamento: 2026-06-09  
Stato: **FASE 4A — Model Improvement attiva**

---

## 1. Obiettivo del progetto

Costruire un tool locale e gratuito in Python per analisi statistica delle scommesse calcistiche.

Scope attivo:

- Premier League
- La Liga
- Bundesliga
- Serie A
- Ligue 1

Scope futuro:

- Nazionali FIFA World Cup 2026
- altri sport

Obiettivo finale:

```bash
Import → Feature Engineering → Poisson → Edge → Profili → Dashboard + Chatbot
```

Il progetto deve restare locale, versionato, testabile e con budget zero.

---

## 2. Stack tecnico

- Python 3.12
- WSL2 Ubuntu
- SQLite
- SQLAlchemy
- Alembic
- pytest
- requests
- BeautifulSoup4
- scipy / scikit-learn
- Streamlit
- Plotly
- Ollama

---

## 3. Architettura a layer

Regola fondamentale: non mischiare responsabilità tra layer.

```text
Layer 1: scrapers/ + api_clients/     → solo raccolta dati
Layer 2: database/ + models ORM       → solo storage e persistenza
Layer 3: models/                      → modelli predittivi/statistici
Layer 4: recommendation/              → classificazione e profili betting
Layer 5: dashboard/ + chatbot/        → presentazione e interazione
```

Cartelle principali:

```text
config/
database/
scrapers/
services/
historical/
models/
backtesting/
recommendation/
dashboard/
chatbot/
tests/
data/
logs/
```

---

## 4. Stato sintetico milestone

```text
FASE 1  Setup + DB + Alembic                         ✅ completata
FASE 2  Scraper ELO + Import storico                 ✅ completata
FASE 3  Poisson + Backtesting + Calibration           ✅ completata
FASE 3C Batch 5 leghe × 5 stagioni + fair odds        ✅ completata
FASE 4A Model Improvement                             🔄 attiva
FASE 5  Dashboard Streamlit                           ⏳ futura
FASE 6  Chatbot Ollama                                ⏳ futura
```

---

## 5. Componenti completati

### Database e Alembic

File principali:

- `database/base.py`
- `database/models.py`
- `database/seed.py`
- `database/migrations/`
- `alembic.ini`

Tabelle principali già presenti:

- `sports`
- `competitions`
- `teams`
- `matches`
- `match_stats`
- `bookmakers`
- `odds`
- `predictions`
- `historical_data_imports`
- `team_rating_snapshots`
- `historical_odd_snapshots`
- `backtest_runs`
- `backtest_bets`
- `scraping_logs`
- `api_cache`

Migration importanti:

- initial schema
- team metadata upgrade
- historical/backtest tables
- `is_bet` su `backtest_bets`
- `fair_prob` su `historical_odd_snapshots`

Nota SQLite/Alembic:

Ogni `ADD COLUMN NOT NULL` deve usare `server_default`.

Esempio:

```python
op.add_column(
    "table_name",
    sa.Column("field_name", sa.Boolean(), nullable=False, server_default=sa.true()),
)
```

---

### Scraping ELO

File:

- `scrapers/base_scraper.py`
- `scrapers/eloratings_scraper.py`
- `scrapers/debug_eloratings_response.py`
- `services/eloratings_sync_service.py`
- `services/mappers/country_code_mapper.py`

Stato:

- parser TSV ELO validato
- sync verso DB funzionante
- 244 record ELO corretti dal feed reale
- mapping country/ISO/FIFA stabilizzato
- creazione automatica sport `football` se assente

---

### Feature engineering

File:

- `models/feature_engineering.py`

Funzionalità:

- estrazione feature per match
- probabilità ELO
- `ModelType`
- `ConfidenceLevel`
- fallback `ELO_ONLY` sotto soglia partite

Stato:

- test verdi
- validato su casi base e match di esempio

---

### Modello Poisson

File:

- `models/poisson_model.py`

Funzionalità:

- calcolo lambda casa/trasferta
- distribuzione scoreline Poisson
- probabilità 1X2
- most likely score
- differenza campo neutro/non neutro

Stato:

- test verdi
- modello funzionante ma non ancora abbastanza forte per battere il mercato

---

### Value metrics

File:

- `models/value_metrics.py`

Funzionalità:

- `edge_pct`
- `ev`
- `kelly_fraction`
- `quarter_kelly_fraction`
- validazione input probabilità/quote

Formula:

```text
Edge% = (prob_modello - prob_bookmaker) × 100
EV    = (prob_modello × quota) - 1
Kelly = (prob × quota - 1) / (quota - 1)
```

---

### Recommendation engine

File:

- `recommendation/profile_engine.py`

Profili implementati:

| Profilo | Regola indicativa |
|---|---|
| SAFE | edge > 3%, confidence HIGH |
| VALUE | edge > 5%, confidence MED/HIGH |
| RISKY | edge > 8% |
| HIGH_RISK | edge > 12% |
| LOW_RISK | edge > 2%, HIGH su favorito |
| NO_BET | default |

Stato:

- implementato
- funzionante
- da evolvere solo dopo miglioramento modello

---

### Prediction persistence

File:

- `services/prediction_persistence_service.py`

Stato:

- prediction persistite nel DB
- output operativo del modello interrogabile da dashboard/chatbot futuri

Campi gestiti:

- `model_version`
- `model_type`
- `market_level`
- `market_type`
- `market_category`
- `selection`
- `estimated_prob`
- `estimated_odd`
- `bookmaker_prob`
- `bookmaker_odd`
- `edge_pct`
- `expected_value`
- `kelly_fraction`
- `profile_tag`
- `recommendation_score`
- `confidence_level`
- `reasoning`
- `is_correct`
- `actual_result`

---

## 6. Historical data e backtesting

File principali:

- `historical/football_data_importer.py`
- `historical/batch_importer.py`
- `backtesting/persistence_service.py`
- `backtesting/historical_poisson_backtester.py`
- `backtesting/diagnostics.py`
- `backtesting/calibration_report.py`
- `backtesting/run_calibration.py`
- `backtesting/run_football_data_backtest.py`

Fonti dati:

- `football-data.co.uk`
- quote storiche Bet365 1X2
- dati match conclusi

Il backtester:

- usa rolling window temporalmente onesta
- ogni match usa solo partite precedenti
- usa split casa/trasferta
- usa shrinkage verso media lega
- salva tutte le selezioni HOME/DRAW/AWAY come prediction
- marca `is_bet=True` solo sulla giocata effettiva
- liquida le bet come `won/lost/push`

---

## 7. Anomalie chiuse

### `run.total_bets` gonfiato

Problema iniziale:

```text
run.total_bets mostrava 825 invece dei soli record is_bet=True
```

Verifica finale:

```python
all_records = (
    self._session.query(BacktestBet)
    .filter(BacktestBet.backtest_run_id == run_id)
    .all()
)

bets = [r for r in all_records if r.is_bet]

run.total_bets = len(bets)
```

Stato:

```text
✅ chiuso
```

Il campo ora conta solo bet reali.

---

### Probabilità bookmaker senza fair odds

Problema:

```python
implied_prob = 1.0 / odd
```

Questa probabilità include il margine bookmaker.

Soluzione:

- aggiunta colonna `fair_prob`
- importer calcola probabilità normalizzate senza overround
- backtester usa `fair_prob` con fallback a `implied_prob`

Formula:

```python
implied_probs = {
    selection: 1.0 / odd
    for selection, odd in decimal_odds.items()
}

implied_prob_total = sum(implied_probs.values())

fair_probs = {
    selection: implied_prob / implied_prob_total
    for selection, implied_prob in implied_probs.items()
}

overround_pct = (implied_prob_total - 1.0) * 100.0
```

Backtester:

```python
bookmaker_probability = (
    odds_snapshot.fair_prob
    if odds_snapshot.fair_prob is not None
    else odds_snapshot.implied_prob
)
```

Verifica DB:

```text
historical_odd_snapshots
record totali: 26.850
fair_prob valorizzato: 26.850
avg_margin_removed: 0.0181
```

Stato:

```text
✅ chiuso
```

---

## 8. Batch completo validato

Comando usato:

```bash
python -m backtesting.run_calibration     --seasons 2324,2223,2122,2021,1920
```

Leghe:

- Premier League
- La Liga
- Bundesliga
- Serie A
- Ligue 1

Stagioni:

- 2023/2024
- 2022/2023
- 2021/2022
- 2020/2021
- 2019/2020

Import finale dopo rigenerazione quote:

```text
25/25 import riusciti
0 nuovi match
26.850 quote rigenerate
```

I match erano già presenti; sono state rigenerate le quote con `fair_prob`.

---

## 9. Calibration report finale

Run IDs finali:

```text
34, 35, 36, 37, 38,
39, 40, 41, 42, 43,
44, 45, 46, 47, 48,
49, 50, 51, 52, 53,
54, 55, 56, 57, 58
```

Risultati:

```text
Prediction totali : 18.573
Bet reali         : 170
Non-bet           : 18.403
Brier Score       : 0.2020
ECE               : 0.0090
```

Interpretazione:

- ECE ottimo
- modello ben calibrato
- probabilità realistiche
- Brier buono ma migliorabile
- ROI aggregato negativo
- modello non batte il mercato in modo sistematico

Breakdown selezioni:

```text
AWAY
n=6191
prob=0.318
win=0.317
brier=0.1962

DRAW
n=6191
prob=0.243
win=0.249
brier=0.1864

HOME
n=6191
prob=0.439
win=0.434
brier=0.2233
```

Osservazione importante:

```text
HOME è la categoria con Brier peggiore.
```

Probabile area di miglioramento:

- home advantage
- forza squadra
- attacco/difesa separati
- stima lambda più ricca

---

## 10. Risultato economico del benchmark

Il batch 5x5 ha generato:

```text
170 bet reali
stake unitario: 10
stake totale stimato: 1.700
P&L aggregato stimato: circa -143.7
ROI aggregato stimato: circa -8.45%
```

Conclusione:

```text
Il modello è calibrato, ma non profittevole.
```

Interpretazione tecnica:

La pipeline funziona; il collo di bottiglia non è più infrastrutturale.

Il problema residuo è il layer predittivo:

```text
Poisson rolling + medie home/away + shrinkage
```

non contiene abbastanza informazione per trovare edge reali contro il bookmaker.

---

## 11. Decisione architetturale attuale

Non passare ancora a:

- dashboard
- chatbot
- recommendation engine avanzato

Motivo:

```text
La dashboard visualizzerebbe un modello ben calibrato ma con ROI negativo.
```

Prima bisogna migliorare il modello.

---

## 12. FASE 4A attiva — Model Improvement

Priorità consigliata:

1. Inspect di `models/poisson_model.py`
2. Migliorare stima lambda
3. Introdurre forza squadra
4. Valutare Dixon-Coles
5. Rieseguire batch 5x5
6. Confrontare Brier/ECE/ROI contro benchmark attuale

Possibili evoluzioni:

### Opzione A — Team strength rolling

Creare rating squadra interno basato su risultati storici.

Pro:

- semplice
- locale
- nessuna nuova fonte dati

Contro:

- meno sofisticato di ELO vero

---

### Opzione B — Attack/Defense strength separati

Stima separata:

```text
home_attack_strength
home_defense_strength
away_attack_strength
away_defense_strength
```

Pro:

- coerente con Poisson classico
- migliora lambda
- implementazione ragionevole

Contro:

- richiede attenzione su sample size e shrinkage

---

### Opzione C — Dixon-Coles correction

Corregge la dipendenza tra goal casa/trasferta, soprattutto nei punteggi bassi.

Pro:

- molto adatto al calcio
- migliora 0-0, 1-0, 0-1, 1-1

Contro:

- più complesso
- richiede stima parametri

---

## 13. Prossimo step operativo consigliato

Prima inspect del modello attuale.

Comandi:

```bash
grep -n "lambda_home" models/poisson_model.py
```

```bash
sed -n '1,220p' models/poisson_model.py
```

Poi decidere il primo intervento tra:

```text
A. attack/defense strength separati
B. club/team ELO rolling
C. Dixon-Coles
```

Consiglio operativo:

```text
Partire da attack/defense strength separati.
```

È il miglior compromesso tra semplicità, impatto e coerenza con il modello Poisson già esistente.

---

## 14. Comandi utili

### Test

```bash
pytest
```

```bash
python -m compileall database models historical backtesting recommendation services scrapers
```

### Calibration completa

```bash
python -m backtesting.run_calibration     --seasons 2324,2223,2122,2021,1920
```

### Verifica fair_prob

```bash
sqlite3 data/betting.db "
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN fair_prob IS NOT NULL THEN 1 ELSE 0 END) AS with_fair_prob,
    ROUND(AVG(implied_prob - fair_prob), 4) AS avg_margin_removed
FROM historical_odd_snapshots;
"
```

### Verifica total_bets

```bash
grep -n "total_bets" backtesting/persistence_service.py
```

Output corretto atteso:

```python
run.total_bets = len(bets)
```

### Verifica DB Alembic

```bash
alembic current
```

```bash
alembic history
```

---

## 15. Regole operative per nuove chat

Quando riprendi il progetto in una nuova chat:

1. Leggi questo file per capire stato e prossima fase.
2. Non ripartire da dashboard/chatbot.
3. Non modificare file esistenti senza inspect-first.
4. Prima di generare codice, chiedere o eseguire:
   - `grep -n "def " file.py`
   - `grep -n -A 30 "class Nome" file.py`
   - `sed -n 'X,Yp' file.py`
5. Restare nella FASE 4A finché il benchmark 5x5 non migliora.
6. Usare il benchmark attuale come baseline:

```text
Brier Score: 0.2020
ECE: 0.0090
ROI: circa -8.45%
Bet: 170
Prediction: 18.573
```

Ogni modifica al modello deve essere giudicata contro questa baseline.

---

## 16. Commit suggerita per questa milestone

```bash
git add .

git commit -m "feat: add fair odds support and complete multi-league calibration benchmark"
```

Commit alternativa più breve:

```bash
git commit -m "feat: validate fair odds calibration benchmark"
```

---

## 17. Sintesi per il prossimo assistente

Il progetto è una betting intelligence pipeline locale in Python.

La pipeline dati e backtesting è ormai valida:

```text
Import storico
→ Quote Bet365
→ Fair odds
→ Poisson rolling
→ Edge/EV
→ Backtest
→ Calibration report
```

Il benchmark 5 leghe × 5 stagioni dice:

```text
Il modello è ben calibrato ma non profittevole.
```

Quindi la prossima fase non è UI, ma **miglioramento del modello predittivo**.

Priorità immediata:

```text
Inspect models/poisson_model.py e migliorare lambda con attack/defense strength separati.
```
