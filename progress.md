# Betting Intelligence Engine — Progress Context

Ultimo aggiornamento: 2026-06-11  
Stato: **FASE 4B — Probabilistic Signal Improvement attiva**

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
FASE 4A Model Improvement                             ✅ completata
FASE 4B Probabilistic Signal Improvement              🔄 attiva
FASE 5  Dashboard Streamlit                           ⏳ futura
FASE 6  Chatbot Ollama                                ⏳ futura
```

Decisione attuale:

```text
Non passare ancora a dashboard/chatbot.
La pipeline funziona, ma il segnale di betting non e' ancora abbastanza
robusto per essere considerato competitivo.
```

---

## 4B. Piano operativo — Probabilistic Signal Improvement

Priorita' concreta della fase attiva:

```text
1. Aggiungere ELO storico pre-match per ogni partita.
2. Aggiungere feature di forma robuste su finestre 5/10 match.
3. Creare un meta-model leggero sopra il Poisson per selezionare edge affidabili.
4. Separare le policy HOME / DRAW / AWAY senza regole condivise implicite.
5. Usare opening vs closing odds e CLV quando i dati sono disponibili.
6. Valutare stabilita' per stagione, lega, drawdown, hit rate e volume minimo.
7. Estendere i mercati naturali del Poisson: Over/Under 2.5 e BTTS prima di Asian handicap e double chance.
```

Regola di fase:

```text
Non cercare solo soglie migliori.
La priorita' e' migliorare il segnale probabilistico e dimostrare se il value esiste prima del movimento del mercato.
Ogni step chiuso deve avere codice, test/verifica e commit dedicato.
Se uno step richiede un componente successivo, si puo' implementare quel componente e poi tornare sullo step precedente.
```

Vincolo operativo WSL:

```bash
wsl -d Ubuntu --cd /home/rigoni_g/Personal/Betting_Intelligence -- .venv/bin/python -m pytest -q
```

Nel runtime Codex attuale il filesystem Linux e' visibile direttamente da:

```bash
/home/rigoni_g/Personal/Betting_Intelligence
```

Ambiente virtuale:

```bash
source .venv/bin/activate
```

---

## 4B. Step 1 chiuso

Implementato e verificato:

```text
- ELO storico pre-match ricostruito in ordine temporale.
- Feature di forma robuste su finestre 5/10 con punti, goal difference, clean sheet e trend concessi.
- Correttore lambda guidato da ELO, configurabile ma disattivato di default.
- Runner calibration/holdout aggiornati per esporre i nuovi parametri.
- Test dedicati aggiunti per ELO, forma e integrazione backtester.
```

Stato test:

```text
61 passed
```

Decisione:

```text
La base probabilistica e' stata estesa senza alterare il Poisson base.
Il peso ELO resta 0.0 di default finche' non viene validato da walk-forward.
```

---

## 4B. Step 2 chiuso

Implementato e verificato:

```text
- Meta-model leggero di selezione basato su logistic regression.
- Feature del meta-model: selection, edge, odds, model probability, bookmaker probability, lega, lambda_home/lambda_away e distanza modello-mercato.
- Training CLI: backtesting.run_selection_meta_training.
- Gate opzionale nel backtester tramite --selection-meta-model-path.
- Policy di selezione rese esplicite per HOME, DRAW e AWAY nella logica del backtester.
- Holdout validation corretta per applicare davvero le policy HOME/DRAW/AWAY.
```

Stato test:

```text
64 passed
```

Decisione:

```text
Il meta-model e' disponibile ma non e' promosso come default.
Va addestrato su stagioni precedenti e validato walk-forward prima di usarlo in policy stabile.
AWAY resta disabilitato di default e puo' riaprire solo con policy dedicata e testata.
```

---

## 4B. Step 3 chiuso

Implementato e verificato:

```text
- Importer Football-Data aggiornato per separare opening odds e closing odds Bet365 quando B365CH/B365CD/B365CA sono disponibili.
- Backtester configurabile con odds_snapshot_type = opening | closing.
- Report di stabilita' con ROI, hit rate, drawdown massimo e CLV medio.
- CLI: backtesting.run_stability_report.
```

Comandi utili:

```bash
python -m backtesting.run_calibration --odds-snapshot-type opening
python -m backtesting.run_calibration --odds-snapshot-type closing
python -m backtesting.run_stability_report --runs 205-259 --min-bets 5
```

Stato test:

```text
68 passed
```

Decisione:

```text
Il codice ora consente di misurare se il segnale batte il closing price.
I dati storici esistenti vanno reimportati per popolare opening odds quando la sorgente CSV contiene le colonne B365C*.
```

---

## 4B. Step 4 chiuso

Implementato e verificato:

```text
- Probabilita' Poisson per Over/Under 2.5.
- Probabilita' Poisson per BTTS yes/no.
- RollingPoissonProbabilities esteso con over_25, under_25, btts_yes, btts_no.
- Settlement esteso per OVER_2_5, UNDER_2_5, BTTS_YES, BTTS_NO.
- Importer Football-Data pronto a caricare quote Bet365 O/U 2.5 e BTTS quando le colonne sono disponibili.
```

Stato test:

```text
71 passed
```

Decisione:

```text
I mercati naturali del Poisson sono disponibili a livello probabilistico e dati.
Non sono ancora promossi come betting policy di default: servono reimport quote, backtest opening/closing e stability report dedicato.
```

---

## 4B. Step 5 chiuso - opening/closing, CLV e meta walk-forward

Implementato e verificato:

```text
- Reimport completo Football-Data su 50 combinazioni lega/stagione.
- Opening odds e true closing odds Bet365 separate e aggiornate in modo idempotente.
- Vecchie closing odds importate da B365H/B365D/B365A corrette con B365CH/B365CD/B365CA quando disponibili.
- Quote non valide <= 1.0 scartate senza bloccare l'import dei match.
- Backtest opening odds su run 265-314.
- Backtest closing odds su run 315-339.
- CLV calcolato come opening_odds / closing_odds - 1.
- Walk-forward del selection meta-model su piu' stagioni opening.
- Modello finale opening salvato in config/selection_meta_opening.pkl.
```

Dati reimportati:

```text
Batch reimport: 50/50 successi
Existing odds aggiornate a true closing: 25,667
1X2 opening odds: 26,850
1X2 closing odds: 54,249
OU_2_5 opening odds: 17,892
OU_2_5 closing odds: 17,906
BTTS odds: 0 (colonne non presenti nei CSV disponibili)
```

Opening odds backtest, run 265-314:

```text
bets: 21
hit rate: 0.810
ROI: +39.00%
P&L: +81.90
max drawdown: 10.00
avg CLV: +1.41%
selection: HOME only
```

Closing odds backtest, run 315-339:

```text
bets: 17
hit rate: 0.706
ROI: +20.59%
P&L: +35.00
max drawdown: 20.50
avg CLV: 0.00% (closing-vs-closing)
selection: HOME only
```

Meta-model walk-forward opening:

```text
min_train_seasons=3: 2 folds, 15 baseline bets, 15 meta bets, ROI +38.93%, P&L +58.40
min_train_seasons=2: 3 folds, 18 baseline bets, 18 meta bets, ROI +42.72%, P&L +76.90
Brier holdout range: 0.2106 - 0.2168
```

Decisione:

```text
Il segnale opening e' migliore del closing e mostra CLV medio positivo, quindi la prova e' interessante.
Non basta ancora per promuovere il motore a sistema betting competitivo: volume molto basso, solo HOME, CLV non stabile in tutte le stagioni e meta-model senza uplift sulle bet selezionate.
```

Stato test:

```text
78 passed
```

---

## 4B. Step 6 chiuso - O/U 2.5 validato ma non promosso

Implementato e verificato:

```text
- Runner backtest esteso a market_type = 1X2 | OU_2_5.
- Policy separata per OVER_2_5 e UNDER_2_5.
- CLI di calibration allineata al nuovo mercato.
- Stability report con bootstrap CI su ROI e CLV.
- Test dedicati per O/U e confidence interval.
```

Risultati O/U 2.5 opening, run 340-389:

```text
bets: 1756
ROI: -7.09%
roi_ci: [-11.56%, -2.91%]
avg CLV: -0.34%
clv_ci: [-0.62%, -0.04%]
```

Risultati O/U 2.5 closing, run 390-439:

```text
bets: 1730
ROI: -4.64%
roi_ci: [-9.69%, -0.29%]
avg CLV: 0.00%
```

Decisione:

```text
O/U 2.5 e' stato messo in produzione come mercato supportato e misurabile, ma non e' competitivo abbastanza per essere promosso come policy live con capitale reale.
Il closing e' meno negativo dell'opening, ma nessuno dei due supera la soglia di affidabilita'.
```

Stato test:

```text
78 passed
```

---

## 4B. Step 7 chiuso - gate capitale reale

Implementato e verificato:

```text
- Capital readiness gate con criteri minimi su volume, CLV count, ROI CI, CLV CI e drawdown.
- CLI: backtesting.run_capital_readiness_report.
- Test dedicati per pass/fail del gate.
```

Risultato 1X2 opening, run 265-314:

```text
CAPITAL_READINESS=FAIL
bets=21
roi=+39.00%
roi_ci=[+9.14%, +64.33%]
clv=+1.41%
clv_ci=[-1.88%, +4.47%]
failures: volume insufficiente, CLV CI low negativa
```

Risultato O/U 2.5 opening, run 340-389:

```text
CAPITAL_READINESS=FAIL
bets=1756
roi=-7.09%
roi_ci=[-11.56%, -2.91%]
clv=-0.34%
clv_ci=[-0.62%, -0.04%]
failures: ROI CI low negativa, CLV CI low negativa
```

Decisione:

```text
Il motore non e' pronto per capitale reale.
Da ora ogni policy candidata deve passare il capital readiness gate prima di essere considerata live.
```

Stato test:

```text
78 passed
```


---

## 4B. Step 8 chiuso - correzione O/U naturale e slice readiness

Implementato e verificato:

```text
- Corretto il calcolo Poisson dei mercati naturali: OVER/UNDER 2.5 e BTTS non dipendono piu' dalla griglia troncata max_goals.
- Aggiunti test di regressione per assicurare che O/U e BTTS siano calcolati con formule Poisson esatte.
- Aggiunto validator di policy slice: backtesting.run_policy_slice_readiness_report.
- Il validator filtra per run, lega, selection, mercato, edge, probabilita' modello, quota massima e controlla ROI CI, drawdown e stabilita' per stagione.
- Aggiunto gate temporale opzionale con numero minimo di bet per stagione e ROI minimo per stagione.
```

Risultati corretti O/U 2.5 broad:

```text
Opening runs 440-464: bets 1764, ROI -6.78%, ROI CI [-11.17%, -2.40%], CLV -0.36%, CLV CI [-0.64%, -0.09%], FAIL.
Closing runs 465-489: bets 1738, ROI -4.95%, ROI CI [-9.42%, -0.62%], FAIL.
```

Risultati slice migliore trovata:

```text
Bundesliga OVER_2_5 closing, runs 465-489
edge [5.0, 9.0), model_probability >= 0.55, odds <= 2.00
bets 112, ROI +15.06%, ROI CI [+0.54%, +29.13%], drawdown 5.36% stake
```

Decisione:

```text
La slice Bundesliga OVER closing e' solo research candidate.
Non e' promossa a capitale reale: a opening odds fallisce ROI/CLV, e con ROI minimo per stagione 2.0% fallisce 2020/2021 e 2023/2024.
La ricerca parametrica non ha trovato candidate O/U con almeno 100 bet totali, 15 per stagione, ROI CI aggregata positiva e ROI >= 2.0% in ogni stagione.
```

Stato test:

```text
80 passed con: .venv/bin/python -m pytest -q -s
```

Report dedicato:

```text
reports/ou25_corrected_poisson_slice_readiness_report.md
```


---

## 4B. Step 9 chiuso - meta-model O/U opening arricchito

Implementato e verificato:

```text
- Il meta-model ora include market_type e odds_snapshot_type nel feature set.
- odds_snapshot_type viene letto dai notes del backtest run (opening/closing).
- Walk-forward del meta-model aggiornato con CLV medio e soglia meta configurabile.
- Aggiunta sweep automatica delle soglie per evitare tuning manuale opaco.
```

Risultati O/U opening, run 440-464:

```text
Baseline broad: 1153 bet, ROI -6.13%, CLV -0.36%.

