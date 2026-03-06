"""
HTML Parser - Extracts posts from HTML blog pages
"""
import json
import requests
from typing import List, Dict
from bs4 import BeautifulSoup
from .base_parser import BaseParser


class HTMLParser(BaseParser):
    """Parser for standard HTML blog pages"""

    def parse(self, url: str, **kwargs) -> List[Dict]:
        """
        Parse HTML blog page and extract posts

        Args:
            url: Blog URL to parse
            **kwargs: Additional arguments (headers, selectors)

        Returns:
            List of posts extracted from HTML
        """
        headers = kwargs.get('headers', {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        try:
            self.logger.info(f"Fetching HTML from: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Try JSON embedded data first (like Envestnet)
            posts = self._parse_json_data(soup)
            if posts:
                return posts

            # Fall back to standard HTML parsing
            posts = self._parse_standard_html(soup, url)
            self.logger.info(f"Found {len(posts)} posts from HTML")
            return posts

        except Exception as e:
            self.logger.error(f"Error parsing HTML {url}: {e}")
            return []

    def _parse_json_data(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Try to extract posts from embedded JSON data

        Args:
            soup: BeautifulSoup object

        Returns:
            List of posts or empty list if no JSON found
        """
        # Look for blog list component with JSON data (Envestnet pattern)
        blog_component = soup.find('bloglistdisplay', class_='blogListDisplay-drupal')
        if blog_component and blog_component.get('data-bloglistdisplay'):
            try:
                json_data = blog_component['data-bloglistdisplay']
                data = json.loads(json_data)

                if 'partner_data' in data:
                    articles = data['partner_data']
                    self.logger.info(f"Extracted {len(articles)} articles from JSON data")

                    posts = []
                    for article in articles:
                        title = article.get('title', 'No title')
                        href = article.get('href', '')
                        excerpt = article.get('excerpt', '')
                        date = article.get('date', 'N/A')

                        if href:
                            posts.append(self._create_post_dict(title, href, excerpt, date))

                    return posts

            except json.JSONDecodeError as e:
                self.logger.warning(f"Error decoding JSON data: {e}")

        return []

    def _parse_standard_html(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        Parse standard HTML blog structure

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for relative links

        Returns:
            List of posts
        """
        posts = []

        # Common blog selectors (customize as needed)
        selectors = [
            'article',
            '.post',
            '.blog-post',
            '[class*="post"]',
            '[class*="article"]'
        ]

        for selector in selectors:
            articles = soup.select(selector)
            if articles:
                self.logger.debug(f"Found {len(articles)} articles with selector: {selector}")

                for article in articles:
                    # Extract title
                    title_elem = article.find(['h1', 'h2', 'h3', 'h4'])
                    title = title_elem.get_text(strip=True) if title_elem else "No title"

                    # Extract link
                    link_elem = article.find('a', href=True)
                    link = link_elem['href'] if link_elem else ""

                    # Make absolute URL
                    if link and not link.startswith('http'):
                        from urllib.parse import urljoin
                        link = urljoin(base_url, link)

                    # Extract excerpt
                    excerpt_elem = article.find(['p', '.excerpt', '.summary'])
                    excerpt = excerpt_elem.get_text(strip=True) if excerpt_elem else ""

                    # Extract date
                    date_elem = article.find(['time', '.date', '.published'])
                    date = date_elem.get_text(strip=True) if date_elem else "N/A"

                    if link:
                        posts.append(self._create_post_dict(title, link, excerpt, date))

                break  # Use first selector that works

        return posts
