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
        Business Key: site_code + normalized_type + zone_label + TIME_BUCKET
        """
        # If normalization failed (empty type), perform simplified fallback or treat as unique per raw message content?
        # User requested: "fallback automatique sur raw-hash" if normalized_type is empty.
        
        nm_type = event.normalized_type or event.event_type or "UNKNOWN"
        z_label = event.zone_label or "GLOBAL"
        
        # Bucket timestamp to create distinct burst windows
        # Use simple integer division by window size
        ts_val = event.timestamp.timestamp()
        bucket = int(ts_val / self.burst_window)
        
        # Unique identifier for the "Burst Group"
        raw_str = f"{event.site_code}|{nm_type}|{z_label}|{bucket}"
        h = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
        return f"burst:{h}"

    def _generate_raw_key(self, event: NormalizedEvent) -> str:
        """
        Safety Key: raw_message + timestamp (rounded to 1s or 10s)
        """
        ts_seconds = int(event.timestamp.timestamp())
        # Round to 1s to catch immediate machine repetitions
        raw_str = f"{event.site_code}|{event.raw_message}|{ts_seconds}"
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
