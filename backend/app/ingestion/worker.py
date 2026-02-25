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
from typing import Optional, List, Any

from app.core.config import settings
from app.db.models import ImportLog
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
from app.services.classification_service import ClassificationService

# Phase B1: New Imports
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.adapters.base import BaseAdapter, AdapterItem
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.ingestion.redis_lock import RedisLock
from app.ingestion.utils import compute_sha256, get_file_probe

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
profile_matcher = ProfileMatcher(profile_manager)

async def get_redis_client():
    return redis.from_url(f"redis://{settings.POSTGRES_SERVER.replace('db', 'redis')}:6379", encoding="utf-8", decode_responses=True)


async def process_ingestion_item(adapter: BaseAdapter, item: AdapterItem, redis_lock: RedisLock, redis_client, poll_run_id: str = "", existing_import_id: int = None) -> Optional[int]:
    """
    Refactored ingestion pipeline (Phase 3).
    Handles: Hash -> Lock -> Profile Match -> Parse -> DB -> Archive -> Unlock.
    Returns primary_import_id on success.
    """
    file_path = Path(item.path)
    
    # 1. Compute Hash (Streaming)
    try:
        item.sha256 = compute_sha256(file_path)
    except Exception as e:
        logger.error(f"[METRIC] event=import_error adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} reason=hash_failed: {e}")
        return None

    # 2. Acquire Redis Lock
    lock_key = f"ingestion:lock:file:{item.sha256}"
    lock_token = str(time.time())
    if not await redis_lock.acquire(lock_key, lock_token):
        logger.info(f"[{adapter.__class__.__name__}] Locked, skipping: {item.filename}")
        return None

    try:
        async with AsyncSessionLocal() as session:
            repo = EventRepository(session)
            
            # 3. Idempotence Check (SHA256 in DB)
            existing_import = await repo.get_import_by_hash(item.sha256)
            is_replay = False
            if existing_import:
                if existing_import.status == "SUCCESS":
                    logger.info(f"[METRIC] run_id={poll_run_id} event=import_duplicate adapter={adapter.__class__.__name__} file={item.filename} sha256={item.sha256[:8]}")
                    await adapter.ack_duplicate(item, existing_import.id)
                    return existing_import.id
                elif existing_import.status == "REPLAY_REQUESTED":
                    logger.info(f"[REPLAY] Hash match found for {item.filename} with REPLAY_REQUESTED status. Starting transactional replace.")
                    is_replay = True

            # 4. Classification de l'import (SMTP Provider)
            sender_email = item.metadata.get('sender_email')
            resolved_provider_id = await ClassificationService.classify_email(session, sender_email)
            
            # --- Profiling (déjà existant) ---
            # Reload profiles each item to ensure DB sync
            await profile_manager.load_profiles(session)

            # 5. Profile Matching (Phase 3: abstraction & threshold)
            # The previous provider resolution logic is replaced by ClassificationService.classify_email
            
            headers_probe, text_probe = get_file_probe(file_path)
            profile, match_report = profile_matcher.match(file_path, headers=headers_probe, text_content=text_probe)
            
            if profile is None:
                logger.warning(f"[METRIC] run_id={poll_run_id} event=import_unmatched adapter={adapter.__class__.__name__} file={item.filename} status=PROFILE_NOT_CONFIDENT")
                
                # Traceability (Final Condition 2)
                raw_payload_sample = ""
                if text_probe:
                    raw_payload_sample = text_probe
                elif headers_probe:
                    raw_payload_sample = "|".join(headers_probe)
                
                import_metadata = {
                    "match_score": match_report.get("best_score"),
                    "best_candidate": match_report.get("best_candidate_id"),
                    "match_details": match_report.get("candidates")
                }
                
                import_log = await repo.create_import_log(
                    item.filename, 
                    file_hash=item.sha256,
                    provider_id=resolved_provider_id,
                    import_metadata=import_metadata,
                    raw_payload=raw_payload_sample
                )
                import_log.adapter_name = item.source
                if hasattr(item, 'source_message_id') and item.source_message_id:
                    import_log.source_message_id = item.source_message_id
                
                await repo.update_import_log(import_log.id, "PROFILE_NOT_CONFIDENT", 0, 0, "No profile reached confidence threshold")
                await session.commit()
                await adapter.ack_unmatched(item, "Profile confidence too low")
                return import_log.id

            logger.info(f"[{adapter.__class__.__name__}] Match Confidence OK: '{profile.profile_id}' (Score: {match_report['best_score']})")
            
            # 5. Get Parser
            ext = file_path.suffix.lower()
            parser = ParserFactory.get_parser(ext)
            
            if not parser:
                error_msg = f"No parser found for extension {ext}"
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
                await repo.update_import_log(import_log.id, "ERROR", 0, 0, error_msg)
                await session.commit()
                await adapter.ack_error(item, error_msg)
                return None

            # 6. Full Processing
            if existing_import_id:
                import_log = await repo.session.get(ImportLog, existing_import_id)
            elif is_replay:
                import_log = existing_import
            else:
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
                
            import_log.adapter_name = item.source
            import_log.provider_id = resolved_provider_id
            if hasattr(item, 'source_message_id') and item.source_message_id:
                import_log.source_message_id = item.source_message_id

            # REPLAY CLEANUP: Delete old events within this transaction if replaying
            if is_replay:
                from sqlalchemy import delete
                from app.db.models import Event
                await session.execute(delete(Event).where(Event.import_id == import_log.id))
                logger.info(f"[REPLAY] Cleared previous events for Import {import_log.id}")
            
            try:
                # Phase 4 (Minimal): If we have an existing import (Grouping), PDF is support only
                ext = file_path.suffix.lower()
                if existing_import_id and ext == '.pdf':
                    import_log_primary = await repo.session.get(ImportLog, existing_import_id)
                    
                    # Fallback logic: if XLS (primary) has 0 events, we extract from PDF instead of just linking it
                    if import_log_primary and import_log_primary.events_count == 0:
                        logger.info(f"[Fallback] XLS Import {existing_import_id} was empty. Attempting PDF extraction from {item.filename}")
                        # Update metadata to track fallback
                        meta = dict(import_log_primary.import_metadata or {})
                        meta["fallback_from_xls"] = True
                        meta["actual_source"] = "pdf"
                        import_log_primary.import_metadata = meta
                        # Do NOT return, proceed to extraction below
                    else:
                        logger.info(f"PDF Grouping: Linking {item.filename} as support for Import {existing_import_id}")
                        # Phase B1: Link PDF to existing XLS import using ORM
                        if import_log_primary:
                            import_log_primary.pdf_path = str(file_path)
                            meta = dict(import_log_primary.import_metadata or {})
                            meta["pdf_support"] = str(item.filename)
                            import_log_primary.import_metadata = meta
                            await repo.session.commit()
                            
                        await repo.update_provider_last_import(resolved_provider_id, datetime.utcnow())
                        await session.commit()
                        await adapter.ack_success(item, existing_import_id)
                        return existing_import_id

                # Pass parser_config (Phase 3 abstraction)
                parse_result = parser.parse(
                    str(file_path), 
                    source_timezone=profile.source_timezone#,
                    # parser_config=profile.parser_config # Parser needs update for this
                )
                events = parse_result if isinstance(parse_result, list) else []

                logger.info(f"Extracted {len(events)} events using {parser.__class__.__name__}")
                
                # Normalize, Deduplicate, Tag, Alert
                dedup_service = DeduplicationService(redis_client)
                unique_events = []
                duplicates_count = 0
                active_rules = await repo.get_active_rules()
                tagging_service = TaggingService(session)
                
                for event in events:
                    normalizer.normalize(event)
                    await tagging_service.tag_event(event) # This includes site code normalization
                    
                    # For REPLAY, we might still want to deduplicate against OTHER imports,
                    # but maybe we should be more lenient? 
                    # Decision: bypass deduplication during replay to ensure we replace correctly
                    # OR keep it to maintain consistency? 
                    # User: "replay recalculates and replaces properly".
                    # If we keep it, and they were duplicates initially, they remain duplicates.
                    # BUT, if we fixed the parser, maybe they aren't duplicates anymore.
                    
                    is_dup = await dedup_service.is_duplicate(event)
                    if not is_dup or is_replay: # Force processing in replay mode
                        unique_events.append(event)
                        # Phase 2.A: Actualiser le compteur business (raccordement site)
                        await repo.upsert_site_connection(
                            provider_id=resolved_provider_id,
                            code_site=event.site_code,
                            client_name=event.client_name,
                            seen_at=event.timestamp
                        )
                        await alerting_service.check_and_trigger_alerts(event, active_rules, repo=repo)
                    else:
                        duplicates_count += 1
                
                # DB Insert
                inserted_db_count = 0
                if unique_events:
                    inserted_db_count = await repo.create_batch(unique_events, import_id=import_log.id)
                    try:
                        incident_service = IncidentService(session)
                        await incident_service.process_batch_incidents(import_log.id)
                    except Exception as inc_err:
                        logger.error(f"Incident reconstruction failed: {inc_err}")

                # Metrics persistence
                meta = dict(import_log.import_metadata or {})
                metrics = {
                    "extracted": len(events),
                    "dedup_kept": len(unique_events),
                    "inserted_db": inserted_db_count
                }
                meta["metrics"] = metrics
                import_log.import_metadata = meta

                logger.info(f"[METRIC] import_id={import_log.id} status=SUCCESS extracted={metrics['extracted']} dedup_kept={metrics['dedup_kept']} inserted_db={metrics['inserted_db']}")
                
                await repo.update_import_log(import_log.id, "SUCCESS", inserted_db_count, duplicates_count)
                # Phase 2.B: Update monitoring last success
                await repo.update_provider_last_import(resolved_provider_id, datetime.utcnow())
                await session.commit()
                await adapter.ack_success(item, import_log.id)
                return import_log.id

            except Exception as e:
                error_msg = f"Crash during processing: {str(e)}"
                logger.error(f"[METRIC] event=import_error adapter={adapter.__class__.__name__} run_id={poll_run_id} reason={error_msg}", exc_info=True)
                await session.commit()
                await adapter.ack_error(item, error_msg)
                return None

    except Exception as e:
        logger.error(f"[METRIC] event=import_fatal run_id={poll_run_id} file={item.filename} reason={e}", exc_info=True)
        return None
    finally:
        await redis_lock.release(lock_key, lock_token)

