# Gestione Formazioni e Visite Mediche — Backend

Stack: **FastAPI + SQLite** — deploy gratuito su Render.com

---

## Struttura del progetto

```
formazioni_app/
├── main.py                  # entry point FastAPI
├── database.py              # connessione SQLite + helper
├── schema.sql               # schema DB + seed dati
├── requirements.txt         # dipendenze Python
└── routers/
    ├── cantieri.py          # CRUD cantieri/sedi
    ├── dipendenti.py        # CRUD dipendenti
    ├── attestati.py         # CRUD attestati + calcolo scadenze
    ├── visite.py            # CRUD visite mediche
    ├── tipi_formazione.py   # catalogo corsi
    └── dashboard.py         # riepilogo + export Excel
```

---

## Avvio in locale (sviluppo)

```bash
# 1. Crea ambiente virtuale
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Installa dipendenze
pip install -r requirements.txt
pip install python-dateutil     # per calcolo scadenze

# 3. Avvia il server
uvicorn main:app --reload --port 8000
```

Apri il browser su:
- **http://localhost:8000/docs** → interfaccia Swagger (testa tutte le API)
- **http://localhost:8000/health** → verifica che il server risponda

---

## Deploy su Render.com (gratuito)

### Passo 1 — Carica il codice su GitHub
```bash
git init
git add .
git commit -m "primo commit"
git remote add origin https://github.com/TUONOME/formazioni-backend.git
git push -u origin main
```

### Passo 2 — Crea il servizio su Render
1. Vai su https://render.com e registrati (gratis, no carta di credito)
2. Clicca **New → Web Service**
3. Connetti il tuo repository GitHub
4. Imposta questi campi:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt && pip install python-dateutil`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Clicca **Create Web Service**

Render ti assegna un URL tipo: `https://formazioni-backend.onrender.com`

### Passo 3 — Aggiorna il CORS in main.py
Sostituisci `allow_origins=["*"]` con il tuo URL GitHub Pages:
```python
allow_origins=["https://TUONOME.github.io"]
```

---

## Endpoints disponibili

| Metodo | URL | Descrizione |
|--------|-----|-------------|
| GET | `/cantieri/` | Lista cantieri |
| POST | `/cantieri/` | Crea cantiere |
| PUT | `/cantieri/{id}` | Modifica cantiere |
| DELETE | `/cantieri/{id}` | Elimina cantiere |
| GET | `/dipendenti/` | Lista dipendenti (filtrabile) |
| POST | `/dipendenti/` | Crea dipendente |
| PUT | `/dipendenti/{id}` | Modifica dipendente |
| DELETE | `/dipendenti/{id}` | Elimina dipendente |
| GET | `/attestati/` | Lista attestati (filtrabile) |
| GET | `/attestati/scadenze?giorni=90` | Scadenze imminenti |
| POST | `/attestati/` | Crea attestato (scadenza auto) |
| PUT | `/attestati/{id}` | Modifica attestato |
| DELETE | `/attestati/{id}` | Elimina attestato |
| GET | `/visite/` | Lista visite mediche |
| POST | `/visite/` | Crea visita medica |
| PUT | `/visite/{id}` | Modifica visita |
| DELETE | `/visite/{id}` | Elimina visita |
| GET | `/tipi-formazione/` | Catalogo corsi |
| GET | `/dashboard/riepilogo` | Statistiche generali |
| GET | `/dashboard/export/excel` | Scarica Excel aggiornato |

---

## Backup del database

Il database è il file `formazioni.db`. Per fare un backup:

```bash
# Copia locale
cp formazioni.db backup_$(date +%Y%m%d).db
```

Dalla web app sarà disponibile il pulsante **Esporta Excel** che scarica
tutti i dati aggiornati in qualsiasi momento.

---

## Note importanti su Render free tier

- Il server si **addormenta dopo 15 minuti** di inattività
- Al primo accesso dopo la pausa impiega ~30 secondi a rispondere
- Il file `formazioni.db` **persiste tra i riavvii** (disco Render)
- Per sicurezza, usa il tasto **Esporta Excel** settimanalmente
