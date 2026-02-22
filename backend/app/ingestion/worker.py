import asyncio
import logging
import json
import redis.asyncio as redis
import os
import time
import hashlib
import uuid
from pathlib import Path
from datetime import datetime

from app.core.config import settings
from app.parsers.factory import ParserFactory
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PdfParser
from app.ingestion.deduplication import DeduplicationService
from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
from app.services.alerting import AlertingService
from app.services.incident_service import IncidentService
from app.services.tagging_service import TaggingService
from app.services.email_fetcher import EmailFetcher
from app.ingestion.normalizer import Normalizer
from app.services.archiver import ArchiverService
from app.services.provider_resolver import ProviderResolver

# Phase B1: New Imports
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.adapters.base import BaseAdapter, AdapterItem
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.ingestion.redis_lock import RedisLock

# Register Parsers
ParserFactory.register_parser(ExcelParser)
ParserFactory.register_parser(PdfParser)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ingestion-worker")

# Initialize shared services
normalizer = Normalizer()
alerting_service = AlertingService()
archiver = ArchiverService()
provider_resolver = ProviderResolver()

# Initialize Profile Engine (Phase A)
profile_manager = ProfileManager()
profile_manager.load_profiles()
profile_matcher = ProfileMatcher(profile_manager)

async def get_redis_client():
    return redis.from_url(f"redis://{settings.POSTGRES_SERVER.replace('db', 'redis')}:6379", encoding="utf-8", decode_responses=True)

def compute_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def _get_file_probe(file_path: Path) -> tuple:
    """
    Extracts a small sample of headers or text to help the ProfileMatcher.
    - Excel: A1 value (first row)
    - PDF: First page text (limit to 2000 chars)
    """
    ext = file_path.suffix.lower()
    headers = None
    text_content = None
    
    try:
        if ext in ['.xls', '.xlsx']:
            # Check if binary or TSV
            is_binary = False
            with open(file_path, 'rb') as f:
                head = f.read(4)
                if head == b'PK\x03\x04': # ZIP header for .xlsx
                    is_binary = True
            
            if is_binary:
                import pandas as pd
                # Read only 1 row, no header assume first row is data or signal
                df = pd.read_excel(str(file_path), nrows=1, header=None)
                if not df.empty:
                    headers = [str(c).strip() for c in df.iloc[0].tolist() if c is not None]
            else:
                import csv
                from app.utils.text import clean_excel_value
                with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                    reader = csv.reader(f, delimiter='\t')
                    first_row = next(reader, None)
                    if first_row:
                        headers = [clean_excel_value(c) for c in first_row if c]
        
        elif ext == '.pdf':
            import pdfplumber
            with pdfplumber.open(str(file_path)) as pdf:
                if pdf.pages:
                    text_content = pdf.pages[0].extract_text()
                    if text_content:
                        text_content = text_content[:2000]
    except Exception as e:
        logger.warning(f"[Probe] Failed for {file_path.name}: {e}")
        
    return headers, text_content

