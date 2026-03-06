# Sources Backlog — Blog Monitor Public
**Aggiornato:** 2026-03-05

Fonti da validare e aggiungere a `config/config.json`.
Procedura: review URL → verifica accessibilità → scegli parser → aggiungi → test → commit.

---

## Tier 2 — Asset Manager & Banche d'Investimento

### Morgan Stanley — Investment Management
- **URL:** https://www.morganstanley.com/im/en-us/institutional-investor/insights-and-education.html
- **Parser suggerito:** Google News RSS (`site:morganstanley.com/im`)
- **Contenuto atteso:** market outlooks, fund commentaries, secular themes
- **Note:** Verifica che Google News indicizzi `morganstanley.com/im` (sottodominio)

### PIMCO
- **URL:** https://www.pimco.com/en-us/resources/blog
- **Parser suggerito:** Google News RSS (`site:pimco.com/en-us/resources/blog`)
- **Contenuto atteso:** fixed income research, macro outlook, Investment Committee views
- **Note:** PIMCO molto attiva su temi obbligazionari, alta rilevanza per advisor. Verificare anche feed nativo `/rss/insights.xml`

### Vanguard
- **URL:** https://advisors.vanguard.com/insights/article/list
- **Parser suggerito:** Google News RSS (`site:advisors.vanguard.com/insights`)
- **Contenuto atteso:** capital markets outlook, asset allocation, factor research
- **Note:** Il sottodominio `advisors.vanguard.com` potrebbe non essere indicizzato da Google News — testare prima

### Amundi Research Center
- **URL:** https://research-center.amundi.com
- **Parser suggerito:** HTML parser (sito statico) o RSS nativo se disponibile
- **Contenuto atteso:** macro research, cross-asset views, ESG, working papers
- **Note:** Verificare se esiste feed RSS nativo. Alta qualità ricerca, focus europeo (ottimo per advisor italiani)

### Schroders — Insights
- **URL:** https://www.schroders.com/en/global/individual/insights/
- **Parser suggerito:** Google News RSS (`site:schroders.com/en/global/individual/insights`)
- **Contenuto atteso:** global market commentary, sustainability, multi-asset
- **Note:** Verificare indicizzazione Google News

### AQR Capital Management
- **URL:** https://www.aqr.com/insights/research
- **Parser suggerito:** HTML parser o Google News RSS
- **Contenuto atteso:** factor investing, quantitative research, alternative risk premia
- **Note:** AQR pubblica ricerca accademica di alto livello. Pagina potrebbe essere JS-rendered — ispezionare con DevTools se necessario

---

## Tier 3 — Fondi Sovrani & Istituzionali

### NBIM (Norges Bank Investment Management)
- **URL:** https://www.nbim.no/en/publications/
- **Parser suggerito:** Google News RSS (`site:nbim.no/en/publications`)
- **Contenuto atteso:** annual reports, investment strategy, responsible investment
- **Note:** Minor frequenza di pubblicazione, ma autorevolezza molto alta. Utile per HNW/UHNW clients

### GIC (Singapore)
- **URL:** https://www.gic.com.sg/perspectives/
- **Parser suggerito:** HTML parser
- **Contenuto atteso:** long-term investment themes, macro
- **Note:** Pubblica poco (2-3 articoli/mese), ma qualità elevata

---

## Tier 1 — Istituzioni Internazionali (già nel PRD, da aggiungere al config)

Queste erano nel PRD originale ma non ancora in config:

### IMF (World Economic Outlook / Blog)
- **URL:** https://www.imf.org/en/News/Articles
- **Parser suggerito:** Google News RSS (`site:imf.org/en/News/Articles`)
- **Note:** Molto prolisso — valutare se settare `max_posts_per_blog: 3` specifico per questa fonte

### World Bank — Blogs
- **URL:** https://blogs.worldbank.org
- **Parser suggerito:** RSS nativo (`https://blogs.worldbank.org/rss.xml`) — verificare se esiste
- **Note:** Focus sviluppo economico, rilevante per mercati emergenti

### BIS (Bank for International Settlements)
- **URL:** https://www.bis.org/speeches.htm
- **Parser suggerito:** Google News RSS o HTML parser
- **Contenuto atteso:** working papers, speeches, quarterly reviews

### ECB
- **URL:** https://www.ecb.europa.eu/pub/economic-research/resbull/html/index.en.html
- **Parser suggerito:** RSS nativo (ECB ha feed RSS ufficiali) — cerca su `ecb.europa.eu/rss`
- **Note:** Essenziale per advisor europei. Cercate `eurosystem/rss`

### Federal Reserve
- **URL:** https://www.federalreserve.gov/feeds/research.xml
- **Parser suggerito:** RSS nativo (feed ufficiale disponibile)
- **Note:** Ottimo segnale su politica monetaria USA

### OECD
- **URL:** https://www.oecd.org/en/topics/finance.html
- **Parser suggerito:** Google News RSS
- **Note:** Bassa frequenza, alta autorevolezza su outlook economico globale

---

## Pattern config per riferimento

```json
// Google News RSS (siti indicizzati da Google News)
{
  "name": "...",
  "url": "URL della pagina principale",
  "rss_url": "https://news.google.com/rss/search?q=site:dominio.com/percorso&hl=en&gl=US&ceid=US:en",
  "use_rss_content_only": false,
  "enabled": true
}

// JSON endpoint (siti JS-rendered con API AEM o simile)
{
  "name": "...",
  "url": "URL della pagina principale",
  "json_url": "URL endpoint JSON (trovato con DevTools > Network > Fetch/XHR)",
  "json_base_url": "https://dominio.com",
  "json_pages_key": "pages",
  "use_rss_content_only": false,
  "enabled": true
}

// RSS nativo
{
  "name": "...",
  "url": "URL della pagina principale",
  "rss_url": "URL del feed RSS nativo",
  "use_rss_content_only": false,
  "enabled": true
}
```
