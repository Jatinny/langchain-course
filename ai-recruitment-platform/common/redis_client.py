"""Redis client with connection pooling and cache helpers."""
import json
import logging
from datetime import timedelta
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool

from common.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None


def get_redis_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
    return _pool


class RedisClient:
    """Async Redis client with cache helpers."""

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.Redis(connection_pool=get_redis_pool())
        return self._client

    @property
    def client(self) -> aioredis.Redis:
        return self._get_client()

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value, auto-deserialize JSON."""
        try:
            value = await self.client.get(key)
            if value is None:
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.warning("Redis get failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int | timedelta] = None,
    ) -> bool:
        """Set cached value, auto-serialize to JSON."""
        try:
            serialized = json.dumps(value, default=str)
            if ttl is None:
                await self.client.set(key, serialized)
            elif isinstance(ttl, timedelta):
                await self.client.setex(key, int(ttl.total_seconds()), serialized)
            else:
                await self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning("Redis set failed", key=key, error=str(e))
            return False

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.warning("Redis delete failed", keys=keys, error=str(e))
            return 0

    async def exists(self, key: str) -> bool:
        try:
            return bool(await self.client.exists(key))
        except Exception:
            return False

    async def increment(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        """Increment counter, setting TTL on first call."""
        try:
            pipe = self.client.pipeline()
            await pipe.incr(key, amount)
            await pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning("Redis increment failed", key=key, error=str(e))
            return 0

    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        try:
            serialized = {k: json.dumps(v, default=str) for k, v in mapping.items()}
            return await self.client.hset(name, mapping=serialized)
        except Exception as e:
            logger.warning("Redis hset failed", name=name, error=str(e))
            return 0

    async def hgetall(self, name: str) -> dict[str, Any]:
        try:
            raw = await self.client.hgetall(name)
            return {k: json.loads(v) for k, v in raw.items()}
        except Exception as e:
            logger.warning("Redis hgetall failed", name=name, error=str(e))
            return {}

    async def lpush(self, key: str, *values: Any) -> int:
        try:
            serialized = [json.dumps(v, default=str) for v in values]
            return await self.client.lpush(key, *serialized)
        except Exception as e:
            logger.warning("Redis lpush failed", key=key, error=str(e))
            return 0

    async def publish(self, channel: str, message: Any) -> int:
        """Publish to a Redis pub/sub channel."""
        try:
            return await self.client.publish(channel, json.dumps(message, default=str))
        except Exception as e:
            logger.warning("Redis publish failed", channel=channel, error=str(e))
            return 0

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
redis_client = RedisClient()
