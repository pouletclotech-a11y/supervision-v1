import logging
from typing import Optional
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger("redis-lock")

class RedisLock:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def acquire(self, key: str, value: str, ttl_seconds: int = 900) -> bool:
        """
        Acquire a distributed lock.
        SET key value NX EX ttl_seconds
        """
        success = await self.redis.set(key, value, nx=True, ex=ttl_seconds)
        if success:
            logger.info(f"Lock acquired: {key}")
            return True
        return False

    async def release(self, key: str, value: str):
        """
        Release a lock safely. 
        Only delete if the value matches (to avoid releasing someone else's lock).
        """
        # Lua script for atomic check-and-delete
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(script, 1, key, value)
        if result:
            logger.info(f"Lock released: {key}")
        else:
            logger.debug(f"Lock release skipped (not owner or already expired): {key}")

async def get_redis_lock() -> RedisLock:
    # Build redis URL (replacing 'db' with 'redis' as in worker.py)
    redis_url = f"redis://{settings.POSTGRES_SERVER.replace('db', 'redis')}:6379"
    client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    return RedisLock(client)
