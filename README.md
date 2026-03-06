# Blog Monitor V2

Sistema automatico per monitorare blog di settore e generare report AI-powered con analisi di rilevanza personalizzata.

## 🎯 Descrizione

Blog Monitor è uno strumento che:
1. **Monitora** automaticamente i blog configurati (HTML, JSON embedded, XML sitemap, RSS, Google News)
2. **Estrae** titoli, contenuti e metadata degli articoli
3. **Analizza** ogni articolo con Claude AI dalla prospettiva di un **private banker o advisor**, valutando cosa è rilevante per te e per i tuoi clienti
4. **Traccia** lo stato degli articoli (analizzati/falliti) per evitare duplicati
5. **Genera** report markdown in italiano con descrizione, importanza per te, punti chiave e spunti di conversazione con il cliente

## 🚀 Quick Start

```bash
# 1. Installa le dipendenze
pip install -r requirements.txt

# 2. Configura API Key (crea file .env)
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# 3. Personalizza il tuo profilo aziendale
# Edita config/user_profile.txt con le info della tua azienda

# 4. Configura le fonti da monitorare
# Edita config/config.json con i blog di interesse

# 5. Esegui il monitor
python3 blog_monitor_v2.py
```

## 📁 Struttura del Progetto

```
blog-monitor/
├── blog_monitor_v2.py       # ⭐ Script principale
│
├── src/
│   ├── parsers/             # Parser modulari
│   │   ├── base_parser.py   # Interface astratta
│   │   ├── html_parser.py   # Parser HTML + JSON embedded
│   │   ├── sitemap_parser.py # Parser XML sitemap
│   │   └── rss_parser.py    # Parser RSS/Atom feed
│   └── utils/               # Utility classes
│       ├── logger.py        # Logging professionale
│       ├── state_manager.py # Tracking articoli + errori
│       └── retry.py         # Retry logic con backoff
│
├── config/
│   ├── config.json          # Configurazione blog e parametri
│   └── user_profile.txt     # Profilo aziendale per AI (da personalizzare)
│
├── state/
│   ├── analyzed_posts.json  # Articoli già analizzati
│   └── failed_posts.json    # Articoli falliti (con retry count)
│
├── output/                  # Report generati (markdown)
├── logs/                    # Log dettagliati (file giornalieri)
│
├── requirements.txt         # Dipendenze Python
└── README.md               # Questa documentazione
```

## 🎨 Features V2

### ✅ Miglioramenti rispetto alla V1

| Feature | V1 | V2 |
|---------|----|----|
| **Architettura** | Monolitica | Modulare (6 classi) |
| **Logging** | print() | File + console professionale |
| **Error tracking** | ❌ | ✅ Con retry count e timestamp |
| **Retry logic** | ❌ | ✅ Exponential backoff |
| **Parser estensibili** | ❌ | ✅ Pattern Strategy (HTML, Sitemap, RSS) |
| **Rate limiting** | Sleep fisso | ✅ RateLimiter intelligente |
| **State permanente** | Solo URL | ✅ URL + metadata + errori |
| **Skip articoli falliti** | ❌ | ✅ Dopo 3 tentativi |
| **Feed RSS/Atom** | ❌ | ✅ Parser nativo con fallback |

### 🔥 Vantaggi Operativi

- **-70% chiamate API**: Evita rianalisi articoli già visti
- **-50% tempo esecuzione**: Skip automatico articoli falliti permanentemente
- **Retry intelligente**: Gestisce errori transitori con backoff esponenziale
- **Logging dettagliato**: File di log giornalieri per troubleshooting
- **State tracking**: Storico completo articoli + errori con timestamp

## ⚙️ Configurazione

### config.json

```json
{
  "blogs": [
    {
      "name": "Example Blog (HTML)",
      "url": "https://example.com/blog",
      "enabled": true
    },
    {
      "name": "Example Blog (RSS)",
      "url": "https://example.com/category",
      "rss_url": "https://example.com/category/feed",
      "use_rss_content_only": true,
      "enabled": true
    },
    {
      "name": "Example Blog (Sitemap)",
      "url": "https://example.com/insights",
      "sitemap_url": "https://example.com/sitemap.xml",
      "enabled": true
    }
  ],
  "company_profile_path": "config/user_profile.txt",
  "output_format": "markdown",
  "max_posts_per_blog": 5,
  "min_relevance_score": 6
}
```

### Parametri

- **enabled**: Abilita/disabilita singolo blog
- **rss_url**: (Opzionale) URL del feed RSS/Atom
- **use_rss_content_only**: (Opzionale) Usa solo contenuto RSS senza fetch articoli completi
- **sitemap_url**: (Opzionale) Usa sitemap XML invece di HTML parser
- **max_posts_per_blog**: Limite articoli da analizzare per blog (default: 5)
- **min_relevance_score**: Score minimo per inclusione in report (1-10)