Sweep soglie meta:
0.55  -> 309 bet, ROI -2.77%, CLV -0.45%
0.58  -> 145 bet, ROI +3.62%, CLV +0.08%
0.59  -> 120 bet, ROI +7.59%, CLV +0.37%
0.60  -> 95 bet,  ROI +5.61%, CLV +0.59%
0.605 -> 86 bet, ROI +11.13%, CLV +0.51%
0.61  -> 79 bet, ROI +9.25%, CLV +0.67%
0.615 -> 59 bet, ROI +12.20%, CLV +1.16%
0.62  -> 52 bet, ROI +15.31%, CLV +0.68%
```

Decisione:

```text
Il meta-model e' migliorato davvero: batte il baseline su ROI e CLV.
Non e' ancora pronto per capitale reale perche' non raggiunge insieme volume minimo, stabilita' per stagione e soglia CLV robusta.
La soglia 0.605 e' il miglior equilibrio trovato finora, ma resta sotto il floor di 100 bet.
```

Stato test:

```text
81 passed con: .venv/bin/python -m pytest -q -s
```

Report dedicato:

```text
reports/ou_opening_meta_walkforward_report.md
```


---

## 4B. Step 10 chiuso - nested walk-forward meta O/U opening

Implementato e verificato:

```text
- Aggiunto runner nested: backtesting.run_selection_meta_nested_walkforward.
- La soglia del meta-model viene scelta solo su inner train folds.
- La soglia scelta viene congelata sul fold holdout successivo.
- Il runner produce direttamente verdict capital-readiness con ROI CI, CLV CI, volume e drawdown.
- Aggiunti test per la logica di ranking delle soglie.
```

Risultati nested O/U opening, run 440-464:

```text
Grid qualita' 0.55-0.62:
meta 58 bet, ROI +11.50%, CLV +0.59%, ROI CI [-5.55%, +26.78%], CLV CI [-0.92%, +2.06%], FAIL per volume e CI.

