from redis import Redis
import json
from typing import Any, Optional
from datetime import timedelta

class CacheService:
    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)

    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        serialized = json.dumps(value)
        if expire:
            self.redis.setex(key, expire, serialized)
        else:
            self.redis.set(key, serialized)

    async def get(self, key: str) -> Optional[Any]:
        value = self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    async def delete(self, key: str):
        self.redis.delete(key)

    async def set_workflow_cache(self, workflow_id: str, data: dict):
        await self.set(f"workflow:{workflow_id}", data, expire=3600)