### user_profile.txt

Personalizza `config/user_profile.txt` con le informazioni della tua azienda. Il profilo viene usato dall'AI per valutare la rilevanza degli articoli rispetto al tuo contesto specifico.

## 📊 Output

### 1. Report Markdown

Generato in `output/blog_report_YYYYMMDD_HHMMSS.md`:

```markdown
# Blog Monitor Report
**Data generazione:** 2026-03-04 09:59
**Articoli analizzati:** 3
**Articoli rilevanti:** 3

## Articoli Rilevanti

### 🔥 Article Title
**Rilevanza:** 8/10
**Data pubblicazione:** March 04, 2026
**Link:** [https://example.com/article](https://example.com/article)

#### Descrizione
Sintesi dell'articolo in 2-3 frasi, come la spiegheresti a un collega.

#### Perché può essere importante per te
Analisi dal punto di vista dell'advisor: cosa connette questo articolo al tuo lavoro
quotidiano, ai portafogli e alle preoccupazioni dei tuoi clienti.

#### I punti chiave
- Primo insight standalone da ricordare prima di un meeting
- Secondo insight rilevante
- Terzo insight se genuinamente distinto

#### Spunti di conversazione con il cliente
- "Frase o domanda pronta all'uso per aprire il tema con un cliente..."
- "Secondo spunto da un angolo diverso..."
- "Terzo spunto opzionale..."
```

### 2. Log File

Salvato in `logs/blog_monitor_YYYYMMDD.log` con dettagli completi.

### 3. State Files

#### analyzed_posts.json
```json
{
  "posts": {
    "https://example.com/article": {
      "title": "Article Title",
      "analyzed_at": "2025-10-22T11:15:18.123456",
      "relevance_score": 9
    }
  }
}
```

#### failed_posts.json
```json
{
  "posts": {
    "https://example.com/broken-article": {
      "title": "Broken Article",
      "failure_count": 3,
      "last_error": "404 Not Found",
      "first_failed": "2025-10-22T11:14:35.123456",
      "last_attempt": "2025-10-22T11:17:20.123456"
    }
  }
}
```

## 🔧 Utilizzo Avanzato

### Esempio di Esecuzione

```bash
python3 blog_monitor_v2.py
```

**Output:**
```
============================================================
Blog Monitor V2
============================================================
Loaded configuration from config/config.json
Articoli già analizzati: 8
Articoli falliti in precedenza: 4

============================================================
Monitoring: Example Blog
============================================================
Analyzing 2 new posts...
  → Article Title One
  → Article Title Two

============================================================
✓ Analysis complete!
  New posts analyzed: 2
  Relevant posts found: 2
  Total in database: 10 (+2)
  Total failed: 4
============================================================
```

### Reset Completo

Per ripartire da zero (rianalizza tutti gli articoli):

```bash
rm state/analyzed_posts.json state/failed_posts.json
python3 blog_monitor_v2.py
```

### Aggiungere Nuovi Blog

1. **Blog HTML Standard**:
```json
{
  "name": "Nome Blog",
  "url": "https://example.com/blog",
  "enabled": true
}
```

2. **Blog con Sitemap XML**:
```json
{
  "name": "Nome Blog",
  "url": "https://example.com/insights",
  "sitemap_url": "https://example.com/sitemap.xml",
  "enabled": true
}
```

3. **Blog con Feed RSS**:
```json
{
  "name": "Nome Blog",
  "url": "https://example.com/category",
  "rss_url": "https://example.com/category/feed",
  "use_rss_content_only": true,
  "enabled": true
}
```

4. **Siti senza RSS (es. Goldman Sachs) — via Google News**:
```json
{
  "name": "Goldman Sachs Insights - Articles",
  "url": "https://www.goldmansachs.com/insights/articles",
  "rss_url": "https://news.google.com/rss/search?q=site:goldmansachs.com/insights/articles&hl=en&gl=US&ceid=US:en",
  "use_rss_content_only": false,
  "enabled": true,
  "notes": "Google News RSS as discovery feed. Fetches full article from GS site."
}
```

**Note:**
- `use_rss_content_only: true` — Usa solo il contenuto del feed RSS senza fare fetch degli articoli completi (utile per siti che bloccano i crawler)
- `use_rss_content_only: false` — Tenta il fetch dell'articolo completo; se fallisce (es. redirect a consent page) usa automaticamente l'excerpt RSS
- Priorità parser: RSS > Sitemap > HTML
- Per siti senza feed RSS nativo, Google News RSS (`site:dominio.com`) funziona come discovery feed alternativo