Grid volume 0.55-0.60:
meta 106 bet, ROI +5.29%, CLV +0.27%, ROI CI [-7.94%, +18.19%], CLV CI [-0.72%, +1.20%], FAIL per CI ROI/CLV e fold 2023/2024 negativo.
```

Decisione:

```text
Il meta-model arricchito e nested e' un miglioramento reale rispetto al baseline O/U opening negativo.
Non e' ancora capital-ready: il segnale non ha abbastanza volume robusto e non ha CLV CI positiva.
Il prossimo step deve rendere il selector CLV-aware, perche' il label win/loss non ottimizza direttamente la competitivita' contro il mercato.
```

Stato test:

```text
83 passed con: .venv/bin/python -m pytest -q -s
```

Report dedicato:

```text
reports/ou_opening_nested_meta_walkforward_report.md
```


---

## 4B. Step 11 chiuso - dual meta-model win + CLV

Implementato e verificato:

```text
- Il nested selector supporta ora un dual-model: win model + CLV-positive model.
- Il score puo' combinare le probabilita' con media o minimo.
- Aggiunto supporto a selection objective volume-first.
- Aggiunti test per il combinatore dual.
```

Risultati dual O/U opening, run 440-464:

```text
Dual mean + volume-first, threshold grid 0.55-0.61: 60 bet, ROI +17.12%, CLV +0.17%, ROI CI [+1.07%, +30.38%], CLV CI [-0.97%, +1.46%], FAIL per volume e CLV CI.

