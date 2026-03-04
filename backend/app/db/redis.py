import redis.asyncio as redis
from app.core.config import settings

async def get_redis_client():
    # Use POSTGRES_SERVER and replace it with redis for hostname
    redis_host = settings.POSTGRES_SERVER.replace('db', 'redis')
    return redis.from_url(f"redis://{redis_host}:6379", encoding="utf-8", decode_responses=True)
