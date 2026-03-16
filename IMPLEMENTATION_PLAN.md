# Implementation Plan — Fides Web App

**Versione:** 1.0
**Data:** 2026-03-16
**Riferimento:** PRD_FASE2.md v1.5
**Status:** Pronto per sviluppo

---

## Struttura cartelle

```
fides/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── models.py            # SQLAlchemy models
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py        # /register, /login, /logout
│   ├── user/
│   │   ├── __init__.py
│   │   └── routes.py        # /app, /app/digest/<id>, /app/sources
│   ├── admin/
│   │   ├── __init__.py
│   │   └── routes.py        # /admin, /admin/run, /admin/sources, /admin/users, /admin/logs
│   ├── templates/
│   │   ├── base.html        # Layout base con nav Bootstrap 5
│   │   ├── auth/
│   │   │   ├── register.html
│   │   │   └── login.html
│   │   ├── user/
│   │   │   ├── digest_list.html
│   │   │   ├── digest_single.html
│   │   │   └── sources.html
│   │   └── admin/
│   │       ├── dashboard.html
│   │       ├── run.html
│   │       ├── sources.html
│   │       ├── users.html
│   │       └── logs.html
│   └── static/
│       └── css/
│           └── custom.css   # Override Bootstrap minimi
├── scripts/
│   └── blog_monitor_v2.py   # Script esistente (copiato/symlink)
├── config/
│   └── config.json          # Configurazione fonti (esistente)
├── migrations/              # Flask-Migrate (Alembic)
├── .env                     # Variabili d'ambiente (non committare)
├── .env.example             # Template variabili d'ambiente
├── requirements.txt
├── render.yaml              # Configurazione Render (web service + cron)
├── Procfile                 # Per Render: web: gunicorn run:app
└── run.py                   # Entry point app
```

---

## Database Schema (PostgreSQL / Supabase)

### Tabella `users`
| Colonna | Tipo | Note |
|---------|------|------|
| id | UUID (PK) | `default gen_random_uuid()` |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| created_at | TIMESTAMP | DEFAULT NOW() |
| last_login | TIMESTAMP | nullable |
| is_active | BOOLEAN | DEFAULT TRUE |

### Tabella `digests`
| Colonna | Tipo | Note |
|---------|------|------|
| id | SERIAL (PK) | |
| title | VARCHAR(255) | es. "Digest #12 — 5 marzo 2026" |
| published_at | TIMESTAMP | NOT NULL |
| article_count | INTEGER | |
| summary | TEXT | anteprima per la lista (3 temi principali) |
| sources_tags | TEXT[] | array di nomi fonte (per i badge nella lista) |
| raw_markdown | TEXT | output originale dello script |

### Tabella `articles`
| Colonna | Tipo | Note |
|---------|------|------|
| id | SERIAL (PK) | |
| digest_id | INTEGER (FK) | → digests.id, ON DELETE CASCADE |
| title | VARCHAR(500) | |
| source | VARCHAR(100) | es. "Goldman Sachs" |
| relevance_score | INTEGER | 1-10 |
| why_relevant | TEXT | sezione "Perché è rilevante" |
| key_points | TEXT[] | array di bullet point |
| conversation_starters | TEXT[] | array di 3 spunti |
| original_url | VARCHAR(500) | link all'articolo originale |
| published_date | DATE | data dell'articolo originale |

### Tabella `run_logs`
| Colonna | Tipo | Note |
|---------|------|------|
| id | SERIAL (PK) | |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | nullable (null se in corso) |
| status | VARCHAR(20) | 'running' / 'success' / 'partial' / 'error' |
| articles_found | INTEGER | |
| digest_id | INTEGER (FK) | → digests.id, nullable |
| error_details | JSONB | `{"Goldman Sachs": "timeout", ...}` |
| log_output | TEXT | output completo per debug |

### Tabella `source_states`
| Colonna | Tipo | Note |
|---------|------|------|
| id | SERIAL (PK) | |
| source_name | VARCHAR(100) | UNIQUE, corrisponde a config.json |
| enabled | BOOLEAN | DEFAULT TRUE |
| last_status | VARCHAR(20) | 'ok' / 'error' / 'timeout' |
| last_run_at | TIMESTAMP | nullable |

---

## Route Map completa

### Auth (Blueprint: `auth`)
| Metodo | Route | Funzione | Auth richiesta |
|--------|-------|----------|----------------|
| GET/POST | `/register` | Form registrazione + creazione utente | No |
| GET/POST | `/login` | Form login + creazione sessione | No |
| GET | `/logout` | Distrugge sessione | Sì |