Dual mean + volume-first, threshold grid 0.50-0.58: 191 bet, ROI +1.20%, CLV -0.40%, ROI CI [-10.79%, +10.64%], CLV CI [-1.26%, +0.42%], FAIL per CI.

Dual min e' stato peggiore su volume e/o redditivita'.
```

Decisione:

```text
Il dual-model e' il miglior segnale finora sul piano dell'edge storico.
Non e' ancora capital-ready: o manca volume, o il volume aggiuntivo distrugge l'edge e il CLV.
La prossima direzione sensata e' un ranker o ensemble piu' ricco, oppure piu' stagioni O/U per dare spazio al nested selector.
```

Stato test:

```text
87 passed con: .venv/bin/python -m pytest -q -s
```

Report dedicato:

```text
reports/ou_dual_nested_meta_walkforward_report.md
```

---

## 4B. Report aggiornato

Report principale:

```text
reports/phase4b_betting_engine_report.md
```

Report della prova decisiva opening/CLV/meta:

```text
reports/opening_clv_meta_walkforward_report.md
```

Sintesi:

```text
Il progetto e' piu' forte come ricerca/backtesting engine e ora ha una prima evidenza positiva su opening odds e CLV.
Non e' ancora provato come betting engine competitivo per capitale reale.
La prossima fase deve aumentare volume e robustezza, soprattutto su O/U 2.5 e BTTS, e rendere il meta-model realmente selettivo.
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

Nota importante:

La dataclass `MatchFeatures` contiene già campi per attack/defense strength:

```python
home_attack_strength
home_defense_strength
away_attack_strength
away_defense_strength
league_avg_goals_home
league_avg_goals_away
```

ma il `FeatureExtractor` classico non li valorizza ancora. Nel backtest storico la logica rolling attack/defense è invece interna a `backtesting/historical_poisson_backtester.py`.

---

### Modello Poisson

File:

- `models/poisson_model.py`

Stato:

- test verdi
- usato per predizioni generiche
- non è il modello effettivo usato dalla calibration storica 5×5

Nota importante:

La calibration 5×5 usa `HistoricalPoissonBacktester`, non `PoissonModel`.

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

Formula base attuale del backtester:

```python
lambda_home = league_home_goals * home_attack * away_defense
lambda_away = league_away_goals * away_attack * home_defense
```

---

## 7. Anomalie chiuse

### `run.total_bets` gonfiato

Problema iniziale:

```text
run.total_bets mostrava tutti i record, incluse le non-bet.
```

Soluzione:

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

Verifica DB precedente:

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

Comando baseline usato:

