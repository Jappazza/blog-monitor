"""
Base Parser - Abstract interface for all parsers
"""
from abc import ABC, abstractmethod
from typing import List, Dict
import logging


class BaseParser(ABC):
    """Abstract base class for all blog parsers"""

    def __init__(self):
        self.logger = logging.getLogger(f"BlogMonitor.{self.__class__.__name__}")

    @abstractmethod
    def parse(self, url: str, **kwargs) -> List[Dict]:
        """
        Parse a blog URL and extract posts

        Args:
            url: Blog URL to parse
            **kwargs: Additional parser-specific arguments

        Returns:
            List of post dictionaries with keys: title, link, excerpt, date
        """
        pass

    def _create_post_dict(self, title: str, link: str, excerpt: str = "", date: str = "N/A") -> Dict:
        """
        Create a standardized post dictionary

        Args:
            title: Post title
            link: Post URL
            excerpt: Post excerpt/summary
            date: Publication date

        Returns:
            Standardized post dictionary
        """
        return {
            'title': title,
            'link': link,
            'excerpt': excerpt,
            'date': date
        }
