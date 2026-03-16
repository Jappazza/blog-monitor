#!/usr/bin/env python3
"""
Blog Monitor V2 - Refactored version with modular architecture
Configurable content monitoring and relevance analysis tool
"""
import os
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import anthropic
from typing import List, Dict, Optional
from pathlib import Path

# Import new modular components
from src.utils import setup_logger, StateManager, retry_with_backoff, RateLimiter
from src.parsers import HTMLParser, SitemapParser, RSSParser


def load_env_file():
    """Load .env file from current or parent directory"""
    env_paths = [Path('.env'), Path('../.env'), Path('../../.env')]

    for env_path in env_paths:
        if env_path.exists():
            print(f"Loading .env from: {env_path.absolute()}")
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            return True
    return False


class BlogMonitorV2:
    """Refactored Blog Monitor with improved architecture"""

    def __init__(self, config_path: str = "config/config.json", log_level: str = "INFO"):
        """
        Initialize the monitor

        Args:
            config_path: Path to configuration file
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        # Setup logging
        self.logger = setup_logger("BlogMonitor", log_level)
        self.logger.info("=" * 60)
        self.logger.info("Blog Monitor V2")
        self.logger.info("=" * 60)

        # Load configuration
        self.config = self._load_config(config_path)
        self.logger.info(f"Loaded configuration from {config_path}")

        # Initialize components
        self.state_manager = StateManager()
        self.html_parser = HTMLParser()
        self.sitemap_parser = SitemapParser()
        self.rss_parser = RSSParser()
        self.rate_limiter = RateLimiter(calls_per_minute=20)  # Conservative API rate

        # Initialize Anthropic client
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Load company profile
        self.company_profile = self._load_company_profile()

        # Create output directory
        Path("output").mkdir(exist_ok=True)

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_company_profile(self) -> str:
        """Load company profile for AI analysis"""
        profile_path = self.config.get('company_profile_path', 'config/company_profile.txt')
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.logger.info(f"Loaded company profile from {profile_path}")
                return content
        except FileNotFoundError:
            self.logger.warning(f"Company profile not found at {profile_path}")
            return ""

    def fetch_blog_posts(self, blog_config: Dict) -> List[Dict]:
        """
        Fetch blog posts using appropriate parser

        Args:
            blog_config: Blog configuration dictionary

        Returns:
            List of posts
        """
        url = blog_config['url']
        name = blog_config.get('name', url)

        # Check parser type priority: RSS > JSON > Sitemap > HTML
        if 'rss_url' in blog_config:
            self.logger.info(f"Using RSS parser for {name}")
            return self.rss_parser.parse(blog_config['rss_url'])
        elif 'json_url' in blog_config:
            self.logger.info(f"Using JSON parser for {name}")
            return self._parse_json_feed(blog_config)
        elif 'sitemap_url' in blog_config:
            self.logger.info(f"Using sitemap parser for {name}")
            return self.sitemap_parser.parse(blog_config['sitemap_url'])
        else:
            self.logger.info(f"Using HTML parser for {name}")
            return self.html_parser.parse(url)

    def _parse_json_feed(self, blog_config: Dict) -> List[Dict]:
        """
        Parse a custom JSON feed endpoint (e.g. JPMorgan AEM model.json).

        Expected JSON structure:
            { "<pages_key>": [ { "title": "...", "url": "/relative/path", "description": "...",
                                  "displayDate": "MM/DD/YYYY", "sortDate": <unix_ms> }, ... ] }

        Args:
            blog_config: Blog config dict. Recognised keys:
                - json_url        (required) Full URL of the JSON endpoint
                - json_base_url   (optional) Base URL prepended to relative article paths
                - json_pages_key  (optional) Top-level key that holds the articles list (default: "pages")

        Returns:
            List of post dicts with keys: title, link, date, excerpt
        """
        json_url = blog_config['json_url']
        base_url = blog_config.get('json_base_url', '').rstrip('/')
        pages_key = blog_config.get('json_pages_key', 'pages')
        name = blog_config.get('name', json_url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        try:
            response = requests.get(json_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch JSON feed for {name}: {e}")
            return []

        pages = data.get(pages_key, [])
        if not pages:
            self.logger.warning(f"No items found in '{pages_key}' key for {name}")
            return []

        posts = []
        for page in pages:
            title = (page.get('title') or '').strip()
            relative_url = (page.get('url') or '').strip()
            link = base_url + relative_url if relative_url else ''
            excerpt = (page.get('description') or '').strip()

            # Date: prefer displayDate ("MM/DD/YYYY"), fall back to sortDate (Unix ms)
            date_str = (page.get('displayDate') or '').strip()
            if not date_str:
                sort_date = page.get('sortDate', 0)
                if sort_date:
                    try:
                        date_str = datetime.fromtimestamp(sort_date / 1000).strftime('%m/%d/%Y')
                    except Exception:
                        date_str = ''

            if not title or not link:
                continue

            posts.append({
                'title': title,
                'link': link,
                'date': date_str,
                'excerpt': excerpt,
            })

        self.logger.info(f"Found {len(posts)} articles in JSON feed for {name}")
        return posts

    @retry_with_backoff(max_retries=2, initial_delay=2.0, exceptions=(requests.RequestException,))
    def fetch_full_article(self, url: str) -> tuple:
        """
        Fetch full article content with retry logic.
        Follows redirects and returns the final URL (useful for Google News redirects).

        Args:
            url: Article URL (may be a redirect URL)

        Returns:
            Tuple of (article content as text, final URL after redirects)
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        # Capture final URL after following any redirects
        final_url = response.url

        # Detect Google consent page (triggered for EU/Italian IPs)
        # In this case the content is useless — raise to trigger RSS fallback
        if 'consent.google.com' in final_url:
            raise ValueError(f"Redirected to Google consent page — cannot fetch article content from this region")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        # Extract main content
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            return main_content.get_text(separator='\n', strip=True), final_url

        return soup.get_text(separator='\n', strip=True), final_url

    def analyze_post_with_ai(self, post: Dict, full_content: str) -> Optional[Dict]:
        """
        Analyze post relevance using Claude AI

        Args:
            post: Post dictionary
            full_content: Full article content

        Returns:
            Analysis dictionary or None if error
        """
        # Truncate content if too long
        max_content_length = 8000
        if len(full_content) > max_content_length:
            full_content = full_content[:max_content_length] + "..."

        prompt = f"""You are an experienced private banker and wealth management advisor. You are reading this article to decide whether it is worth your attention and whether it could be useful in conversations with your clients.

YOUR PROFESSIONAL PROFILE:
{self.company_profile}

ARTICLE TO READ:
Title: {post['title']}
URL: {post['link']}
Date: {post.get('date', 'N/A')}
Content:
{full_content}

YOUR TASK:
Read this article as a professional advisor would. Then produce a structured analysis from your own perspective — not as an abstract evaluator, but as the advisor yourself.

Answer these four questions in JSON format:

1. "descrizione": What is this article actually about? Summarize in 2-3 sentences as if explaining it to a colleague.

2. "rilevanza": Why does this matter to YOU, as an advisor? Think about your clients, their portfolios, their concerns, and your strategic priorities. Be specific — what in this article connects to your daily work or your clients' situations?

3. "punti_chiave": What are the 2-4 key takeaways you would want to remember from this article? Write them as clear, standalone statements — things you could recall from memory before a client meeting.

4. "spunti_conversazione": How could you bring this topic up naturally with a client? Write 2-3 ready-to-use conversation openers — actual sentences or questions you might say at the start of a meeting or during a review. Make them feel natural, not like talking points from a script.

Return your response in this exact JSON structure:
{{
  "relevance_score": <number from 1 to 10, where 10 means extremely relevant to your work and clients>,
  "descrizione": "<2-3 sentence summary of the article>",
  "rilevanza": "<why this matters to you as an advisor — specific, personal, grounded in your client relationships>",
  "punti_chiave": [
    "<key takeaway 1>",
    "<key takeaway 2>",
    "<key takeaway 3 — include only if genuinely distinct>"
  ],
  "spunti_conversazione": [
    "<natural conversation opener you could use with a client>",
    "<second opener from a different angle>",
    "<optional third opener if relevant>"
  ]
}}

SCORING GUIDE:
- 8-10: Article directly relevant to your clients' portfolios, concerns, or decisions right now
- 6-7: Useful background or context that could come up in client conversations
- 4-5: Mildly interesting but not immediately actionable
- 1-3: Not relevant to your work or clients

LANGUAGE REQUIREMENT:
Respond entirely in Italian. All fields (descrizione, rilevanza, punti_chiave, spunti_conversazione) must be written in Italian, regardless of the language of the article."""

        try:
            self.rate_limiter.wait_if_needed()

            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # Extract JSON from response
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]

            analysis = json.loads(response_text.strip())

            # Add post metadata
            analysis.update({
                'title': post['title'],
                'link': post['link'],
                'date': post.get('date', 'N/A')
            })

            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing post {post['title']}: {e}")
            return None

    def generate_report(self, analyses: List[Dict], output_format: str = 'markdown') -> str:
        """Generate report from analyses"""
        if output_format == 'markdown':
            return self._generate_markdown_report(analyses)
        else:
            return self._generate_json_report(analyses)

    def _generate_markdown_report(self, analyses: List[Dict]) -> str:
        """Generate Markdown report"""
        min_score = self.config.get('min_relevance_score', 6)
        relevant = [a for a in analyses if a.get('relevance_score', 0) >= min_score]
        relevant.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        report = f"""# Blog Monitor Report
**Data generazione:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Articoli analizzati:** {len(analyses)}
**Articoli rilevanti:** {len(relevant)}

---

"""

        if not relevant:
            report += "\n## Nessun articolo rilevante trovato\n"
            return report

        report += "## Articoli Rilevanti\n\n"

        for i, analysis in enumerate(relevant, 1):
            score = analysis.get('relevance_score', 0)
            emoji = "🔥" if score >= 8 else "⭐" if score >= 7 else "✓"

            report += f"""### {emoji} {analysis['title']}

**Rilevanza:** {score}/10
**Data pubblicazione:** {analysis['date']}
**Link:** [{analysis['link']}]({analysis['link']})

#### Descrizione
{analysis.get('descrizione', 'N/A')}

#### Perché può essere importante per te
{analysis.get('rilevanza', 'N/A')}

"""

            if analysis.get('punti_chiave'):
                report += "#### I punti chiave\n"
                for punto in analysis['punti_chiave']:
                    report += f"- {punto}\n"
                report += "\n"

            if analysis.get('spunti_conversazione'):
                report += "#### Spunti di conversazione con il cliente\n"
                for spunto in analysis['spunti_conversazione']:
                    report += f"- {spunto}\n"

            report += "\n---\n\n"

        return report

    def _generate_json_report(self, analyses: List[Dict]) -> str:
        """Generate JSON report"""
        relevant = [a for a in analyses if a.get('relevance_score', 0) >= 6]
        relevant.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        report = {
            'timestamp': datetime.now().isoformat(),
            'total_analyzed': len(analyses),
            'relevant_count': len(relevant),
            'articles': relevant
        }

        return json.dumps(report, indent=2, ensure_ascii=False)

    def save_report(self, report: str, output_format: str = 'markdown') -> str:
        """Save report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = 'md' if output_format == 'markdown' else 'json'
        filename = f"output/blog_report_{timestamp}.{extension}"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)

        self.logger.info(f"Report saved to: {filename}")
        return filename

    def run(self, max_posts: int = None, force_reanalyze: bool = False):
        """
        Run complete monitoring cycle

        Args:
            max_posts: Maximum posts to analyze per blog
            force_reanalyze: Force reanalysis of already seen posts
        """
        all_analyses = []
        source_errors: dict = {}   # {blog_name: "messaggio errore"} per il RunLog
        initial_count = self.state_manager.get_analyzed_count()
        initial_failed = self.state_manager.get_failed_count()

        # ── Avvia RunLog nel DB Fides (se configurato) ────────────────────
        _db_run_id = None
        try:
            import importlib.util as _ilu, sys as _sys
            _dbw_path = Path(__file__).parent / "fides" / "scripts" / "db_writer.py"
            _spec = _ilu.spec_from_file_location("db_writer", _dbw_path)
            _dbw = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_dbw)
            _sys.modules["db_writer"] = _dbw
            _db_run_id = _dbw.start_run()
            self.logger.info(f"DB: RunLog creato (id={_db_run_id})")
        except Exception as _e:
            self.logger.debug(f"DB writer non disponibile: {_e}")

        self.logger.info(f"\nArticoli già analizzati: {initial_count}")
        self.logger.info(f"Articoli falliti in precedenza: {initial_failed}\n")

        # Get max_posts from config if not specified
        if max_posts is None:
            max_posts = self.config.get('max_posts_per_blog', 10)

        for blog_config in self.config['blogs']:
            if not blog_config.get('enabled', True):
                continue

            name = blog_config.get('name', blog_config['url'])
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"Monitoring: {name}")
            self.logger.info('=' * 60)

            # Fetch posts
            posts = self.fetch_blog_posts(blog_config)

            if not posts:
                self.logger.warning(f"No posts found for {name}")
                continue

            # Limit posts
            posts = posts[:max_posts]

            # Filter already analyzed or failed posts
            if not force_reanalyze:
                filtered_posts = []
                for post in posts:
                    url = post['link']

                    if self.state_manager.is_analyzed(url):
                        self.logger.debug(f"Skipping already analyzed: {post['title']}")
                        continue

                    if self.state_manager.is_failed(url, max_retries=3):
                        self.logger.debug(f"Skipping permanently failed: {post['title']}")
                        continue

                    filtered_posts.append(post)

                skipped = len(posts) - len(filtered_posts)
                if skipped > 0:
                    self.logger.info(f"Skipped {skipped} already processed posts")

                posts = filtered_posts

            if not posts:
                self.logger.info(f"No new posts to analyze for {name}")
                continue

            self.logger.info(f"Analyzing {len(posts)} new posts...")

            # Check if this blog uses RSS-only content
            use_rss_content_only = blog_config.get('use_rss_content_only', False)

            # Analyze each post
            for post in posts:
                title_truncated = post['title'][:60] + "..." if len(post['title']) > 60 else post['title']
                self.logger.info(f"  → {title_truncated}")

                try:
                    # Determine content source
                    full_content = None

                    # Prefer source_url (real article URL) over Google News redirect for display
                    source_url = post.get('source_url', '')
                    if source_url and len(source_url) > 30 and '/' in source_url.replace('https://', '').replace('http://', ''):
                        # source_url looks like a specific article path, use it as the display link
                        self.logger.debug(f"Using source_url as article link: {source_url}")
                        post['link'] = source_url

                    if use_rss_content_only:
                        # Use RSS excerpt/description only (no fetch)
                        full_content = post.get('excerpt', post.get('title', ''))
                        self.logger.debug(f"Using RSS content only for {title_truncated}")
                    else:
                        try:
                            # Try to fetch full content; also capture final URL after redirects
                            full_content, final_url = self.fetch_full_article(post['link'])
                            # Update post link only if we got a real article URL (not a redirect/consent page)
                            if final_url and final_url != post['link'] and 'consent.google.com' not in final_url:
                                self.logger.debug(f"Resolved redirect → {final_url}")
                                post['link'] = final_url
                        except Exception as fetch_error:
                            # Fallback to RSS excerpt if fetch fails (e.g. Google consent redirect)
                            self.logger.warning(f"Failed to fetch full article, using RSS excerpt: {fetch_error}")
                            full_content = post.get('excerpt', post.get('title', ''))

                    if not full_content:
                        raise ValueError("No content available for analysis")

                    # Analyze with AI
                    analysis = self.analyze_post_with_ai(post, full_content)

                    if analysis:
                        analysis['blog_name'] = name
                        all_analyses.append(analysis)

                        # Mark as analyzed
                        self.state_manager.mark_analyzed(
                            post['link'],
                            post['title'],
                            analysis.get('relevance_score')
                        )
                    else:
                        # Mark as failed
                        self.state_manager.mark_failed(
                            post['link'],
                            post['title'],
                            "Analysis returned None"
                        )

                except Exception as e:
                    self.logger.error(f"  ✗ Error processing {post['title']}: {e}")
                    self.state_manager.mark_failed(post['link'], post['title'], str(e))
                    source_errors[name] = str(e)

        # Save state
        self.state_manager.save()

        # Generate report
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Generating report...")
        self.logger.info("=" * 60)

        report = self.generate_report(all_analyses, self.config.get('output_format', 'markdown'))
        self.save_report(report, self.config.get('output_format', 'markdown'))

        # Print summary
        relevant = [a for a in all_analyses if a.get('relevance_score', 0) >= 6]
        new_count = self.state_manager.get_analyzed_count()
        new_failed = self.state_manager.get_failed_count()

        self.logger.info(f"\n{'=' * 60}")
        self.logger.info("✓ Analysis complete!")
        self.logger.info(f"  New posts analyzed: {len(all_analyses)}")
        self.logger.info(f"  Relevant posts found: {len(relevant)}")
        self.logger.info(f"  Total in database: {new_count} (+{new_count - initial_count})")
        self.logger.info(f"  Total failed: {new_failed}")
        self.logger.info("=" * 60)

        # ── Salva nel DB Fides (se il RunLog è stato avviato) ─────────────
        if _db_run_id is not None:
            try:
                _finish_run = _sys.modules["db_writer"].finish_run
                _digest_id = _finish_run(
                    _db_run_id,
                    all_analyses,
                    source_errors or None,
                    min_score=self.config.get('min_relevance_score', 6),
                )
                if _digest_id:
                    self.logger.info(f"DB: Digest salvato (id={_digest_id})")
                else:
                    self.logger.info("DB: RunLog aggiornato (nessun articolo rilevante)")
            except Exception as _e:
                self.logger.error(f"DB: errore nel salvataggio ({_e})")


def main():
    """Entry point"""
    load_env_file()

    # Create monitor and run
    monitor = BlogMonitorV2()
    monitor.run()


if __name__ == "__main__":
    main()
