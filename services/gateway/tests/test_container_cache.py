"""
Unit tests for ContainerHostCache.

TDD Red Phase: These tests should fail until container_cache.py is implemented.
"""

import time


class TestContainerHostCache:
    """Tests for ContainerHostCache class."""

    def test_cache_set_and_get(self):
        """Basic cache set and get operations."""
        from services.gateway.services.container_cache import ContainerHostCache

        cache = ContainerHostCache(max_size=10, ttl_seconds=30)

        # Set and get
        cache.set("lambda-hello", "10.0.0.1")
        result = cache.get("lambda-hello")

        assert result == "10.0.0.1"

    def test_cache_miss_returns_none(self):
        """Cache miss should return None."""
        from services.gateway.services.container_cache import ContainerHostCache

        cache = ContainerHostCache()

        result = cache.get("non-existent-function")

        assert result is None

    def test_cache_ttl_expiry(self):
        """Cache entries should expire after TTL."""
        from services.gateway.services.container_cache import ContainerHostCache

        # Very short TTL for testing
        cache = ContainerHostCache(ttl_seconds=0.1)

        cache.set("lambda-hello", "10.0.0.1")

        # Should hit before TTL
        assert cache.get("lambda-hello") == "10.0.0.1"

        # Wait for TTL to expire
        time.sleep(0.15)

        # Should miss after TTL
        assert cache.get("lambda-hello") is None

    def test_cache_lru_eviction(self):
        """LRU eviction when max_size is exceeded."""
        from services.gateway.services.container_cache import ContainerHostCache

        cache = ContainerHostCache(max_size=2, ttl_seconds=60)

        # Add 2 items
        cache.set("func-1", "host-1")
        cache.set("func-2", "host-2")

        # Access func-1 to make it recently used
        cache.get("func-1")

        # Add 3rd item, should evict func-2 (least recently used)
        cache.set("func-3", "host-3")

        assert cache.get("func-1") == "host-1"  # Still there (recently accessed)
        assert cache.get("func-2") is None  # Evicted
        assert cache.get("func-3") == "host-3"  # Just added

    def test_cache_invalidate(self):
        """Explicit invalidation of cache entry."""
        from services.gateway.services.container_cache import ContainerHostCache

        cache = ContainerHostCache()

        cache.set("lambda-hello", "10.0.0.1")
        assert cache.get("lambda-hello") == "10.0.0.1"

        cache.invalidate("lambda-hello")
        assert cache.get("lambda-hello") is None

    def test_cache_clear(self):
        """Clear all cache entries."""
        from services.gateway.services.container_cache import ContainerHostCache

        cache = ContainerHostCache()

        cache.set("func-1", "host-1")
        cache.set("func-2", "host-2")

        cache.clear()

        assert cache.get("func-1") is None
        assert cache.get("func-2") is None

    def test_cache_ttl_from_env(self, monkeypatch):
        """TTL should be configurable via environment variable."""
        from services.gateway.services.container_cache import ContainerHostCache

        monkeypatch.setenv("CONTAINER_CACHE_TTL", "60")

        # Need to reload to pick up env var, or pass explicitly
        cache = ContainerHostCache()

        # Check that TTL is 60 (from env)
        assert cache.ttl_seconds == 60
