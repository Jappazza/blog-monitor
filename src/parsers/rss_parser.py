"""
RSS Parser - Parses RSS/Atom feeds
"""
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict
from datetime import datetime
from .base_parser import BaseParser


class RSSParser(BaseParser):
    """Parser for RSS/Atom feeds"""

    def __init__(self):
        super().__init__()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }

    def parse(self, url: str, **kwargs) -> List[Dict]:
        """
        Parse an RSS feed and extract posts

        Args:
            url: RSS feed URL to parse
            **kwargs: Additional arguments (timeout, etc.)

        Returns:
            List of post dictionaries
        """
        timeout = kwargs.get('timeout', 15)

        try:
            self.logger.info(f"Fetching RSS feed: {url}")
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            # Find all items (RSS 2.0 standard)
            items = root.findall('.//item')

            if not items:
                # Try Atom format
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
                if items:
                    return self._parse_atom_items(items)

            self.logger.info(f"Found {len(items)} posts in RSS feed")

            posts = []
            for item in items:
                post = self._parse_rss_item(item)
                if post:
                    posts.append(post)

            return posts

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch RSS feed: {e}")
            return []
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse XML: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error parsing RSS: {e}")
            return []

    def _parse_rss_item(self, item: ET.Element) -> Dict:
        """
        Parse a single RSS item element

        Args:
            item: XML element for RSS item

        Returns:
            Post dictionary or None if parsing fails
        """
        try:
            # Extract basic fields
            title_elem = item.find('title')
            link_elem = item.find('link')
            description_elem = item.find('description')
            pub_date_elem = item.find('pubDate')

            # Title is required
            if title_elem is None or not title_elem.text:
                return None

            title = title_elem.text.strip()
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""

            # Extract description (may contain HTML)
            excerpt = ""
            if description_elem is not None and description_elem.text:
                # Remove HTML tags for clean excerpt
                import re
                excerpt = re.sub(r'<[^>]+>', '', description_elem.text)
                excerpt = excerpt.strip()[:500]  # Limit to 500 chars

            # Parse date
            date = "N/A"
            if pub_date_elem is not None and pub_date_elem.text:
                date = pub_date_elem.text.strip()
                # Optionally convert to standard format
                try:
                    # RSS date format: "Wed, 22 Oct 2025 09:20:10 +0000"
                    dt = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z")
                    date = dt.strftime("%B %d, %Y")  # "October 22, 2025"
                except:
                    pass  # Keep original format if parsing fails

            # Extract source URL if present (common in Google News RSS)
            # <source url="https://publisher.com/article-path">Publisher Name</source>
            source_url = ""
            source_elem = item.find('source')
            if source_elem is not None:
                source_url = source_elem.get('url', '').strip()

            post = self._create_post_dict(
                title=title,
                link=link,
                excerpt=excerpt,
                date=date
            )
            # Attach source_url separately (may be publisher homepage or article URL)
            post['source_url'] = source_url
            return post

        except Exception as e:
            self.logger.warning(f"Failed to parse RSS item: {e}")
            return None

    def _parse_atom_items(self, items: List[ET.Element]) -> List[Dict]:
        """
        Parse Atom feed items (fallback for non-RSS feeds)

        Args:
            items: List of Atom entry elements

        Returns:
            List of post dictionaries
        """
        self.logger.info(f"Parsing Atom feed with {len(items)} entries")
        posts = []

        atom_ns = '{http://www.w3.org/2005/Atom}'

        for item in items:
            try:
                title_elem = item.find(f'{atom_ns}title')
                link_elem = item.find(f'{atom_ns}link[@rel="alternate"]')
                summary_elem = item.find(f'{atom_ns}summary')
                updated_elem = item.find(f'{atom_ns}updated')

                if title_elem is None or not title_elem.text:
                    continue

                title = title_elem.text.strip()
                link = link_elem.get('href') if link_elem is not None else ""
                excerpt = summary_elem.text.strip()[:500] if summary_elem is not None and summary_elem.text else ""

                date = "N/A"
                if updated_elem is not None and updated_elem.text:
                    date = updated_elem.text.strip()

                post = self._create_post_dict(
                    title=title,
                    link=link,
                    excerpt=excerpt,
                    date=date
                )
                posts.append(post)

            except Exception as e:
                self.logger.warning(f"Failed to parse Atom entry: {e}")
                continue

        return posts