```bash
python -m backtesting.run_calibration --seasons 2324,2223,2122,2021,1920
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

Import dopo rigenerazione quote/fair odds:

```text
25/25 import riusciti
0 nuovi match
26.850 quote rigenerate
```

I match erano già presenti; sono state rigenerate le quote con `fair_prob`.

---

## 9. Baseline stabile da battere

Benchmark baseline 5 leghe × 5 stagioni, modello rolling Poisson con fair odds:

```text
Prediction totali : 18.573
Bet reali         : 170
Non-bet           : 18.403
Brier Score       : 0.2020
ECE               : 0.0090
ROI aggregato     : circa -8.45%
Stake unitario    : 10
Stake totale      : circa 1.700
P&L aggregato     : circa -143.7
```

Breakdown selezioni baseline:

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

Conclusione baseline:

```text
Il modello è calibrato, ma non profittevole.
```

---

## 9B. Nuovo benchmark selezione stretta

Run recente con soglie più severe:

```bash
python -m backtesting.run_calibration \
  --seasons 2324,2223,2122,2021,1920 \
  --min-edge-pct 5.0 \
  --max-edge-pct 6.0 \
  --max-bookmaker-odds 1.8 \
  --away-min-edge-pct 99.0
```

Risultato:

```text
Prediction : 18.573
Bet reali  : 19
Brier      : 0.2020
ECE        : 0.0090
P&L        : +60.3
ROI        : +31.74%
```

Breakdown betting:

```text
HOME only
odds 1.6-1.8  → ROI +34.07%
edge 5.0-6.0   → ROI +31.74%
```

Conclusione:

```text
La finestra 5-6% con quote <= 1.8 batte nettamente la baseline.
AWAY resta disabilitato di default.
```

---

## 9C. Validazione holdout separata

Nuovo entrypoint:

```bash
python -m backtesting.run_holdout_validation --leagues E0 --holdout-seasons 2324
```

Scopo:

```text
Valutare il modello su stagioni tenute fuori dal tuning.
```

Risultato smoke test:

```text
Premier League 2023/2024
Prediction : 825
Bet reali  : 2
Brier      : 0.1945
ECE        : 0.0351
P&L        : -4.30
ROI        : -21.5%
```

Interpretazione:

```text
Il nuovo runner funziona e separa l'analisi out-of-sample,
ma il singolo holdout mostra ancora che il segnale resta fragile
fuori dal corridoio selettivo stretto.
```

---

## 9D. Storico esteso a 10 stagioni

Catalogo storico ampliato da 5 a 10 stagioni:

```text
2023/24, 2022/23, 2021/22, 2020/21, 2019/20,
2018/19, 2017/18, 2016/17, 2015/16, 2014/15
```

Import extra completato:

```text
25/25 import riusciti
9.130 match aggiunti
27.387 quote aggiunte
```

Nuovo comando import dedicato:

```bash
python -m historical.run_batch_import --seasons 1819,1718,1617,1516,1415
```

---

## 9E. Walk-forward tuning per lega

Nuova procedura:

```bash
python -m backtesting.run_walkforward_tuning \
  --seasons 1415,1516,1617,1718,1819,1920,2021,2122,2223,2324 \
  --policy-file config/league_backtest_policy.json
```

Cosa fa:

```text
1. Usa le prediction gia' salvate nel DB.
2. Tuning per lega su fold temporali walk-forward.
3. Salva una policy per lega in config/league_backtest_policy.json.
4. Disabilita le leghe che non superano il cancello di stabilita'.
5. Valida sull'ultima stagione come holdout finale.
```

Policy finale:

```text
Premier League  active  edge 5.0-6.0  odds <= 1.8
La Liga         active  edge 5.0-6.0  odds <= 1.8
Bundesliga      active  edge 5.0-6.5  odds <= 1.8
Serie A         active  edge 5.0-6.0  odds <= 2.0
Ligue 1         no-bet  segnale non abbastanza stabile
AWAY            disabilitato
```

Holdout finale 2023/24 con policy per lega:

```text
Run IDs      : 205-209
Bet reali    : 6
Stake        : 60.0
P&L          : +12.3
ROI          : +20.5%
Brier        : 0.2011
ECE          : 0.0088
```

Diagnosi:

```text
Il progetto e' piu' competitivo:
- ROI out-of-sample positivo su holdout 2023/24.
- Leghe deboli vengono escluse invece di forzare volume.
- Il tuning non ricalcola Poisson per ogni candidato: usa prediction-cache.

Resta da migliorare:
- Volume ancora basso.
- HOME resta la sola selezione attiva.
- Serve un secondo modello o feature aggiuntive per aumentare volume senza rumore.
```

---

## 9F. Feature selection HOME/DRAW e form goal-difference

Intervento implementato:

```text
- form_goal_diff_delta pre-match calcolato solo da partite precedenti
- lambda_gap per riconoscere partite potenzialmente equilibrate
- policy con allow_home_bets / allow_draw_bets / allow_away_bets
- soglie DRAW dedicate:
  - draw_min_edge_pct
  - draw_max_edge_pct
  - draw_min_model_probability
  - draw_max_bookmaker_odds
  - draw_max_lambda_gap
  - draw_max_abs_form_goal_diff_delta
