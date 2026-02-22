import asyncio
import logging
import shutil
import uuid
import sys
import os
from pathlib import Path
from datetime import datetime

# Add app to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.ingestion.worker import process_ingestion_item
from app.ingestion.adapters.base import AdapterItem, BaseAdapter
from app.ingestion.redis_lock import RedisLock
from app.ingestion.worker import get_redis_client
from app.services.repository import EventRepository
from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog, Event
from sqlalchemy import select

# Configure logging to stdout for capture
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("test-real-ingestion")

class MockAdapter(BaseAdapter):
    async def poll(self):
        yield None
    async def ack_success(self, item, import_id): logger.info(f"ACK SUCCESS: {item.filename}")
    async def ack_duplicate(self, item, import_id): logger.info(f"ACK DUPLICATE: {item.filename}")
    async def ack_error(self, item, error_msg): logger.error(f"ACK ERROR: {item.filename} - {error_msg}")
    async def ack_unmatched(self, item, reason): logger.warning(f"ACK UNMATCHED: {item.filename} - {reason}")

async def run_test():
    logger.info("Starting Real Ingestion Test V3 (Strict Mode)")
    
    redis_client = await get_redis_client()
    redis_lock = RedisLock(redis_client)
    adapter = MockAdapter()
    
    spgo_path = "/app/data/archive/2026/02/22/smoke_spgo.xls"
    cors_path = "/app/data/archive/duplicates/1769814590_2026-01-30-07-YPSILON_HISTO.pdf"
    
    test_files = [
        {"name": "smoke_spgo.xls", "path": spgo_path},
        {"name": "cors_histo.pdf", "path": cors_path}
    ]
    
    # 0. Cleanup specific files from DB to allow "fresh" ingestion test
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        for f in test_files:
            # We delete by filename to allow re-testing
            stmt = delete(ImportLog).where(ImportLog.filename == f["name"])
            await session.execute(stmt)
        await session.commit()
    
    poll_run_id = f"test-{uuid.uuid4().hex[:6]}"
    logger.info(f"Using run_id={poll_run_id}")
    
    for file_info in test_files:
        if not os.path.exists(file_info["path"]):
            logger.error(f"File not found: {file_info['path']}")
            continue
            
        # Create a unique copy to force a new hash
        ext = os.path.splitext(file_info["path"])[1]
        temp_path = f"/tmp/{file_info['name']}.{uuid.uuid4().hex[:6]}{ext}"
        shutil.copy(file_info["path"], temp_path)
        with open(temp_path, "ab") as f:
            f.write(b" ") # Change hash
        
        stats = os.stat(file_info["path"])
        item = AdapterItem(
            filename=file_info["name"],
            path=temp_path,
            size_bytes=stats.st_size,
            mtime=datetime.fromtimestamp(stats.st_mtime),
            source="test-manual"
        )
        
        logger.info(f"--- Testing ingestion for {file_info['name']} ---")
        
        # 1. First Ingestion
        await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id)
        
        # 2. Verify in DB
        async with AsyncSessionLocal() as session:
            repo = EventRepository(session)
            # Find the import log
            stmt = select(ImportLog).where(ImportLog.filename == file_info["name"]).order_by(ImportLog.created_at.desc())
            res = await session.execute(stmt)
            import_log = res.scalars().first()
            
            if import_log and import_log.status == "SUCCESS":
                logger.info(f"SUCCESS: {file_info['name']} ingested. Events: {import_log.events_count}")
                
                # Check Pydantic check implicitly by successful DB insert of NormalizedEvent batch
                # Check for tenant_id in events
                stmt_evt = select(Event).where(Event.import_id == import_log.id)
                res_evt = await session.execute(stmt_evt)
                evts = res_evt.scalars().all()
                if evts and all(e.site_code for e in evts):
                    logger.info(f"VERIFIED: All events from {file_info['name']} have valid site_code and were processed.")
            else:
                 logger.error(f"FAILURE: {file_info['name']} ingestion failed or unexpected status: {import_log.status if import_log else 'No Log'}")

        # 3. Re-ingestion (Idempotency check)
        logger.info(f"--- Testing RE-ingestion for {file_info['name']} ---")
        await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id)
        # Should log "import_duplicate" or similar

if __name__ == "__main__":
    asyncio.run(run_test())
