"""
Redis Semantic Cache.
Caches research results by query embedding similarity.
Returns cached reports for similar queries (cosine similarity > 0.92).
"""

import os
import json
import hashlib
from typing import Optional, Dict, Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from ..embeddings import embed_text, cosine_similarity


# Cache configuration
CACHE_SIMILARITY_THRESHOLD = 0.92
CACHE_TTL_SECONDS = 86400  # 24 hours


class SemanticCache:
    """
    Semantic cache using Redis for storing and retrieving research reports.
    
    Uses embedding similarity to match incoming queries against cached queries.
    If similarity > threshold, returns the cached report instead of re-running the pipeline.
    """

    def __init__(self):
        self._redis = None
        self._cache_key_prefix = "dra:cache:"
        self._index_key = "dra:cache:index"

    async def _get_redis(self):
        """Lazy init Redis connection."""
        if self._redis is None:
            if aioredis is None:
                print("[SemanticCache] Redis package not installed. Cache disabled.")
                return None
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            try:
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
                await self._redis.ping()
                print("[SemanticCache] Connected to Redis.")
            except Exception as e:
                print(f"[SemanticCache] Failed to connect to Redis: {e}. Cache disabled.")
                self._redis = None
        return self._redis

    async def check_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Check if a similar query exists in cache.

        Args:
            query: The incoming user query.

        Returns:
            Cached report dict if similarity > threshold, else None.
        """
        r = await self._get_redis()
        if r is None:
            return None

        try:
            # Embed the incoming query
            query_embedding = await embed_text(query)
            if query_embedding is None:
                return None

            # Get all cached query embeddings from the index
            cached_entries = await r.hgetall(self._index_key)

            best_match_key = None
            best_similarity = 0.0

            for cache_key, cached_data_str in cached_entries.items():
                cached_data = json.loads(cached_data_str)
                cached_embedding = cached_data.get("embedding", [])

                if not cached_embedding:
                    continue

                similarity = cosine_similarity(query_embedding, cached_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_key = cache_key

            if best_similarity >= CACHE_SIMILARITY_THRESHOLD and best_match_key:
                # Cache hit — retrieve the full report
                report_data = await r.get(f"{self._cache_key_prefix}{best_match_key}")
                if report_data:
                    print(f"[SemanticCache] Cache HIT (similarity: {best_similarity:.4f})")
                    return json.loads(report_data)

            print(f"[SemanticCache] Cache MISS (best similarity: {best_similarity:.4f})")
            return None

        except Exception as e:
            print(f"[SemanticCache] Error checking cache: {e}")
            return None

    async def store_result(self, query: str, report_data: Dict[str, Any]) -> None:
        """
        Store a research result in the cache.

        Args:
            query: The original user query.
            report_data: The full report data to cache.
        """
        r = await self._get_redis()
        if r is None:
            return

        try:
            # Embed the query
            query_embedding = await embed_text(query)
            if query_embedding is None:
                return

            # Create a unique cache key
            cache_key = hashlib.md5(query.encode()).hexdigest()

            # Store the embedding in the index
            index_entry = json.dumps({
                "query": query,
                "embedding": query_embedding,
            })
            await r.hset(self._index_key, cache_key, index_entry)

            # Store the full report
            await r.setex(
                f"{self._cache_key_prefix}{cache_key}",
                CACHE_TTL_SECONDS,
                json.dumps(report_data),
            )
            print(f"[SemanticCache] Stored result for query: {query[:50]}...")

        except Exception as e:
            print(f"[SemanticCache] Error storing result: {e}")

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