- soglia HOME opzionale su home_min_form_goal_diff_delta
```

Nota ELO storico:

```text
La tabella team_rating_snapshots e' vuota.
Non e' stato usato ELO statico per evitare leakage temporale.
L'integrazione ELO storica resta da fare solo dopo aver popolato rating snapshot per data.
```

Risultato tuning aggiornato:

```text
Il grid ha provato candidati DRAW e filtri form-delta.
Il walk-forward non ha promosso DRAW: nessuna policy DRAW ha battuto stabilmente HOME.
La policy finale resta HOME-only con AWAY disabilitato.
```

Nuovi run generati con backtester aggiornato:

```text
Run IDs      : 210-259
Prediction   : 38.373
Bet reali    : 32
Brier        : 0.2006
ECE          : 0.0104
```

Holdout finale 2023/24 dopo le nuove feature:

```text
Run IDs      : 260-264
Bet reali    : 6
Stake        : 60.0
P&L          : +12.3
ROI          : +20.5%
Brier        : 0.2011
ECE          : 0.0088
```

Decisione:

```text
Le feature sono utili come guardrail e sono ora disponibili nel tuning,
ma non aumentano ancora il volume out-of-sample senza perdere stabilita'.
Non forzare DRAW finche' non supera il walk-forward.
```

---

## 10. Esperimento 1 — Recent form weighting

### Obiettivo

Rendere le medie gol rolling più sensibili alla forma recente.

### Modifica implementata

File:

- `backtesting/historical_poisson_backtester.py`
- `tests/test_historical_poisson_backtester.py`

Aggiunto parametro:

```python
recent_form_half_life_matches: float = 0.0
```

Nota:

```text
Default finale riportato a 0.0 per mantenere comportamento baseline.
Valori > 0 attivano il peso temporale.
```

Helper aggiunto:

```python
_weighted_average_goals(...)
```

Valori sperimentali:

```text
0.0  = baseline, media semplice
4.0  = forma molto recente
8.0  = compromesso testato
16.0 = memoria più lunga
```

### Test con half-life 8.0

Run IDs:

```text
64–88
```

Risultato 5×5:

```text
Prediction : 18.573
Bet reali  : 197
Brier      : 0.2026
ECE        : 0.0057
P&L        : circa -176.40
Stake      : 1.970
ROI        : circa -8.95%
```

Verdetto:

```text
❌ Non promosso come default.
```

Motivo:

```text
Brier peggiora: 0.2020 → 0.2026
ROI peggiora: circa -8.45% → circa -8.95%
ECE migliora: 0.0090 → 0.0057
```

Decisione:

```text
Tenere la feature come parametro sperimentale.
Default: recent_form_half_life_matches = 0.0
```

---

## 11. Esperimento 2 — Lambda multipliers

### Obiettivo

Correggere in modo piccolo e controllato la sovrastima HOME.

Ipotesi:

```text
HOME ha Brier peggiore e prob media leggermente sopra win reale.
Ridurre leggermente lambda_home potrebbe migliorare calibrazione/ROI.
```

### Modifica implementata

File:

- `backtesting/historical_poisson_backtester.py`
- `backtesting/run_calibration.py`

Aggiunti parametri in `HistoricalPoissonBacktestConfig`:

```python
home_lambda_multiplier: float = 1.0
away_lambda_multiplier: float = 1.0
```

Aggiunti flag CLI:

```bash
--home-lambda-multiplier
--away-lambda-multiplier
--recent-form-half-life-matches
```

Formula aggiornata:

```python
lambda_home = (
    league_home_goals
    * home_attack
    * away_defense
    * config.home_lambda_multiplier
)

lambda_away = (
    league_away_goals
    * away_attack
    * home_defense
    * config.away_lambda_multiplier
)
```

### Test con home_lambda_multiplier=0.99

Comando:

```bash
python -m backtesting.run_calibration   --seasons 2324,2223,2122,2021,1920   --home-lambda-multiplier 0.99   --away-lambda-multiplier 1.0
```

Run IDs:

```text
89–113
```

Calibration report:

```text
Prediction : 18.573
Bet reali  : 163
Non-bet    : 18.410
Brier      : 0.2020
ECE        : 0.0089
```

Breakdown selezioni:

```text
AWAY
n=6191
prob=0.320
win=0.317
brier=0.1962

DRAW
n=6191
prob=0.244
win=0.249
brier=0.1864

