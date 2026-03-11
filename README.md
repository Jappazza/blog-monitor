# Blog Monitor V2

An automated tool that monitors financial research blogs, extracts articles, and generates AI-powered reports with personalized relevance analysis — built for wealth management professionals who want to stay on top of market research without spending hours reading.

## 🎯 What it does

1. **Monitors** configured sources (HTML, JSON/AEM endpoints, XML sitemap, RSS, Google News)
2. **Extracts** article titles, content, and metadata
3. **Analyzes** each article with Claude AI from the perspective of a **private banker or wealth advisor**, evaluating relevance to your work and clients
4. **Tracks** article state (analyzed / failed) to avoid duplicate processing
5. **Generates** markdown reports with description, why it matters, key takeaways, and client conversation starters

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# 3. Customize your profile
# Edit config/user_profile.txt with your firm/role context

# 4. Configure sources
# Edit config/config.json — 11 sources already included out of the box

# 5. Run
python3 blog_monitor_v2.py
```

## 📡 Sources included (11)

| Source | Parser | Coverage |
|--------|--------|----------|
| Goldman Sachs Insights | Google News RSS | Market views, macro research |
| BlackRock Investment Institute | Google News RSS | Weekly commentary, mega forces |
| JPMorgan Asset Management | JSON/AEM endpoint | Market Insights, Guide to Markets |
| Federal Reserve | Google News RSS | FEDS Notes, working papers |
| ECB | Google News RSS | Research Bulletin, Economic Bulletin |
| PIMCO | Google News RSS | Fixed income, Secular Outlook |
| Morgan Stanley IM | Google News RSS | Market outlooks, fund commentary |
| IMF | Google News RSS | WEO, Global Financial Stability Report |
| World Bank Blogs | Google News RSS | EM, development economics |
| BIS | Google News RSS | Working papers, Quarterly Review |
| OECD | Google News RSS | Economic Outlook, policy research |

## 📁 Project structure

```
blog-monitor/
├── blog_monitor_v2.py       # ⭐ Main script
│
├── src/
│   ├── parsers/             # Modular parsers
│   │   ├── base_parser.py   # Abstract interface
│   │   ├── html_parser.py   # HTML + embedded JSON parser
│   │   ├── sitemap_parser.py # XML sitemap parser
│   │   └── rss_parser.py    # RSS/Atom feed parser
│   └── utils/
│       ├── logger.py        # File + console logging
│       ├── state_manager.py # Article tracking + error state
│       └── retry.py         # Exponential backoff retry
│
├── config/
│   ├── config.json          # Sources and parameters
│   └── user_profile.txt     # Your advisor profile (customize this)
│
├── state/                   # Persistent tracking (git-ignored)
├── output/                  # Generated reports (git-ignored)
├── logs/                    # Daily log files (git-ignored)
│
├── requirements.txt
└── README.md
```

## ⚙️ Configuration

### config.json

The parser is chosen automatically based on which field is present:

```json
// Standard HTML blog
{
  "name": "My Blog",
  "url": "https://example.com/blog",
  "enabled": true
}

// RSS or Google News feed
{
  "name": "My Blog (RSS)",
  "url": "https://example.com/blog",
  "rss_url": "https://example.com/feed.xml",
  "use_rss_content_only": false,
  "enabled": true
}

// Sites without RSS — via Google News
{
  "name": "Goldman Sachs Insights",
  "url": "https://www.goldmansachs.com/insights/articles",
  "rss_url": "https://news.google.com/rss/search?q=site:goldmansachs.com/insights/articles&hl=en&gl=US&ceid=US:en",
  "use_rss_content_only": false,
  "enabled": true
}

