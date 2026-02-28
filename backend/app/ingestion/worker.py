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
from sqlalchemy import select, update, delete
from app.db.models import ImportLog, Event
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
from app.services.business_rules import BusinessRuleEngine

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
    Returns (primary_import_id, events) on success.
    """
    file_path = Path(item.path)
    logger.info(f"[Ingestion] ATTACHMENT_RECEIVED: filename={item.filename} size={item.size_bytes} ext={file_path.suffix.lower()}")
    
    # 1. Compute Hash (Streaming)
    try:
        item.sha256 = compute_sha256(file_path)
    except Exception as e:
        logger.error(f"[METRIC] event=import_error adapter={adapter.__class__.__name__} run_id={poll_run_id} file={item.filename} reason=hash_failed: {e}")
        return None, []

    # 2. Acquire Redis Lock
    lock_key = f"ingestion:lock:file:{item.sha256}"
    lock_token = str(time.time())
    if not await redis_lock.acquire(lock_key, lock_token):
        logger.info(f"[{adapter.__class__.__name__}] Locked, skipping: {item.filename}")
        return None, []

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
                    return existing_import.id, []
                elif existing_import.status == "REPLAY_REQUESTED":
                    logger.info(f"[REPLAY] Hash match found for {item.filename} with REPLAY_REQUESTED status. Starting transactional replace.")
                    is_replay = True

            # 4. Classification de l'import (SMTP Provider)
            sender_email = item.metadata.get('sender_email')
            resolved_provider_id = await ClassificationService.classify_email(session, sender_email)
            
            # --- Profiling (déjà existant) ---
            # Reload profiles each item to ensure DB sync
            await profile_manager.load_profiles(session)

            # --- Attachment Filtering (Phase 6.2) ---
            monitoring_provider = await repo.get_monitoring_provider(resolved_provider_id)
            accepted_types = monitoring_provider.accepted_attachment_types if monitoring_provider else ["pdf", "xls", "xlsx"]
            
            ext = file_path.suffix.lower().replace('.', '')
            if ext not in accepted_types:
                logger.info(f"[Ingestion] FILTER_DECISION: IGNORED file={item.filename} reason=FORMAT_REJECTED")
                logger.warning(f"[METRIC] run_id={poll_run_id} event=import_rejected file={item.filename} ext={ext} reason=FORMAT_REJECTED")
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
                import_log.provider_id = resolved_provider_id
                import_log.adapter_name = item.source
                import_log.status = "IGNORED"
                import_log.import_metadata = {"reason": "FORMAT_REJECTED", "extension": ext}
                await session.commit()
                await adapter.ack_error(item, f"REJECTED: format {ext} not accepted for provider {resolved_provider_id}")
                return None, []

            # 5. Profile Matching (Phase 3: abstraction & threshold)
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
                return import_log.id, []

            logger.info(f"[Ingestion] FILTER_DECISION: ACCEPT {ext} file={item.filename} -> matching profile...")
            logger.info(f"[{adapter.__class__.__name__}] MATCH [{item.filename}] EXT={ext} -> {profile.profile_id} (Score: {match_report['best_score']}) ACCEPT")

            # --- Provider Override by Profile (Roadmap 9) ---
            if profile.provider_code:
                # Try to resolve actual provider_id from profile's provider_code
                profile_provider = await repo.get_monitoring_provider_by_code(profile.provider_code)
                if profile_provider:
                    if resolved_provider_id != profile_provider.id:
                        logger.info(f"[Ingestion] PROVIDER_OVERRIDE: email_resolved={resolved_provider_id} -> profile_provider={profile_provider.id} ({profile.provider_code})")
                        resolved_provider_id = profile_provider.id
            
            # 5. Get Parser
            parser = ParserFactory.get_parser(f".{ext}")
            
            if not parser:
                error_msg = f"No parser found for extension .{ext}"
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256)
                await repo.update_import_log(import_log.id, "ERROR", 0, 0, error_msg)
                await session.commit()
                await adapter.ack_error(item, error_msg)
                return None, []

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

            # Phase Roadmap 11: Commit the log creation so it exists in DB even if processing crashes
            await session.commit()
            
            # Re-fetch it in the new transaction
            import_log = await session.get(ImportLog, import_log.id)
            repo = EventRepository(session) # Refresh repo session if needed (though it shares it)

            # REPLAY CLEANUP: Delete old events within this transaction if replaying
            if is_replay:
                await session.execute(delete(Event).where(Event.import_id == import_log.id))
                logger.info(f"[REPLAY] Cleared previous events for Import {import_log.id}")
            
            try:
                # Phase 4 (Minimal): If we have an existing import (Grouping), PDF is support only
                if existing_import_id and ext == 'pdf':
                    import_log_primary = await repo.session.get(ImportLog, existing_import_id)
                    logger.info(f"[Ingestion] PAIR_ATTEMPT: source_message_id={item.source_message_id} import_id={existing_import_id}")
                    
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
                            # Phase 6.2 Regression Fix: Standardize pdf_support object
                            meta["pdf_support"] = {
                                "filename": str(item.filename),
                                "path": str(file_path),
                                "size_bytes": item.size_bytes
                            }
                            import_log_primary.import_metadata = meta
                            logger.info(f"[Ingestion] PDF_SUPPORT_WRITTEN for import_id={existing_import_id}")
                            await repo.session.commit()
                            
                        await repo.update_provider_last_import(resolved_provider_id, datetime.utcnow())
                        await session.commit()
                        
                        # We still parse it for Integrity Check if requested
                        # But we don't insert it as events
                        parse_result = parser.parse(str(file_path), source_timezone=profile.source_timezone)
                        events = parse_result if isinstance(parse_result, list) else []
                        
                        await adapter.ack_success(item, existing_import_id)
                        return existing_import_id, events
                
                # Case: PDF-only email (Phase C.2 Roadmap 4)
                # If it's a PDF and NO existing_import_id was provided (meaning it's the first or only item in group)
                # and it's from a group that might have an XLS later? No, if it's orphans or first of group.
                # If we want it as support only even if alone:
                if not existing_import_id and ext == 'pdf':
                    # Case: PDF-only or PDF-first in group. 
                    # Ensure metadata is written so Frontend shows the Support icon.
                    meta = dict(import_log.import_metadata or {})
                    meta["pdf_support"] = {
                        "filename": str(item.filename),
                        "path": str(file_path),
                        "size_bytes": item.size_bytes
                    }
                    import_log.import_metadata = meta
                    import_log.pdf_path = str(file_path)
                    logger.info(f"[Ingestion] PDF_SUPPORT_WRITTEN for primary import_id={import_log.id}")

                # Pass parser_config (Phase 3 abstraction)
                parse_result = parser.parse(
                    str(file_path), 
                    source_timezone=profile.source_timezone
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
                    
                    is_dup = await dedup_service.is_duplicate(event)
                    if is_dup:
                        event.dup_count = 1 # Mark as duplicate (Phase C)
                        duplicates_count += 1
                    
                    if not is_dup or is_replay:
                        unique_events.append(event)
                        
                # DB Insert & Processing
                db_events = []
                inserted_db_count = 0
                if unique_events:
                    # Phase Roadmap 11: Create DB objects and flush FIRST so events get IDs
                    db_events = await repo.create_batch(unique_events, import_id=import_log.id)
                    await session.flush()
                    inserted_db_count = len(db_events)

                    # Trigger Alerts & Business Rules (now that event.id exists)
                    alerting_service = AlertingService()
                    for db_event in db_events:
                        if db_event.normalized_type != 'OPERATOR_ACTION':
                            # Phase 2.A: Actualiser le compteur business (raccordement site)
                            await repo.upsert_site_connection(
                                provider_id=resolved_provider_id,
                                code_site=db_event.site_code,
                                client_name=db_event.client_name,
                                seen_at=db_event.time
                            )
                            await alerting_service.check_and_trigger_alerts(db_event, active_rules, repo=repo)

                    try:
                        # Phase C: Business Rule Engine (V1)
                        rule_engine = BusinessRuleEngine(session)
                        start_rules = time.time()
                        await rule_engine.evaluate_batch(db_events)
                        duration_rules = (time.time() - start_rules) * 1000
                        logger.info(f"[METRIC] rule_engine_duration_ms={duration_rules:.2f} import_id={import_log.id}")
                    except Exception as rule_err:
                        logger.error(f"Business rules evaluation failed: {rule_err}")

                    try:
                        # Exclude from incident reconstruction if handled by incident_service
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
                return import_log.id, events

            except Exception as e:
                # Phase A Roadmap 11: Persist error details in metadata
                # Must rollback first because session might be tainted (IntegrityError, etc.)
                await session.rollback()
                
                error_msg = f"Crash during processing: {str(e)}"
                logger.error(f"[METRIC] event=import_error adapter={adapter.__class__.__name__} run_id={poll_run_id} reason={error_msg}", exc_info=True)
                
                if import_log:
                    try:
                        # Use direct update for robustness after rollback
                        
                        meta_patch = {
                            "error_code": type(e).__name__,
                            "error_message": str(e)[:500],
                            "error_at": datetime.utcnow().isoformat()
                        }
                        
                        # In PostgreSQL, we can't easily merge JSONB in a simple UPDATE without complex syntax, 
                        # but we can at least set the main fields. 
                        # For simplicity, we'll try to update the status and error_message.
                        stmt = (
                            update(ImportLog)
                            .where(ImportLog.id == import_log.id)
                            .values(
                                status="ERROR",
                                error_message=error_msg[:1000]
                            )
                        )
                        await session.execute(stmt)
                        await session.commit()
                    except Exception as e2:
                        logger.error(f"Failed to persist error metadata: {e2}")
                
                await adapter.ack_error(item, error_msg)
                return None, []

    except Exception as e:
        logger.error(f"[METRIC] event=import_fatal run_id={poll_run_id} file={item.filename} reason={e}", exc_info=True)
        return None, []
    finally:
        await redis_lock.release(lock_key, lock_token)

def compute_integrity_check(xls_events: List[Any], pdf_events: List[Any]) -> dict:
    """
    Compares events from XLS and PDF to compute match percentage.
    Key = (site_code_norm, timestamp_norm, alarm_code_norm)
    """
    def get_key(e):
        from app.ingestion.normalizer import normalize_site_code
        site = normalize_site_code(str(e.site_code or ""))
        ts = e.timestamp.strftime("%Y-%m-%dT%H:%M:%S") if hasattr(e.timestamp, 'strftime') else str(e.timestamp)
        code = str(e.raw_code or "").strip()
        return (site, ts, code)

    # Filter out DETAIL_LOG and OPERATOR_ACTION for comparison? 
    # Or keep everything? User said: "site_code, ts, alarm_code".
    # Let's filter to only events with an alarm_code if possible, or all main events.
    xls_keys = {get_key(e) for e in xls_events if e.event_type != 'DETAIL_LOG'}
    pdf_keys = {get_key(e) for e in pdf_events if e.event_type not in ['DETAIL_LOG', 'OPERATOR_ACTION']}

    matched = xls_keys.intersection(pdf_keys)
    missing_in_pdf = xls_keys - pdf_keys
    missing_in_xls = pdf_keys - xls_keys

    total_xls = len(xls_keys)
    total_pdf = len(pdf_keys)
    
    match_pct = 0
    if max(total_xls, total_pdf) > 0:
        match_pct = len(matched) / max(total_xls, total_pdf)

    return {
        "total_xls": total_xls,
        "total_pdf": total_pdf,
        "matched": len(matched),
        "missing_in_pdf": list(missing_in_pdf)[:5], # Sample
        "missing_in_xls": list(missing_in_xls)[:5],
        "match_pct": round(match_pct, 3)
    }

async def worker_loop():
    logger.info("Starting Supervision Worker (Phase 3: Matcher & Normalization)...")
    
    # Roadmap V12: Dump Monitoring Settings
    async with AsyncSessionLocal() as session:
        merged = await settings.get_monitoring_settings(session)
        logger.info(f"MONITORING_SETTINGS_LOADED: {json.dumps(merged, indent=2)}")

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
                
                primary_import_id = None
                events_map = {"xls": [], "pdf": []}
                
                for adapter, item in group:
                    # Logic for grouping: pass existing_import_id if already set
                    import_id, events = await process_ingestion_item(
                        adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id, 
                        existing_import_id=primary_import_id
                    )
                    
                    if import_id:
                        if not primary_import_id:
                            primary_import_id = import_id
                        
                        ext = item.filename.lower()
                        if ext.endswith(('.xls', '.xlsx')):
                            events_map["xls"].extend(events)
                        elif ext.endswith('.pdf'):
                            events_map["pdf"].extend(events)

                # --- 2. Integrity Check (Phase 6.2) ---
                if primary_import_id and events_map["xls"] and events_map["pdf"]:
                    logger.info(f"[Integrity] Computing check for Import {primary_import_id}")
                    results = compute_integrity_check(events_map["xls"], events_map["pdf"])
                    
                    # Update primary import metadata
                    from app.db.session import engine, AsyncSession
                    async with AsyncSession(engine) as session:
                        # Roadmap V12: Get monitoring settings
                        mon_settings = await settings.get_monitoring_settings(session)
                        
                        import_log = await session.get(ImportLog, primary_import_id)
                        if import_log:
                            meta = dict(import_log.import_metadata or {})
                            meta["integrity_check"] = results
                            
                            # Logique Phase 1 V12: XLS Source of Truth
                            if mon_settings['integrity']['xls_is_source_of_truth'] and import_log.status == "ERROR":
                                # If we had an error but XLS is OK, maybe we should reconsider?
                                # Actually ERROR usually means crash or parser fail.
                                # But if we are here, it means both XLS and PDF were parsed.
                                pass

                            # UI Warning based on settings
                            warn_pct = mon_settings['integrity'].get('warn_pct', 90) / 100
                            if results['match_pct'] < warn_pct:
                                logger.warning(f"[Integrity] WARNING: Low match score {results['match_pct']*100}% (Threshold: {warn_pct*100}%)")
                                meta["integrity_warning"] = True
                            
                            import_log.import_metadata = meta
                            await session.commit()
                            
                    logger.info(f"[Integrity] Result: {results['match_pct']*100}% matched")
                    if results['match_pct'] < 0.9:
                        logger.warning(f"[Integrity] LOW MATCH SCORE: {results['match_pct']*100}% for Import {primary_import_id}")

            # 2. Process Isolated Items
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