### User (Blueprint: `user`)
| Metodo | Route | Funzione | Auth richiesta |
|--------|-------|----------|----------------|
| GET | `/app` | Lista digest (cronologica inversa) | Sì |
| GET | `/app/digest/<int:id>` | Digest singolo con articoli | Sì |
| GET | `/app/sources` | Le nostre fonti (da config.json) | Sì |

### Admin (Blueprint: `admin`)
| Metodo | Route | Funzione | Auth richiesta |
|--------|-------|----------|----------------|
| GET/POST | `/admin/login` | Login separato per admin | No |
| GET | `/admin/logout` | Logout admin | Admin |
| GET | `/admin` | Dashboard (stats, ultimo run) | Admin |
| GET | `/admin/run` | Pagina trigger + log real-time | Admin |
| POST | `/admin/run/start` | Avvia script in background | Admin |
| GET | `/admin/run/status` | Polling JSON stato esecuzione | Admin |
| GET | `/admin/sources` | Lista fonti con toggle | Admin |
| POST | `/admin/sources/<name>/toggle` | Abilita/disabilita fonte | Admin |
| GET | `/admin/users` | Lista utenti registrati | Admin |
| GET | `/admin/logs` | Storico run (ultimi 10) | Admin |
| GET | `/admin/logs/<int:id>` | Dettaglio singolo run | Admin |

---

## Variabili d'ambiente (`.env`)

```bash
# Database
DATABASE_URL=postgresql://...  # Connection string Supabase

# Flask
SECRET_KEY=...                  # Chiave crittografica sessioni (random 32 bytes)
FLASK_ENV=production

# Admin credentials (non nel DB, più sicuro)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=...

# Email (Resend)
RESEND_API_KEY=...
EMAIL_FROM=digest@fides.app

# Anthropic (per lo script)
ANTHROPIC_API_KEY=...
```

---

## Sequenza di build consigliata

La sequenza è ordinata per valore consegnabile: ogni fase produce qualcosa di testabile.

### Fase 1 — Scaffold + DB + Auth (2-3 giorni)
**Obiettivo:** avere un'app Flask deployata su Render con registrazione e login funzionanti.

1. Crea struttura cartelle e `requirements.txt`
2. Configura `create_app()` con Flask-SQLAlchemy + Flask-Login
3. Scrivi i modelli SQLAlchemy (`User`, `Digest`, `Article`, `RunLog`, `SourceState`)
4. Inizializza il database su Supabase + `flask db upgrade`
5. Implementa Blueprint `auth`: `/register`, `/login`, `/logout`
6. Template Bootstrap 5 per register e login (ispirato al Figma Make)
7. Deploy iniziale su Render (web service) — verifica che login funzioni in produzione

**Test:** registra un utente, fai login, verifica sessione, fai logout.

---

### Fase 2 — Area utente (2 giorni)
**Obiettivo:** le 3 pagine utente funzionanti (con dati mock).

1. Blueprint `user`: `/app` con lista digest da DB
2. Template `digest_list.html` con card Bootstrap (data, badge fonti, count articoli)
3. Route `/app/digest/<id>` con articoli completi
4. Template `digest_single.html` con score, sezioni, spunti conversazione
5. Route `/app/sources` che legge `config.json` e mostra le 11 fonti
6. Template `sources.html` con badge categoria (Asset Manager / Banca Centrale / Organismo Internazionale)
7. Inserisci 1-2 digest di test nel DB con dati reali (dal file `blog_report_20260305_171406.md`)

**Test:** naviga tutte e 3 le pagine su mobile + desktop. Verifica redirect a login se non autenticato.

---

### Fase 3 — Integrazione script (2 giorni)
**Obiettivo:** il blog_monitor_v2.py salva i risultati nel database invece di produrre markdown.

1. Aggiungi funzione `save_digest_to_db(parsed_output)` in un modulo `scripts/db_writer.py`
2. Modifica `blog_monitor_v2.py` per chiamare `save_digest_to_db` a fine esecuzione (mantieni il fallback markdown)
3. Implementa parsing del markdown esistente (per importare i digest storici)
4. Importa `blog_report_20260305_171406.md` nel database come primo digest reale
5. Crea tabella `run_logs`: log iniziale e finale dello script

**Test:** esegui lo script manualmente, verifica che il digest appaia su `/app`.

---

### Fase 4 — Area admin (2 giorni)
**Obiettivo:** dashboard admin funzionante con trigger manuale.