// JS-rendered sites with hidden JSON/AEM endpoints
{
  "name": "JPMorgan Asset Management",
  "url": "https://am.jpmorgan.com/...",
  "json_url": "https://am.jpmorgan.com/.../_jcr_content/.../jpm_am_mosaic.model.json",
  "json_base_url": "https://am.jpmorgan.com",
  "json_pages_key": "pages",
  "enabled": true
}
```

**Parser priority:** `json_url` → `rss_url` → `sitemap_url` → HTML

**Key parameters:**
- `use_rss_content_only: false` — fetches the full article; falls back to RSS excerpt if blocked
- `use_rss_content_only: true` — uses only RSS content, no article fetch (for sites that block scrapers)
- `max_posts_per_blog` — cap on articles per source per run (default: 10)
- `min_relevance_score` — minimum AI score for inclusion in report (0–10)

### user_profile.txt

This is what the AI uses to calibrate relevance. Describe your role, your firm, your clients, your areas of focus. The more specific, the better the analysis.

## 📊 Output

### Report (markdown)

Generated in `output/blog_report_YYYYMMDD_HHMMSS.md`:

```markdown
### 🔥 Article Title
**Relevance:** 8/10
**Published:** March 04, 2026
**Link:** https://example.com/article

#### Summary
2–3 sentence summary as you'd explain it to a colleague.

#### Why it matters for you
Analysis from an advisor perspective: how this connects to your work,
client portfolios, and conversations.

#### Key takeaways
- First standalone insight worth remembering
- Second relevant point
- Third if genuinely distinct

#### Client conversation starters
- "Ready-to-use phrase or question to open this topic with a client..."
- "Second angle..."
```

### State files

`state/analyzed_posts.json` — tracks every analyzed article with score and timestamp
`state/failed_posts.json` — tracks failed fetches with retry count (auto-skipped after 3 attempts)

## 🏗️ Architecture

Built around the **Strategy Pattern** — each source type gets its own parser class, all sharing a common interface:

```python
class BaseParser(ABC):
    @abstractmethod
    def parse(self, url: str, **kwargs) -> List[Dict]:
        pass
```

Available parsers: `HTMLParser`, `SitemapParser`, `RSSParser`, plus a JSON/AEM inline parser for JS-rendered sites.

The `StateManager` handles persistent deduplication, `retry_with_backoff` handles transient errors, and `RateLimiter` prevents API throttling.

## 🔍 Troubleshooting

**No articles found** → Check `logs/blog_monitor_YYYYMMDD.log` for parser details

**Too many 404s** → Some sitemaps have stale URLs. They're auto-skipped after 3 failures.

**Links redirect to consent.google.com (EU/Italy)** → Expected behavior when using Google News RSS from a European IP. The system detects this, cancels the fetch, and uses the RSS excerpt instead. The report link remains the original Google News URL (clickable from your browser where you've already accepted consent).

**Rate limiting** → Default is 20 calls/minute. Adjust in `blog_monitor_v2.py`:
```python
self.rate_limiter = RateLimiter(calls_per_minute=10)
```

## 📅 Scheduling

```bash
# macOS/Linux — every Monday at 9am
crontab -e
0 9 * * 1 cd /path/to/blog-monitor && python3 blog_monitor_v2.py
```

## 🔐 Security

- Never commit `.env` — it's already in `.gitignore`
- Only put information in `user_profile.txt` that you're comfortable making public (this file is tracked by git)

## 💰 Estimated cost

Using `claude-sonnet-4-5`:
- ~2,000 tokens per article analysis
- 10 articles ≈ ~$0.05–0.08 per run
- Weekly runs ≈ ~$0.25–0.35/month

## 🚧 Roadmap

- [x] RSS/Atom native parser
- [x] JSON/AEM endpoint parser
- [x] Google News as discovery feed for JS-rendered sites
- [ ] Article content cache (avoid re-fetching)
- [ ] Async processing with `asyncio`
- [ ] Email delivery of reports
- [ ] Slack/Teams notifications
- [ ] Multi-format export (JSON, CSV, PDF)

## 📄 License

MIT — use it, fork it, adapt it.

---

**Version:** 2.0
