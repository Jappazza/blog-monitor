"""
State Manager - Handles tracking of analyzed posts and errors
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set
import logging


class StateManager:
    """Manages persistent state for analyzed posts and error tracking"""

    def __init__(self, state_dir: str = "state"):
        """
        Initialize state manager

        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)

        self.analyzed_file = self.state_dir / "analyzed_posts.json"
        self.errors_file = self.state_dir / "failed_posts.json"

        self.logger = logging.getLogger("BlogMonitor.StateManager")

        self._analyzed_posts: Dict = self._load_json(self.analyzed_file, {"posts": {}})
        self._failed_posts: Dict = self._load_json(self.errors_file, {"posts": {}})

    def _load_json(self, file_path: Path, default: Dict) -> Dict:
        """Load JSON file or return default if not exists"""
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                self.logger.error(f"Error loading {file_path}: {e}")
                return default
        return default

    def _save_json(self, file_path: Path, data: Dict):
        """Save data to JSON file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving {file_path}: {e}")

    def is_analyzed(self, url: str) -> bool:
        """Check if a post has been successfully analyzed"""
        return url in self._analyzed_posts.get("posts", {})

    def is_failed(self, url: str, max_retries: int = 3) -> bool:
        """
        Check if a post has failed too many times

        Args:
            url: URL to check
            max_retries: Maximum number of retries before giving up

        Returns:
            True if post has failed >= max_retries times
        """
        post_data = self._failed_posts.get("posts", {}).get(url)
        if not post_data:
            return False
        return post_data.get("failure_count", 0) >= max_retries

    def mark_analyzed(self, url: str, title: str, relevance_score: Optional[int] = None):
        """Mark a post as successfully analyzed"""
        if "posts" not in self._analyzed_posts:
            self._analyzed_posts["posts"] = {}

        self._analyzed_posts["posts"][url] = {
            "title": title,
            "analyzed_at": datetime.now().isoformat(),
            "relevance_score": relevance_score
        }

        # Remove from failed posts if it was there
        if url in self._failed_posts.get("posts", {}):
            del self._failed_posts["posts"][url]
            self._save_json(self.errors_file, self._failed_posts)

        self.logger.debug(f"Marked as analyzed: {title}")

    def mark_failed(self, url: str, title: str, error: str):
        """Mark a post as failed"""
        if "posts" not in self._failed_posts:
            self._failed_posts["posts"] = {}

        if url in self._failed_posts["posts"]:
            # Increment failure count
            self._failed_posts["posts"][url]["failure_count"] += 1
            self._failed_posts["posts"][url]["last_error"] = error
            self._failed_posts["posts"][url]["last_attempt"] = datetime.now().isoformat()
        else:
            # First failure
            self._failed_posts["posts"][url] = {
                "title": title,
                "failure_count": 1,
                "last_error": error,
                "first_failed": datetime.now().isoformat(),
                "last_attempt": datetime.now().isoformat()
            }

        self.logger.warning(f"Marked as failed: {title} - {error}")

    def get_analyzed_count(self) -> int:
        """Get count of successfully analyzed posts"""
        return len(self._analyzed_posts.get("posts", {}))

    def get_failed_count(self) -> int:
        """Get count of failed posts"""
        return len(self._failed_posts.get("posts", {}))

    def get_failed_urls(self) -> Set[str]:
        """Get set of all failed URLs"""
        return set(self._failed_posts.get("posts", {}).keys())

    def save(self):
        """Save all state to disk"""
        self._save_json(self.analyzed_file, self._analyzed_posts)
        self._save_json(self.errors_file, self._failed_posts)
        self.logger.debug("State saved to disk")

    def get_stats(self) -> Dict:
        """Get statistics about the state"""
        return {
            "total_analyzed": self.get_analyzed_count(),
            "total_failed": self.get_failed_count(),
            "failed_urls": list(self.get_failed_urls())
        }
