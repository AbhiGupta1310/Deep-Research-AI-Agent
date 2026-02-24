"""
Test: Redis Semantic Cache (cache/redis_cache.py)

Tests cache hit/miss flow with mocked Redis and embedding functions.
"""

from unittest.mock import patch, AsyncMock, MagicMock
import json
import pytest

from app.cache.redis_cache import SemanticCache, CACHE_SIMILARITY_THRESHOLD


class TestSemanticCacheInit:

    def test_init_defaults(self):
        cache = SemanticCache()
        assert cache._redis is None
        assert cache._cache_key_prefix == "dra:cache:"

    @pytest.mark.asyncio
    async def test_get_redis_returns_none_when_no_connection(self):
        """When Redis is unavailable, _get_redis should return None gracefully."""
        cache = SemanticCache()
        with patch("app.cache.redis_cache.aioredis") as mock_aioredis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=ConnectionError("refused"))
            mock_aioredis.from_url.return_value = mock_client
            result = await cache._get_redis()
            assert result is None


class TestSemanticCacheCheckCache:

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        """No cached entries → should return None."""
        cache = SemanticCache()
        cache._redis = AsyncMock()
        cache._redis.hgetall = AsyncMock(return_value={})

        with patch("app.cache.redis_cache.embed_text", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 128
            result = await cache.check_cache("new query about AI")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_report(self):
        """High similarity → should return cached report."""
        cache = SemanticCache()
        cache._redis = AsyncMock()

        cached_embedding = [0.1] * 128
        cached_report = {"content": "Cached report content", "topic": "AI"}

        cache._redis.hgetall = AsyncMock(return_value={
            "abc123": json.dumps({"query": "AI research", "embedding": cached_embedding})
        })
        cache._redis.get = AsyncMock(return_value=json.dumps(cached_report))

        # Mock embed_text to return the same embedding (similarity = 1.0)
        with patch("app.cache.redis_cache.embed_text", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = cached_embedding
            with patch("app.cache.redis_cache.cosine_similarity", return_value=0.98):
                result = await cache.check_cache("AI research overview")

        assert result is not None
        assert result["content"] == "Cached report content"

    @pytest.mark.asyncio
    async def test_cache_low_similarity_returns_none(self):
        """Low similarity → should return None."""
        cache = SemanticCache()
        cache._redis = AsyncMock()

        cache._redis.hgetall = AsyncMock(return_value={
            "abc123": json.dumps({"query": "cooking recipes", "embedding": [0.9] * 128})
        })

        with patch("app.cache.redis_cache.embed_text", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 128
            with patch("app.cache.redis_cache.cosine_similarity", return_value=0.3):
                result = await cache.check_cache("quantum physics")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_handles_embed_failure(self):
        """If embedding fails, should return None."""
        cache = SemanticCache()
        cache._redis = AsyncMock()

        with patch("app.cache.redis_cache.embed_text", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = None
            result = await cache.check_cache("test query")

        assert result is None


class TestSemanticCacheStoreResult:

    @pytest.mark.asyncio
    async def test_store_result_writes_to_redis(self):
        cache = SemanticCache()
        cache._redis = AsyncMock()
        cache._redis.hset = AsyncMock()
        cache._redis.setex = AsyncMock()

        with patch("app.cache.redis_cache.embed_text", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 128
            await cache.store_result("test query", {"content": "test report"})

        cache._redis.hset.assert_called_once()
        cache._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_result_skips_when_no_redis(self):
        """Should silently skip when Redis is unavailable."""
        cache = SemanticCache()
        cache._redis = None
        # Should not raise
        await cache.store_result("test query", {"content": "test report"})

    @pytest.mark.asyncio
    async def test_store_result_skips_when_embed_fails(self):
        cache = SemanticCache()
        cache._redis = AsyncMock()

        with patch("app.cache.redis_cache.embed_text", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = None
            await cache.store_result("test query", {"content": "report"})

        cache._redis.hset.assert_not_called()


class TestSemanticCacheClose:

    @pytest.mark.asyncio
    async def test_close_resets_redis(self):
        cache = SemanticCache()
        cache._redis = AsyncMock()
        await cache.close()
        assert cache._redis is None

    @pytest.mark.asyncio
    async def test_close_noop_when_no_connection(self):
        cache = SemanticCache()
        cache._redis = None
        await cache.close()  # Should not raise
        assert cache._redis is None