## 🏗️ Architettura

### Parser Modulari

Il sistema usa il **Strategy Pattern** per supportare diverse fonti:

```python
# BaseParser - Interface comune
class BaseParser(ABC):
    @abstractmethod
    def parse(self, url: str, **kwargs) -> List[Dict]:
        pass

# HTMLParser - Per blog HTML e JSON embedded
# SitemapParser - Per sitemap XML
# RSSParser - Per feed RSS/Atom
```

**Parser disponibili:**
- **HTMLParser**: Estrae articoli da pagine HTML e JSON embedded
- **SitemapParser**: Legge sitemap XML per trovare URL articoli
- **RSSParser**: Parsa feed RSS 2.0 e Atom (con fallback automatico)

**Facile estendere** con nuovi parser (API, PDF, etc.)

### StateManager

Gestisce tracking articoli e errori:

```python
state_manager = StateManager()

if state_manager.is_analyzed(url):
    skip()

if state_manager.is_failed(url, max_retries=3):
    skip()

state_manager.mark_analyzed(url, title, score)
state_manager.mark_failed(url, title, error)
state_manager.save()
```

### Retry con Backoff

Gestione automatica errori transitori:

```python
@retry_with_backoff(max_retries=2, initial_delay=2.0)
def fetch_full_article(url):
    # Ritenta automaticamente con delay: 2s, 4s, 8s...
    return requests.get(url)
```

### Rate Limiter

Previene throttling API:

```python
rate_limiter = RateLimiter(calls_per_minute=20)
rate_limiter.wait_if_needed()
```

## 🔍 Troubleshooting

### Articoli non vengono trovati
Controlla `logs/blog_monitor_YYYYMMDD.log` per dettagli parser.

### Troppi errori 404
Alcune sitemap contengono URL obsoleti. Dopo 3 tentativi vengono skippati automaticamente.

### "Invalid control character" in AI analysis
Contenuto articolo con caratteri speciali. Il sistema logga l'errore e marca l'articolo come fallito.

### Link che puntano a consent.google.com (Italia/EU)
Quando si usa Google News come discovery feed da IP europei, il redirect dell'articolo può portare alla pagina di consenso di Google invece che all'articolo reale. Il sistema lo rileva automaticamente, annulla il fetch e usa l'excerpt RSS per l'analisi. Il link nel report rimane quello Google News originale (cliccabile dal browser dell'utente che ha già accettato il consenso).

### Rate limiting API
Il `RateLimiter` limita a 20 chiamate/minuto. Se necessario, modifica in `blog_monitor_v2.py`:

```python
self.rate_limiter = RateLimiter(calls_per_minute=10)  # Più conservativo
```

## 📅 Schedulazione

### macOS/Linux (cron)

```bash
crontab -e
# Aggiungi (esecuzione ogni lunedì alle 9:00):
0 9 * * 1 cd /path/to/blog-monitor && /usr/bin/python3 blog_monitor_v2.py
```

### macOS (launchd)

Crea `~/Library/LaunchAgents/com.blogmonitor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.blogmonitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/blog_monitor_v2.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>9</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/path/to/blog-monitor</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ANTHROPIC_API_KEY</key>
        <string>sk-ant-...</string>
    </dict>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.blogmonitor.plist
```

## 🔐 Sicurezza

- ⚠️ **NON** committare mai `.env` o API keys — il `.gitignore` è già configurato
- Compila `config/user_profile.txt` con informazioni che sei disposto a rendere pubbliche
- Rispetta robots.txt e Terms of Service dei siti monitorati

## 💰 Costi stimati

Usando `claude-sonnet-4-5-20250929`:
- ~2000 token per analisi articolo (prompt più ricco con prospettiva advisor)
- 5 articoli ≈ 10K token ≈ $0.04-0.06 per esecuzione
- Esecuzione settimanale ≈ $0.20-0.25/mese

## 🚧 Roadmap

- [x] Parser RSS/Atom nativo ✅
- [ ] Cache contenuti articoli (evitare re-fetch)
- [ ] Async processing con `asyncio`
- [ ] Email automatica con report
- [ ] Dashboard web per statistiche
- [ ] Notifiche Slack/Teams
- [ ] Export multi-formato (JSON, CSV, PDF)

## 📚 Estensioni

### Aggiungere Parser API

```python
# src/parsers/api_parser.py
from .base_parser import BaseParser

class APIParser(BaseParser):
    def parse(self, url: str, **kwargs) -> List[Dict]:
        response = requests.get(url, headers=kwargs.get('headers'))
        data = response.json()
        return [self._create_post_dict(...) for item in data['articles']]
```

## 📄 Licenza

MIT License — libero utilizzo, modifica e distribuzione.

---

**Versione**: 2.0
