# Guida Deploy — Fides su Render + Supabase

**Tempo stimato:** 30-45 minuti
**Prerequisiti:** account GitHub, account Render (free), account Supabase (free)

---

## Parte 1 — Supabase (database PostgreSQL)

### 1.1 Crea il progetto

1. Vai su [supabase.com](https://supabase.com) → **Start your project**
2. Crea un nuovo progetto:
   - **Nome:** `fides`
   - **Password database:** genera una password sicura e salvala in un posto sicuro
   - **Regione:** `West EU (Ireland)` — più vicina all'Italia
3. Aspetta ~2 minuti che il progetto si avvii

### 1.2 Copia la connection string

1. Nel progetto Supabase → **Settings** → **Database**
2. Sezione **Connection string** → tab **URI**
3. Copia la stringa (inizia con `postgresql://postgres:...`)
4. Sostituisci `[YOUR-PASSWORD]` con la password che hai scelto

> ⚠️ **Nota importante:** aggiungi `?pgbouncer=true&connection_limit=1` alla fine della stringa
> per evitare problemi con il connection pooling del free tier.
>
> Esempio finale:
> ```
> postgresql://postgres:TUA_PASSWORD@db.xxxx.supabase.co:5432/postgres?pgbouncer=true&connection_limit=1
> ```

---

## Parte 2 — GitHub

### 2.1 Assicurati che il repo sia pronto

Prima del push, verifica che `.gitignore` escluda correttamente:
```bash
# Dalla cartella blog-monitor-public/
git status
```
Non devono comparire: `.env`, `fides/instance/`, `*.db`, `blog_report_*.md`

### 2.2 Push su GitHub (se non l'hai già fatto)

```bash
cd blog-monitor-public/
git add .
git commit -m "fase 6: privacy policy, deploy config"
git push origin main
```

---

## Parte 3 — Render (web service + cron)

### 3.1 Crea il Web Service

1. Vai su [render.com](https://render.com) → **New** → **Web Service**
2. **Connect a repository** → seleziona `blog-monitor-public`
3. Configura:
   - **Name:** `fides`
   - **Root Directory:** `fides`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt && FLASK_APP=run flask db upgrade`
   - **Start Command:** `gunicorn run:app`
   - **Instance Type:** Free

### 3.2 Variabili d'ambiente

Nella sezione **Environment Variables** aggiungi:

| Key | Value | Note |
|-----|-------|------|
| `DATABASE_URL` | `postgresql://postgres:...` | La stringa Supabase con `?pgbouncer=true&connection_limit=1` |
| `SECRET_KEY` | genera con `python -c "import secrets; print(secrets.token_hex(32))"` | Chiave random, 32 bytes |
| `FLASK_APP` | `run` | Necessario per flask db upgrade |
| `FLASK_ENV` | `production` | |
| `ADMIN_USERNAME` | es. `admin` | Scegli tu |
| `ADMIN_PASSWORD` | stringa sicura | Scegli tu — min 12 caratteri |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | La tua chiave Anthropic |
| `APP_URL` | `https://fides.onrender.com` | Il tuo URL Render (lo trovi dopo il primo deploy) |
| `RESEND_API_KEY` | `re_...` | Opzionale per ora — lascia vuoto se non hai dominio |
| `EMAIL_FROM` | `onboarding@resend.dev` | Temporaneo finché non hai dominio |

> 💡 **SECRET_KEY:** puoi generarla da terminale localmente:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 3.3 Primo deploy

1. Clicca **Create Web Service**
2. Render clona il repo, installa le dipendenze e lancia `flask db upgrade`
3. Tieni d'occhio il **Deploy Log** — deve finire con `==> Your service is live 🎉`
4. Il build può richiedere 3-5 minuti la prima volta

> ⚠️ **Se `flask db upgrade` fallisce:** controlla che `DATABASE_URL` sia corretta. L'errore più comune è la password con caratteri speciali non encodati — usa `%40` per `@`, `%23` per `#` ecc.

### 3.4 Verifica il deploy

1. Apri l'URL `https://fides.onrender.com` (o il tuo subdomain)
2. Devi vedere il redirect a `/login`
3. Registra un account di test
4. Vai su `/admin/login` e prova le credenziali admin

---

## Parte 4 — Cron Job (digest settimanale)

### 4.1 Crea il Cron Job su Render

1. Render dashboard → **New** → **Cron Job**
2. Configura:
   - **Name:** `fides-weekly-digest`
   - **Repository:** stesso repo di Fides
   - **Root Directory:** `fides`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Command:** `python scripts/blog_monitor_v2.py`
   - **Schedule:** `0 7 * * 1` (ogni lunedì alle 07:00 UTC = 08:00 CET / 09:00 CEST)
3. Aggiungi le stesse variabili d'ambiente (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `APP_URL`, ecc.)

### 4.2 Test manuale del cron

Prima di aspettare lunedì, testa che lo script funzioni dall'area admin:
1. Vai su `/admin/run`
2. Clicca **Genera nuovo digest**
3. Osserva il log in tempo reale
4. Verifica che il digest appaia su `/app`

---

## Parte 5 — Seed dei digest storici (opzionale)

Se vuoi caricare i digest già creati localmente sul database di produzione:

```bash
# Da terminale locale, con DATABASE_URL impostata sull'URL Supabase
export DATABASE_URL="postgresql://postgres:TUA_PASSWORD@db.xxx.supabase.co:5432/postgres?pgbouncer=true&connection_limit=1"

cd blog-monitor-public/fides/
python scripts/seed_digest.py
```

---

## Parte 6 — Dopo il deploy

### Aggiorna APP_URL

Una volta che conosci il tuo URL Render definitivo:
1. Render dashboard → **fides** → **Environment**
2. Aggiorna `APP_URL` con l'URL reale (es. `https://fides-xxxx.onrender.com`)
3. Render fa redeploy automatico

### Dominio custom (opzionale, ~10€/anno)

1. Acquista un dominio su Cloudflare (es. `fides.email` o `tryf ides.app`)
2. Render dashboard → **Settings** → **Custom Domains** → aggiungi il dominio
3. Copia i record DNS che Render ti dà e configurali su Cloudflare
4. Aspetta propagazione DNS (5-60 minuti)
5. Configura il dominio anche su Resend per abilitare le email dal tuo indirizzo

---

## Checklist finale pre-lancio

- [ ] `https://[tuo-url]/login` apre la pagina di login
- [ ] La registrazione funziona (utente creato nel DB)
- [ ] Login e logout funzionano
- [ ] `/app` mostra la lista digest dopo login
- [ ] `/app/digest/1` mostra gli articoli
- [ ] `/privacy` mostra la privacy policy
- [ ] `/admin/login` funziona con le credenziali che hai scelto
- [ ] Il trigger manuale da `/admin/run` esegue lo script senza errori
- [ ] Il cron job è configurato su Render
- [ ] `APP_URL` è impostata con l'URL corretto

---

## Troubleshooting

**`ModuleNotFoundError`** → verifica che `requirements.txt` sia nella cartella `fides/` e che il Root Directory su Render sia `fides`

**`sqlalchemy.exc.OperationalError`** → controlla la `DATABASE_URL` — character encoding della password, porta corretta (5432), stringa `?pgbouncer=true&connection_limit=1` presente

**`flask db upgrade` fallisce** → esegui il comando manualmente con la DATABASE_URL Supabase dal tuo terminale locale per leggere l'errore completo

**L'app si sveglia lentamente** → normale sul free tier di Render — il server si "addormenta" dopo 15 minuti di inattività. La prima richiesta dopo la pausa può richiedere 30-60 secondi.

**Il cron job non gira** → verifica il log del cron job su Render. Errori comuni: `BLOG_MONITOR_SCRIPT` non impostato, `ANTHROPIC_API_KEY` mancante nel cron service.
