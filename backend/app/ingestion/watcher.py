import asyncio
import logging
import os
import redis.asyncio as redis
from pathlib import Path
from app.core.config import settings

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingestion-watcher")

# Configuration
WATCH_DIR = Path("/app/data/ingress")
REDIS_QUEUE_KEY = "ingestion_queue"
POLL_INTERVAL = 5  # Seconds

async def get_redis_client():
    return redis.from_url(f"redis://{settings.POSTGRES_SERVER.replace('db', 'redis')}:6379", encoding="utf-8", decode_responses=True)

async def watch_loop():
    logger.info(f"Starting Watcher Service on {WATCH_DIR}")
    
    # Ensure directory exists
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    
    redis_client = await get_redis_client()
    processed_files = set()

    while True:
        try:
            # List all files in directory
            current_files = set()
            for file_path in WATCH_DIR.glob("*"):
                if not file_path.is_file():
                    continue

                if file_path.name.startswith((".", "~")):
                     # Ignore hidden/temp files silently or debug log
                     continue

                if file_path.suffix.lower() in ['.xls', '.xlsx', '.pdf']:
                    if file_path.name not in processed_files:
                        logger.info(f"New file file detected: {file_path.name}")
                        # Push to Redis Queue
                        await redis_client.rpush(REDIS_QUEUE_KEY, str(file_path))
                        # Mark as processed (in-memory for now, could be DB backed)
                        processed_files.add(file_path.name)
                else:
                    # Ignore other extensions but log once
                    if file_path.name not in processed_files:
                        logger.warning(f"Ignored unsupported file: {file_path.name}")
                        processed_files.add(file_path.name)
            
            # Simple cleanup of processed_files set if file removed? 
            # ideally we move processed files to an 'archive' folder, but for V1 we stick to this.
            
        except Exception as e:
            logger.error(f"Error in watcher loop: {e}")
        
        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(watch_loop())
    except KeyboardInterrupt:
        logger.info("Watcher Service stopped.")