1. Login admin separato (credenziali da variabili d'ambiente, sessione separata)
2. Dashboard: stats (utenti, digest, stato ultimo run)
3. Pagina `/admin/run` con pulsante trigger + log in polling (ogni 2s via fetch JSON)
4. Avvio script in background con `subprocess` + file di log temporaneo
5. Pagina `/admin/logs` con storico run
6. Pagina `/admin/sources` con toggle (aggiorna `source_states` nel DB)
7. Pagina `/admin/users` con lista utenti

**Test:** triggera il digest manualmente dall'admin, verifica che appaia nel log e nella lista utenti.

---

### Fase 5 — Email (1 giorno)
**Obiettivo:** notifica email settimanale automatica.

1. Configura Resend SDK (`resend` package)
2. Funzione `send_weekly_notification(digest_id)`: recupera i top 3 articoli, compone HTML email, invia a tutti gli utenti
3. Chiama `send_weekly_notification` alla fine dell'esecuzione dello script (se successo)
4. Configura Render Cron Job: `python scripts/blog_monitor_v2.py` ogni lunedì alle 07:00

**Test:** invia email di test a te stesso, verifica template su mobile.

---

### Fase 6 — QA e lancio (1 giorno)
1. Test completo su mobile (iOS Safari + Android Chrome)
2. Verifica checklist pre-lancio del PRD
3. Aggiungi privacy policy minimale (`/privacy`, testo semplice)
4. Configura dominio custom (opzionale)
5. Primo utente reale registrato

---

## requirements.txt

```
flask>=3.0
flask-sqlalchemy>=3.1
flask-login>=0.6
flask-migrate>=4.0
werkzeug>=3.0
psycopg2-binary>=2.9
python-dotenv>=1.0
gunicorn>=21.0
resend>=0.7
anthropic>=0.20
requests>=2.31
beautifulsoup4>=4.12
feedparser>=6.0
```

---

## render.yaml

```yaml
services:
  - type: web
    name: fides
    env: python
    buildCommand: pip install -r requirements.txt && flask db upgrade
    startCommand: gunicorn run:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: fides-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true

  - type: cron
    name: fides-weekly-digest
    env: python
    schedule: "0 7 * * 1"   # Ogni lunedì alle 07:00
    buildCommand: pip install -r requirements.txt
    startCommand: python scripts/blog_monitor_v2.py
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: fides-db
          property: connectionString

databases:
  - name: fides-db
    databaseName: fides
    plan: free
```

---

## Note implementative chiave

**Sessione admin separata:** Flask-Login gestisce un solo `current_user`. Per l'admin usa una sessione Flask manuale (`session['admin_logged_in'] = True`) con un decorator `@admin_required` custom invece di `@login_required`.

**Polling log real-time:** il trigger dello script usa `subprocess.Popen` con `stdout=PIPE`. L'output viene scritto riga per riga su un file temporaneo (`/tmp/fides_run_<timestamp>.log`). La route `/admin/run/status` legge il file e restituisce JSON. Il frontend fa polling ogni 2 secondi con `fetch()`.

**Parsing del markdown:** il formato dell'output di `blog_monitor_v2.py` è strutturato. Puoi parsarlo con regex o scrivere un parser dedicato che riconosce i pattern `## Articolo`, `**Rilevanza:**`, `**Perché è rilevante:**`, `**Spunti per il cliente:**`. Alternativa più robusta: modifica lo script per produrre anche un output JSON oltre al markdown.

**`/app/sources` da config.json:** la route legge `config/config.json` a runtime, non da DB. Aggiunge il campo `category` in base al nome (GS/BlackRock/JPMorgan/PIMCO/MS → "Asset Manager", Fed/ECB/BIS → "Banca Centrale", IMF/WorldBank/OECD → "Organismo Internazionale").

**Supabase connection pooling:** usa `?pgbouncer=true&connection_limit=1` nella connection string per evitare problemi con il free tier di Supabase (max 60 connessioni simultanee).

---

## Prompt consigliato per la prossima sessione

```
Stiamo costruendo Fides, una web app Flask per consulenti finanziari.
Leggi IMPLEMENTATION_PLAN.md per la struttura completa e PRD_FASE2.md
per il contesto di prodotto.

Inizia dalla Fase 1 della sequenza di build:
- Crea la struttura cartelle fides/
- Scrivi requirements.txt
- Implementa create_app() con SQLAlchemy e Flask-Login
- Scrivi i modelli (User, Digest, Article, RunLog, SourceState)
- Implementa il Blueprint auth: /register, /login, /logout
- Template Bootstrap 5 base per register e login

Il codice va scritto nella cartella blog-monitor-public/fides/.
```
