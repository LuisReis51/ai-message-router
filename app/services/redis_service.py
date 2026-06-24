from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.models import TaskResult

logger = logging.getLogger(__name__)

TASK_PREFIX = "ai_router:task:"
TASK_TTL = 3600  # 1 hour


class RedisService:
    """Redis-backed caching, pub/sub, and task persistence."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None

    async def connect(self) -> None:
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await self._redis.ping()
            logger.info("Connected to Redis at %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) - running without persistence/cache", exc)
            self._redis = None

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    async def store_task(self, result: TaskResult) -> None:
        if not self._redis:
            return
        key = f"{TASK_PREFIX}{result.task_id}"
        await self._redis.set(key, result.model_dump_json(), ex=TASK_TTL)

    async def get_task(self, task_id: str) -> TaskResult | None:
        if not self._redis:
            return None
        key = f"{TASK_PREFIX}{task_id}"
        data = await self._redis.get(key)
        if data:
            return TaskResult.model_validate_json(data)
        return None

    async def publish_event(self, channel: str, data: dict[str, Any]) -> None:
        if not self._redis:
            return
        await self._redis.publish(channel, json.dumps(data))

    async def cache_set(self, key: str, value: str, ttl: int = 300) -> None:
        if not self._redis:
            return
        await self._redis.set(key, value, ex=ttl)

    async def cache_get(self, key: str) -> str | None:
        if not self._redis:
            return None
        return await self._redis.get(key)
