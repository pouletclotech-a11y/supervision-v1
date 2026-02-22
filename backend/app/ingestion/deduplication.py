import hashlib
import redis.asyncio as redis
from datetime import datetime
from app.ingestion.models import NormalizedEvent
from app.core.config import settings

LUA_DEDUP_SCRIPT = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])

if redis.call("EXISTS", key) == 1 then
    redis.call("INCR", key)
    redis.call("EXPIRE", key, ttl)
    return 1 -- Is Duplicate
else
    redis.call("SET", key, 1)
    redis.call("EXPIRE", key, ttl)
    return 0 -- Is New
end
"""

class DeduplicationService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.script = self.redis.register_script(LUA_DEDUP_SCRIPT)
        
        # Config
        self.burst_window = settings.INGESTION.get('burst_window_seconds', 10)
        self.raw_window = 60 # Safety anti-spam window

    def _generate_burst_key(self, event: NormalizedEvent) -> str:
        """
        Business Key (STRICT): tenant|site|time|code|action
        - tenant: event.tenant_id
        - site: event.site_code
        - time: bucket (ts / burst_window)
        - code: event.normalized_type
        - action: event.status
        """
        nm_type = (event.normalized_type or event.event_type or "UNKNOWN").strip().lower()
        status = (event.status or "INFO").strip().lower()
        
        # Bucket timestamp to create distinct burst windows
        ts_val = event.timestamp.timestamp()
        bucket = int(ts_val / self.burst_window)
        
        # Format STRICT: tenant|site|time|code|action
        raw_str = f"{event.tenant_id}|{event.site_code}|{bucket}|{nm_type}|{status}"
        h = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
        return f"burst:{h}"

    def _generate_raw_key(self, event: NormalizedEvent) -> str:
        """
        Safety Key: tenant|site|time|raw_message
        """
        ts_seconds = int(event.timestamp.timestamp())
        # Format: tenant|site|time|raw_message
        raw_str = f"{event.tenant_id}|{event.site_code}|{ts_seconds}|{event.raw_message}"
        h = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
        return f"raw:{h}"

    async def is_duplicate(self, event: NormalizedEvent) -> bool:
        """
        Checks if event is a duplicate.
        """
        # 1. Raw Hash Check (Anti-spam)
        # Prevents ingesting the exact same log line appearing multiple times in split second
        raw_key = self._generate_raw_key(event)
        is_raw_dup = await self.script(keys=[raw_key], args=[self.raw_window])
        
        if is_raw_dup == 1:
            return True

        # 2. Burst Collapse Check (Business Aggregation)
        # If it's the "Same Alarm" (normalized) from "Same Zone" within "Window" -> Duplicate
        burst_key = self._generate_burst_key(event)
        is_burst_dup = await self.script(keys=[burst_key], args=[self.burst_window])
        
        if is_burst_dup == 1:
            return True
            
        return False