async def process_ingestion_item(adapter: BaseAdapter, item: AdapterItem, redis_lock: RedisLock, redis_client, poll_run_id: str = ""):
    """
    Refactored ingestion pipeline (Gate B1).
    Handles: Hash -> Lock -> Profile Match -> Parse -> DB -> Archive -> Unlock.
    poll_run_id is propagated to all METRIC logs.
    """
    file_path = Path(item.path)
    
    # 1. Compute Hash (Streaming)
    try:
        item.sha256 = compute_sha256(file_path)
    except Exception as e:
        logger.error(f"[METRIC] event=import_error adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} reason=hash_failed: {e}")
        return

    # 2. Acquire Redis Lock
    lock_key = f"ingestion:lock:file:{item.sha256}"
    lock_token = str(time.time())
    if not await redis_lock.acquire(lock_key, lock_token):
        logger.info(f"[{adapter.__class__.__name__}] Locked, skipping: {item.filename}")
        return

    try:
        async with AsyncSessionLocal() as session:
            repo = EventRepository(session)
            
            # 3. Idempotence Check (SHA256 in DB)
            existing_import = await repo.get_import_by_hash(item.sha256)
            if existing_import and existing_import.status == "SUCCESS":
                logger.info(f"[METRIC] event=import_duplicate adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} sha256={item.sha256[:8]}")
                await adapter.ack_duplicate(item, existing_import.id)
                return

            # 4. Profile Matching (Phase R: with probe & provider resolution)
            sender_email = item.metadata.get('sender_email')
            resolved_provider_id = None
            if sender_email:
                resolved_provider_id = provider_resolver.resolve_provider(sender_email)
            
            headers_probe, text_probe = _get_file_probe(file_path)
            matching_result = profile_matcher.match(file_path, headers=headers_probe, text_content=text_probe)
            
            if matching_result is None:
                logger.warning(f"[METRIC] event=import_unmatched adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} reason=no_profile")
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
                import_log.adapter_name = item.source
                import_log.provider_id = resolved_provider_id # Populate even if unmatched
                if hasattr(item, 'source_message_id') and item.source_message_id:
                    import_log.source_message_id = item.source_message_id
                await repo.update_import_log(import_log.id, "UNMATCHED", 0, 0, "No profile matched")
                await session.commit()
                await adapter.ack_unmatched(item, "No profile matched")
                return

            profile = matching_result

            logger.info(f"[{adapter.__class__.__name__}] Matched '{profile.profile_id}' for {item.filename} (Provider={resolved_provider_id})")
            
            # 5. Get Parser
            ext = file_path.suffix.lower()
            parser = ParserFactory.get_parser(ext) # Use Factory
            
            if not parser:
                error_msg = f"No parser found for extension {ext}"
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
                import_log.adapter_name = item.source
                import_log.provider_id = resolved_provider_id
                if hasattr(item, 'source_message_id') and item.source_message_id:
                    import_log.source_message_id = item.source_message_id
                await repo.update_import_log(import_log.id, "ERROR", 0, 0, error_msg)
                await session.commit()
                await adapter.ack_error(item, error_msg)
                return

            # 6. Full Processing
            # Start official Import Log
            import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
            import_log.adapter_name = item.source
            import_log.provider_id = resolved_provider_id
            if hasattr(item, 'source_message_id') and item.source_message_id:
                import_log.source_message_id = item.source_message_id
            
            try:
                # Robust Parse: Ensure it returns a list
                parse_result = parser.parse(str(file_path))
                if not isinstance(parse_result, list):
                    logger.warning(f"Parser returned {type(parse_result)} instead of list. Attempting to convert.")
                    events = list(parse_result) if hasattr(parse_result, '__iter__') else []
                else:
                    events = parse_result

                logger.info(f"Extracted {len(events)} events using {parser.__class__.__name__}")
                
                # Normalize, Deduplicate, Tag, Alert
                dedup_service = DeduplicationService(redis_client)
                unique_events = []
                duplicates_count = 0
                active_rules = await repo.get_active_rules()
                tagging_service = TaggingService(session)
                
                for event in events:
                    normalizer.normalize(event)
                    await tagging_service.tag_event(event)
                    is_dup = await dedup_service.is_duplicate(event)
                    if not is_dup:
                        unique_events.append(event)
                        await alerting_service.check_and_trigger_alerts(event, active_rules, repo=repo)
                    else:
                        duplicates_count += 1
                
                # DB Insert
                if unique_events:
                    await repo.create_batch(unique_events, import_id=import_log.id)
                    # Incident Reconstruction (Atomic inside transaction)
                    try:
                        incident_service = IncidentService(session)
                        await incident_service.process_batch_incidents(import_log.id)
                    except Exception as inc_err:
                        logger.error(f"Incident reconstruction failed: {inc_err}")

                # Update Status
                await repo.update_import_log(import_log.id, "SUCCESS", len(unique_events), duplicates_count)

                # 7. COMMIT COMMIT COMMIT (Critical before physical move)
                await session.commit()

                logger.info(f"[METRIC] event=import_success adapter={adapter.__class__.__name__} run_id={poll_run_id} import_id={import_log.id} file={item.filename} events={len(unique_events)} duplicates={duplicates_count}")

                # 8. Physical Ack (Move to Done/Archive)
                await adapter.ack_success(item, import_log.id)

            except Exception as e:
                error_msg = f"Crash during processing: {str(e)}"
                logger.error(f"[METRIC] event=import_error adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} reason={error_msg}", exc_info=True)
                await repo.update_import_log(import_log.id, "ERROR", 0, 0, error_msg)
                await session.commit()
                await adapter.ack_error(item, error_msg)

    except Exception as e:
        logger.error(f"[METRIC] event=import_fatal adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} reason={e}", exc_info=True)
    finally:
        # 9. Release Lock
        await redis_lock.release(lock_key, lock_token)

async def worker_loop():
    logger.info("Starting Supervision Worker (Phase B1: Adapters & Locking)...")
    redis_client = await get_redis_client()
    redis_lock = RedisLock(redis_client)
    registry = AdapterRegistry()
    email_fetcher = EmailFetcher()

    last_email_scan = 0

    while True:
        # Generate a unique poll_run_id per cycle for log correlation
        poll_run_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()
        logger.info(f"[METRIC] event=poll_cycle_start run_id={poll_run_id}")

        # 1. Adapter Consumption (Dropbox / Email / Local Files)
        try:
            async for adapter, item in registry.poll_all():
                logger.info(f"[METRIC] event=item_picked adapter={item.source} run_id={poll_run_id} file={item.filename}")
                await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id)
        except Exception as e:
            logger.error(f"[METRIC] event=poll_cycle_error run_id={poll_run_id} reason={e}", exc_info=True)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"[METRIC] event=poll_cycle_done run_id={poll_run_id} duration_ms={elapsed_ms}")

        await asyncio.sleep(5)

async def main():
    logger.info("Starting Refactored worker service...")
    await worker_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped.")