HOME
n=6191
prob=0.436
win=0.434
brier=0.2233
```

ROI aggregato run 89–113:

```text
runs       : 25
total_bets : 163
stake      : 1.630
P&L        : -163.80
ROI        : -10.05%
```

Breakdown ROI bet reali:

```text
HOME | 136 bet | stake 1360.0 | P&L -88.4 | ROI -6.50%
AWAY |  27 bet | stake  270.0 | P&L -75.4 | ROI -27.93%
```

Verdetto:

```text
❌ Non promosso come default.
```

Motivo:

```text
ECE migliora lievemente: 0.0090 → 0.0089
Brier resta invariato: 0.2020
Bet scendono: 170 → 163
ROI peggiora: circa -8.45% → -10.05%
```

Decisione:

```text
Tenere i lambda multipliers come strumenti diagnostici.
Default: home_lambda_multiplier = 1.0
Default: away_lambda_multiplier = 1.0
Non impostare 0.99 come default.
```

---

## 12. Stato test

Ultimo test completo:

```bash
wsl -d Ubuntu --cd /home/rigoni_g/Personal/Betting_Intelligence -- .venv/bin/python -m pytest -q
```

Risultato:

```text
55 passed
```

Nota test aggiornata:

`tests/test_historical_poisson_backtester.py` ora è coerente con la nuova architettura:

```text
BacktestBet contiene sia prediction non-bet sia bet reali.
run.total_bets deve contare solo is_bet=True.
```

---

## 13. Stato codice attuale consigliato

Default consigliati per il modello probabilistico:

```python
recent_form_half_life_matches: float = 0.0
home_lambda_multiplier: float = 1.0
away_lambda_multiplier: float = 1.0
```

Default consigliato per la selezione betting:

```text
Usare policy per lega da config/league_backtest_policy.json.
Non tornare alla sola soglia globale se si sta valutando competitivita'.
```

Feature sperimentali disponibili da CLI:

```bash
python -m backtesting.run_calibration \
  --seasons 2324,2223,2122,2021,1920 \
  --policy-file config/league_backtest_policy.json \
  --recent-form-half-life-matches 0.0 \
  --home-lambda-multiplier 1.0 \
  --away-lambda-multiplier 1.0
```

---

## 14. Decisione architetturale attuale

Non passare ancora a:

- dashboard
- chatbot
- recommendation engine avanzato

Motivo:

```text
La dashboard deve mostrare benchmark in-sample e out-of-sample separati.
```

Prima bisogna migliorare il modello o la selezione delle bet.

---

## 15. Diagnosi attuale

Gli esperimenti su lambda e forma recente non hanno migliorato il ROI.

Punti emersi:

```text
1. Il modello è già ragionevolmente calibrato.
2. Il collo di bottiglia non è solo il lambda.
3. HOME resta la categoria con Brier peggiore.
4. Le bet AWAY sono poche ma molto dannose nel test home_multiplier=0.99.
5. Il filtro value/selection potrebbe essere il vero collo di bottiglia.
```

Interpretazione:

```text
La probabilità media è buona, ma il sistema seleziona ancora edge non realmente profittevoli.
```

Quindi il prossimo intervento dovrebbe concentrarsi più sulla selezione bet che sulla sola stima lambda.

---

## 16. Prossimo step operativo consigliato

Priorità consigliata:

```text
FASE 4A.2 — Bet Selection Diagnostics
```

Aggiornamento operativo:

```text
AWAY è stato reso più severo nella selezione:
- away_min_edge_pct = 6.0
- away_min_model_probability = 0.58
- away_max_bookmaker_odds = 1.8

HOME e DRAW restano sui filtri globali.
```

Obiettivo:

Capire quali regole generano le bet perdenti e filtrarle.

Analisi consigliate:

```sql
SELECT
    selection,
    COUNT(*) AS bets,
    ROUND(AVG(model_probability), 4) AS avg_model_prob,
    ROUND(AVG(bookmaker_probability), 4) AS avg_book_prob,
    ROUND(AVG(edge_pct), 2) AS avg_edge,
    ROUND(AVG(bookmaker_odds), 2) AS avg_odds,
    ROUND(SUM(stake), 2) AS staked,
    ROUND(SUM(profit_loss), 2) AS profit_loss,
    ROUND((SUM(profit_loss) / NULLIF(SUM(stake), 0)) * 100, 2) AS roi_pct
FROM backtest_bets
WHERE backtest_run_id BETWEEN 34 AND 58
  AND is_bet = 1
GROUP BY selection
ORDER BY roi_pct DESC;
```

Poi breakdown per fascia edge:

```sql
SELECT
    CASE
        WHEN edge_pct < 4 THEN '03-04'
        WHEN edge_pct < 5 THEN '04-05'
        WHEN edge_pct < 6 THEN '05-06'
        WHEN edge_pct < 8 THEN '06-08'
        WHEN edge_pct < 10 THEN '08-10'
        ELSE '10+'
    END AS edge_bin,
    COUNT(*) AS bets,
    ROUND(SUM(stake), 2) AS staked,
    ROUND(SUM(profit_loss), 2) AS profit_loss,
    ROUND((SUM(profit_loss) / NULLIF(SUM(stake), 0)) * 100, 2) AS roi_pct
