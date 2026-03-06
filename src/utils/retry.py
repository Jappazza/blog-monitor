"""
Retry utilities with exponential backoff
"""
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger("BlogMonitor.Retry")
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries} retries: {e}")
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                    delay *= backoff_factor

            return None  # Should never reach here

        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, calls_per_minute: int = 60):
        """
        Initialize rate limiter

        Args:
            calls_per_minute: Maximum number of calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0
        self.logger = logging.getLogger("BlogMonitor.RateLimiter")

    def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time

        if time_since_last_call < self.min_interval:
            wait_time = self.min_interval - time_since_last_call
            self.logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)

        self.last_call_time = time.time()