async def worker_loop():
    logger.info("Starting Supervision Worker (Phase 3: Matcher & Normalization)...")
    redis_client = await get_redis_client()
    redis_lock = RedisLock(redis_client)
    registry = AdapterRegistry()
    heartbeat_path = Path("/tmp/worker_heartbeat")

    while True:
        poll_run_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()
        logger.info(f"[METRIC] event=poll_cycle_start run_id={poll_run_id}")

        try:
            items_by_msg = {} # source_message_id -> list[(adapter, item)]
            orphans = []
            
            async for adapter, item in registry.poll_all():
                msg_id = item.source_message_id
                if msg_id:
                    if msg_id not in items_by_msg:
                        items_by_msg[msg_id] = []
                    items_by_msg[msg_id].append((adapter, item))
                else:
                    orphans.append((adapter, item))
            
            # 1. Process Groups (Fusion V1)
            for msg_id, group in items_by_msg.items():
                logger.info(f"[Group] Processing email group {msg_id} ({len(group)} items)")
                # Sort: XLS first
                group.sort(key=lambda x: 0 if x[1].filename.lower().endswith(('.xls', '.xlsx')) else 1)
                
                primary_id = None
                for adapter, item in group:
                    # process_ingestion_item now returns primary_id or None
                    res_id = await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id, existing_import_id=primary_id)
                    if res_id and not primary_id:
                        primary_id = res_id
            
            # 2. Process Orphans
            for adapter, item in orphans:
                await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id)

        except Exception as e:
            logger.error(f"[METRIC] event=poll_cycle_error run_id={poll_run_id} reason={e}", exc_info=True)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"[METRIC] event=poll_cycle_done run_id={poll_run_id} duration_ms={elapsed_ms}")
        
        # Write heartbeat
        try:
            heartbeat_path.touch()
        except:
            pass
            
        await asyncio.sleep(5)

async def main():
    logger.info("Starting Refactored worker service (V3.1)...")
    await worker_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped.")
