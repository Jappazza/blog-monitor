"""
Sitemap Parser - Extracts posts from XML sitemaps
"""
import requests
from datetime import datetime
from typing import List, Dict
from bs4 import BeautifulSoup
from .base_parser import BaseParser


class SitemapParser(BaseParser):
    """Parser for XML sitemap files"""

    def parse(self, sitemap_url: str, **kwargs) -> List[Dict]:
        """
        Parse XML sitemap and extract article URLs

        Args:
            sitemap_url: URL of the sitemap.xml file
            **kwargs: Additional arguments (headers, filter_terms)

        Returns:
            List of posts extracted from sitemap
        """
        headers = kwargs.get('headers', {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        filter_terms = kwargs.get('filter_terms', ['/insights/', '/perspectives/', '/articles/', '/blog/'])

        try:
            self.logger.info(f"Fetching sitemap: {sitemap_url}")
            response = requests.get(sitemap_url, headers=headers, timeout=30)
            response.raise_for_status()

            # Parse XML
            soup = BeautifulSoup(response.content, 'xml')
            url_tags = soup.find_all('url')

            posts = []
            for url_tag in url_tags:
                loc = url_tag.find('loc')
                if not loc:
                    continue

                href = loc.get_text()

                # Filter by terms (insights, articles, blog, etc.)
                if not any(term in href.lower() for term in filter_terms):
                    continue

                # Extract date
                lastmod = url_tag.find('lastmod')
                date_str = 'N/A'
                date_raw = ''

                if lastmod:
                    date_raw = lastmod.get_text()
                    try:
                        date_obj = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                        date_str = date_obj.strftime('%B %d, %Y')
                    except:
                        date_str = date_raw

                # Extract title from URL (placeholder until we fetch the page)
                title = href.split('/')[-1].replace('.html', '').replace('-', ' ').title()

                posts.append({
                    'title': title,
                    'link': href,
                    'excerpt': '',
                    'date': date_str,
                    '_date_raw': date_raw  # For sorting
                })

            # Sort by date (most recent first)
            posts_sorted = sorted(posts, key=lambda x: x.get('_date_raw', '') or '', reverse=True)

            self.logger.info(f"Found {len(posts_sorted)} posts from sitemap")
            return posts_sorted

        except Exception as e:
            self.logger.error(f"Error parsing sitemap {sitemap_url}: {e}")
            return []