FROM backtest_bets
WHERE backtest_run_id BETWEEN 34 AND 58
  AND is_bet = 1
GROUP BY edge_bin
ORDER BY edge_bin;
```

Poi breakdown per quota bookmaker:

```sql
SELECT
    CASE
        WHEN bookmaker_odds < 1.40 THEN '<1.40'
        WHEN bookmaker_odds < 1.60 THEN '1.40-1.60'
        WHEN bookmaker_odds < 1.80 THEN '1.60-1.80'
        WHEN bookmaker_odds < 2.00 THEN '1.80-2.00'
        WHEN bookmaker_odds < 2.50 THEN '2.00-2.50'
        ELSE '2.50+'
    END AS odds_bin,
    COUNT(*) AS bets,
    ROUND(SUM(stake), 2) AS staked,
    ROUND(SUM(profit_loss), 2) AS profit_loss,
    ROUND((SUM(profit_loss) / NULLIF(SUM(stake), 0)) * 100, 2) AS roi_pct
FROM backtest_bets
WHERE backtest_run_id BETWEEN 34 AND 58
  AND is_bet = 1
GROUP BY odds_bin
ORDER BY odds_bin;
```

Scopo:

```text
Prima diagnosticare, poi modificare soglie:
- min_edge_pct
- max_edge_pct
- min_model_probability
- max_bookmaker_odds
- eventuale blocco selezione AWAY se dannosa
```

---

## 17. Comandi utili

### Test

```bash
pytest
```

```bash
python -m compileall database models historical backtesting recommendation services scrapers
```

### Calibration baseline completa

```bash
python -m backtesting.run_calibration --seasons 2324,2223,2122,2021,1920
```

### Calibration con parametri sperimentali

```bash
python -m backtesting.run_calibration   --seasons 2324,2223,2122,2021,1920   --recent-form-half-life-matches 0.0   --home-lambda-multiplier 1.0   --away-lambda-multiplier 1.0
```

### Validazione holdout

```bash
python -m backtesting.run_holdout_validation --leagues E0 --holdout-seasons 2324
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

## 18. Regole operative per nuove chat

Quando riprendi il progetto in una nuova chat:

1. Leggi questo file per capire stato e prossima fase.
2. Non ripartire da dashboard/chatbot.
3. Non modificare file esistenti senza inspect-first.
4. Prima di generare codice, chiedere o eseguire:
   - `grep -n "def " file.py`
   - `grep -n -A 30 "class Nome" file.py`
   - `sed -n 'X,Yp' file.py`
5. Restare nella FASE 4A finché il benchmark 5x5 non migliora.
6. Usare il benchmark baseline come riferimento:

```text
Brier Score: 0.2020
ECE: 0.0090
ROI: circa -8.45%
Bet: 170
Prediction: 18.573
```

7. Non promuovere esperimenti solo perché migliorano ECE: devono migliorare anche Brier o ROI.
8. Recent-form weighting half-life 8.0 e home multiplier 0.99 sono già stati testati e non promossi.

---

## 19. Commit suggerita

Se le modifiche sperimentali sono nel working tree e i test sono verdi:

```bash
git add backtesting/historical_poisson_backtester.py backtesting/run_calibration.py tests/test_historical_poisson_backtester.py progress.md

git commit -m "feat: add configurable backtest tuning parameters"
```

Se vuoi separare docs da codice:

```bash
git add backtesting/historical_poisson_backtester.py backtesting/run_calibration.py tests/test_historical_poisson_backtester.py

git commit -m "feat: add configurable backtest tuning parameters"

git add progress.md

git commit -m "docs: update model improvement experiment results"
```

---

## 20. Sintesi per il prossimo assistente

Il progetto è una betting intelligence pipeline locale in Python.

La pipeline dati e backtesting è valida:

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

Esperimenti già fatti:

```text
recent_form_half_life_matches=8.0
→ ECE migliora, ma Brier e ROI peggiorano.

home_lambda_multiplier=0.99
→ ECE migliora lievemente, Brier invariato, ROI peggiora a -10.05%.

away-specific gating
→ introdotto per tagliare le giocate AWAY più fragili.
```

Decisione:

```text
Non promuovere questi esperimenti come default.
Tenere i parametri come strumenti diagnostici.
Default consigliati: 0.0 / 1.0 / 1.0.
```

Priorità immediata:

```text
FASE 4A.2 — Bet Selection Diagnostics.
Analizzare le bet reali della baseline run 34–58 per selection, edge bin, odds bin.
Poi modificare le soglie di selezione, non il lambda.
```
