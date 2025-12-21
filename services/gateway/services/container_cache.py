"""
Container Host Cache - TTL-based LRU cache for container hosts.

Reduces latency by caching container host information from Manager,
avoiding redundant HTTP calls on warm starts.
"""

import os
import time
import logging
from collections import OrderedDict
from typing import Optional
from threading import Lock

logger = logging.getLogger("gateway.container_cache")


class ContainerHostCache:
    """
    TTL-based LRU cache for container host names.

    Thread-safe cache that stores function_name -> host mappings
    with automatic expiration and LRU eviction.
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: Optional[float] = None,
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries (default: 100)
            ttl_seconds: Time-to-live in seconds (default: 30, or from CONTAINER_CACHE_TTL env)
        """
        self.max_size = max_size

        # TTL from env or default
        if ttl_seconds is not None:
            self.ttl_seconds = ttl_seconds
        else:
            self.ttl_seconds = float(os.getenv("CONTAINER_CACHE_TTL", "30"))

        # OrderedDict for LRU ordering: {function_name: (host, timestamp)}
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = Lock()

        logger.debug(
            f"ContainerHostCache initialized: max_size={max_size}, ttl={self.ttl_seconds}s"
        )

    def get(self, function_name: str) -> Optional[str]:
        """
        Get cached host for function.

        Args:
            function_name: Lambda function name

        Returns:
            Cached host string, or None if not found or expired
        """
        with self._lock:
            if function_name not in self._cache:
                return None

            host, timestamp = self._cache[function_name]

            # Check TTL
            if time.time() - timestamp > self.ttl_seconds:
                # Expired - remove and return None
                del self._cache[function_name]
                logger.debug(f"Cache expired for {function_name}")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(function_name)
            return host

    def set(self, function_name: str, host: str) -> None:
        """
        Cache host for function.

        Args:
            function_name: Lambda function name
            host: Container host name or IP
        """
        with self._lock:
            # If already exists, update and move to end
            if function_name in self._cache:
                del self._cache[function_name]

            # Add new entry
            self._cache[function_name] = (host, time.time())

            # Evict LRU if over capacity
            while len(self._cache) > self.max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug(f"LRU evicted: {evicted_key}")

    def invalidate(self, function_name: str) -> None:
        """
        Remove specific entry from cache.

        Args:
            function_name: Lambda function name to invalidate
        """
        with self._lock:
            if function_name in self._cache:
                del self._cache[function_name]
                logger.debug(f"Cache invalidated: {function_name}")

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")
