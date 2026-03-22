import asyncio
import logging
import json
import redis.asyncio as redis
import os
import time
from app.db.redis import get_redis_client
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Any
import re

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
from app.services.pdf_match_service import PdfMatchService
from app.services.catalog_service import CatalogService

# Phase B1: New Imports
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.adapters.base import BaseAdapter, AdapterItem
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.ingestion.redis_lock import RedisLock
from app.ingestion.utils import compute_sha256, get_file_probe, detect_file_format

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




async def process_ingestion_item(adapter: BaseAdapter, item: AdapterItem, redis_lock: RedisLock, redis_client, poll_run_id: str = "", existing_import_id: int = None) -> Optional[int]:
    """
    Refactored ingestion pipeline (Phase 3).
    Handles: Hash -> Lock -> Profile Match -> Parse -> DB -> Archive -> Unlock.
    """
    file_path = Path(item.path)
    ext = file_path.suffix.lower().lstrip('.')
    
    # NEW: Detect Format Robustly (Phase 2)
    detected_kind = detect_file_format(file_path)
    logger.info(f"[INGEST_FORMAT_DETECTED] filename={item.filename} kind={detected_kind}")
    
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
                    archive_path = await adapter.ack_duplicate(item, existing_import.id)
                    if archive_path:
                        existing_import.archive_path = str(archive_path)
                        existing_import.archive_status = "ARCHIVED"
                        await session.commit()
                    return existing_import.id, []
                elif existing_import.status == "REPLAY_REQUESTED":
                    logger.info(f"[REPLAY] Hash match found for {item.filename} with REPLAY_REQUESTED status. Starting transactional replace.")
                    is_replay = True

            # 4. Classification initiale et Création de l'ImportLog
            sender_email = item.metadata.get('sender_email')
            resolved_provider_id = await ClassificationService.classify_email(session, sender_email)
            monitoring_provider = await repo.get_monitoring_provider(resolved_provider_id)
            provider_code = monitoring_provider.code if monitoring_provider else "UNKNOWN"

            # Sécurité Lifecycle (Archive / Delete)
            if monitoring_provider and (monitoring_provider.deleted_at is not None or monitoring_provider.is_archived):
                logger.warning(f"[INGESTION_SKIPPED] Provider {provider_code} is archived or deleted. Ignoring file {item.filename}.")
                import_log = await repo.create_import_log(
                    item.filename, 
                    file_hash=item.sha256, 
                    provider_id=resolved_provider_id,
                    import_metadata=item.metadata
                )
                await repo.update_import_log(import_log.id, "IGNORED", 0, 0, f"Provider {provider_code} inactive")
                archive_path = await adapter.ack_unmatched(item, f"Provider {provider_code} inactive")
                if archive_path:
                    import_log.archive_path = str(archive_path)
                    import_log.archive_status = "ARCHIVED"
                await session.commit()
                return import_log.id, []

            # On crée l'import_log dès maintenant (Phase 2 Architecture)
            if existing_import_id:
                import_log = await repo.session.get(ImportLog, existing_import_id)
            elif is_replay:
                import_log = existing_import
            else:
                # Grouping Logic: Check if we already have an import for this source email
                import_log = await repo.get_import_by_source_message_id(item.source_message_id)

            # Security V3: Non-bypassable quota block
            if import_log and import_log.status == "DAILY_QUOTA_EXCEEDED":
                logger.warning(f"[QUOTA_BLOCKED] Skipping secondary file {item.filename} for already blocked lot {import_log.id}")
                archive_path = await adapter.ack_unmatched(item, "DAILY_QUOTA_EXCEEDED (Grouped)")
                if archive_path:
                    import_log.archive_path = str(archive_path)
                    await session.commit()
                return import_log.id, []

            if not import_log:
                # NEW: Daily Quota Check (V3)
                if monitoring_provider:
                    max_quota = monitoring_provider.max_emails_per_day if monitoring_provider.max_emails_per_day is not None else 10
                    current_count = await repo.count_imports_today_tz(monitoring_provider.id)
                    
                    if current_count >= max_quota:
                        logger.warning(f"[QUOTA_EXCEEDED] Provider={provider_code} Count={current_count} Max={max_quota} msg_id={item.source_message_id} file={item.filename}")
                        import_log = await repo.create_import_log(
                            item.filename, 
                            file_hash=item.sha256, 
                            provider_id=resolved_provider_id,
                            import_metadata=item.metadata
                        )
                        import_log.status = "DAILY_QUOTA_EXCEEDED"
                        import_log.source_message_id = item.source_message_id
                        import_log.error_message = f"DAILY_QUOTA_EXCEEDED: Quota of {max_quota} emails reached for today (Paris Time)."
                        await session.commit()
                        # Ack as unmatched/ignored to clear from inbox but not count as success
                        archive_path = await adapter.ack_unmatched(item, "DAILY_QUOTA_EXCEEDED")
                        if archive_path:
                            import_log.archive_path = str(archive_path)
                            import_log.archive_status = "ARCHIVED"
                            await session.commit()
                        return import_log.id, []

                import_log = await repo.create_import_log(
                    item.filename, 
                    file_hash=item.sha256, 
                    provider_id=resolved_provider_id,
                    import_metadata=item.metadata
                )
            else:
                logger.info(f"[Ingestion] Grouping with existing ImportLog {import_log.id} via source_message_id {item.source_message_id}")
                # Update metadata to include second attachment info
                meta = dict(import_log.import_metadata or {})
                meta["secondary_filename"] = item.filename
                meta["secondary_sha256"] = item.sha256
                import_log.import_metadata = meta

            import_log.source_message_id = item.source_message_id
            import_log.adapter_name = item.source

            # 5. Profile Matching (Phase 2: Provider + Kind + Filename)
            await profile_manager.load_profiles(session)
            profiles = profile_manager.list_profiles()
            
            # Phase 2 improvement: Try to find a profile that matches by (provider OR regex) AND format_kind
            matched_profile = None
            
            # We sort by priority just in case
            sorted_profiles = sorted(profiles, key=lambda x: x.priority, reverse=True)
            
            for p in sorted_profiles:
                # Extension fallback: if detected_kind is UNKNOWN, we check if the profile extension matches
                if detected_kind != "UNKNOWN" and p.format_kind != detected_kind:
                    continue
                
                # Case A: Provider matches
                provider_match = (p.provider_code == provider_code)
                
                # Case B: Filename regex matches (stronger signal)
                filename_match = False
                if p.filename_regex:
                    if re.search(p.filename_regex, item.filename, re.IGNORECASE):
                        filename_match = True
                
                # Case C: Profile is provider-agnostic (NULL provider_code)
                agnostic_match = (p.provider_code is None or p.provider_code == "")
                
                # PRIORITY: 1. Regex Match, 2. Explicit Provider Match, 3. Agnostic Match
                if filename_match:
                    matched_profile = p
                    # If we matched via regex, we MUST update the provider to the profile's provider
                    if p.provider_code and p.provider_code != provider_code:
                        logger.info(f"[Classification] Re-classified via profile regex: {item.filename} ({provider_code} -> {p.provider_code})")
                        provider_code = p.provider_code
                        # Synchronize with DB provider_id
                        new_p = await repo.get_monitoring_provider_by_code(p.provider_code)
                        if new_p:
                            import_log.provider_id = new_p.id
                    break
                elif provider_match and not p.filename_regex:
                    matched_profile = p
                    break
                elif agnostic_match:
                    # We store it as a potential match but keep looking for a regex match
                    if not matched_profile:
                        matched_profile = p

            if not matched_profile:
                # Fallback to old matcher (headers/text) if no explicit profile found
                headers_probe, text_probe = get_file_probe(file_path)
                matched_profile, match_report = profile_matcher.match(
                    file_path, 
                    detected_format=detected_kind, 
                    headers=headers_probe, 
                    text_content=text_probe
                )
            
            if matched_profile is None:
                logger.warning(f"[INGEST_REJECT] event=profile_not_found file={item.filename} provider={provider_code} kind={detected_kind}")
                import_log = await repo.create_import_log(item.filename, file_hash=item.sha256, provider_id=resolved_provider_id)
                await repo.update_import_log(import_log.id, "PROFILE_NOT_CONFIDENT", 0, 0, "No profile matched provider/kind/regex")
                archive_path = await adapter.ack_unmatched(item, "No profile matched")
                if archive_path:
                    import_log.archive_path = str(archive_path)
                    import_log.archive_status = "ARCHIVED"
                await session.commit()
                return None, []

            logger.info(f"[INGEST_PROFILE_SELECTED] provider={provider_code} profile_id={matched_profile.profile_id} format_kind={matched_profile.format_kind} (detected={detected_kind}) filename={item.filename}")
            
            # 6. Get Parser
            parser = ParserFactory.get_parser_by_kind(matched_profile.format_kind)
            if not parser:
                logger.warning(f"No parser for kind {matched_profile.format_kind}, falling back to extension {file_path.suffix}")
                parser = ParserFactory.get_parser(file_path.suffix)
            
            # --- EFI DIAGNOSTIC (STRICT MODE - ZERO HARDCODING) ---
            monitoring_provider = await repo.get_monitoring_provider(resolved_provider_id)
            debug_code = settings.MONITORING.get("ingestion", {}).get("debug_provider_code")
            
            is_efi = False
            if monitoring_provider:
                # A: Baseline logic (EFI code)
                if monitoring_provider.code == "EFI" or monitoring_provider.label == "EFI":
                    is_efi = True
                # B: Dynamic override via Setting (PROD-STABLE STRICT)
                if debug_code and monitoring_provider.code == debug_code:
                    is_efi = True
            
            if is_efi:
                logger.info(f"[EFI_INGEST_START] import_id=NEW filename={item.filename} provider_id={resolved_provider_id} ext={ext}")
                logger.info(f"[EFI_ROUTE] selected_parser={parser.__class__.__name__ if parser else 'NONE'} supported_ext={ext}")
                if file_path.exists():
                    logger.info(f"[EFI_FILE_EXISTS] size_bytes={item.size_bytes}")
            
            if not parser:
                error_msg = f"No parser found for extension .{ext}"
                await repo.update_import_log(import_log.id, "ERROR", 0, 0, error_msg)
                archive_path = await adapter.ack_error(item, error_msg)
                if archive_path:
                    import_log.archive_path = str(archive_path)
                    import_log.archive_status = "ARCHIVED"
                await session.commit()
                return None, []

            # 6. Full Processing
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

                # Phase 3: Convert List[MappingRule] to Dict for parsers
                mapping_dict = {m.target: m.source for m in matched_profile.mapping}
                
                # Pass parser_config (Phase 2 deterministic)
                parse_result = parser.parse(
                    str(file_path), 
                    source_timezone=matched_profile.source_timezone,
                    parser_config={
                        "mapping": mapping_dict,
                        "action_config": matched_profile.action_config,
                        "provider_code": provider_code,
                        **(matched_profile.parser_config or {})
                    }
                )
                events = parse_result if isinstance(parse_result, list) else []

                logger.info(f"Extracted {len(events)} events using {parser.__class__.__name__} for profile {matched_profile.profile_id}")
                
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

                # PDF Match Logic (Phase 4)
                pdf_match_report = {}
                # Look for a companion PDF in the same ingestion item or sibling files
                # (Assuming adapter might group them or we look in the same directory)
                pdf_path = None
                # Basic heuristic: if current is .xls/.xlsx, look for .pdf with same name
                potential_pdf = file_path.with_suffix('.pdf')
                if potential_pdf.exists():
                    pdf_path = potential_pdf
                
                if pdf_path and monitoring_provider:
                    try:
                        pdf_parser = PdfParser()
                        pdf_events = pdf_parser.parse(str(pdf_path))
                        
                        pdf_matcher = PdfMatchService()
                        # Pass monitoring_provider converted to dict for config
                        provider_conf = {
                            "code": monitoring_provider.code,
                            "pdf_warning_threshold": monitoring_provider.pdf_warning_threshold,
                            "pdf_critical_threshold": monitoring_provider.pdf_critical_threshold,
                            "pdf_ignore_case": monitoring_provider.pdf_ignore_case,
                            "pdf_ignore_accents": monitoring_provider.pdf_ignore_accents
                        }
                        pdf_match_report = pdf_matcher.calculate_match_report(unique_events, pdf_events, provider_conf)
                        import_log.pdf_match_report = pdf_match_report
                        logger.info(f"[PDF_MATCH] import_id={import_log.id} ratio={pdf_match_report.get('match_ratio')}")
                    except Exception as pdf_err:
                        logger.error(f"PDF matching failed: {pdf_err}")
                        import_log.pdf_match_report = {"error": str(pdf_err)}

                # Metrics & Quality Report persistence
                parser_metrics = getattr(parser, 'last_metrics', {})
                import_log.quality_report = parser_metrics
                
                meta = dict(import_log.import_metadata or {})
                metrics = {
                    "extracted": len(events),
                    "dedup_kept": len(unique_events),
                    "inserted_db": inserted_db_count
                }
                meta["metrics"] = metrics
                import_log.import_metadata = meta

                logger.info(f"[EVENTS_CREATED] import_id={import_log.id} count={inserted_db_count} (extracted={len(events)}, dedup_kept={len(unique_events)})")
                
                await repo.update_import_log(import_log.id, "SUCCESS", inserted_db_count, duplicates_count)
                # Phase 2.B: Update monitoring last success
                await repo.update_provider_last_import(resolved_provider_id, datetime.utcnow())
                
                archive_path = await adapter.ack_success(item, import_log.id)
                if archive_path:
                    import_log.archive_path = str(archive_path)
                    import_log.archive_status = "ARCHIVED"
                
                # Archive PDF companion if exists
                if pdf_path and pdf_path.exists():
                    try:
                        archived_pdf, _ = archiver.archive_file(pdf_path, import_log.created_at)
                        import_log.archive_path_pdf = str(archived_pdf)
                        logger.info(f"[ARCHIVE_PDF] import_id={import_log.id} path={archived_pdf}")
                    except Exception as arch_err:
                        logger.error(f"Failed to archive PDF companion: {arch_err}")
                
                await session.commit()
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
                
                archive_path = await adapter.ack_error(item, error_msg)
                if archive_path and import_log:
                    import_log.archive_path = str(archive_path)
                    import_log.archive_status = "ARCHIVED"
                
                if import_log:
                    await session.commit()
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

    last_redis_heartbeat = 0
    parse_times = [] # Keep last 100 parse times for moving average
    last_catalog_update_day = None

    while True:
        poll_run_id = str(uuid.uuid4())[:8]
        t_cycle_start = time.monotonic()
        
        # 1. Update Heartbeat (Redis + File)
        now = time.time()
        if now - last_redis_heartbeat > 30:
            try:
                heartbeat_data = {
                    "timestamp": datetime.now().isoformat(),
                    "worker_id": os.environ.get("HOSTNAME", "default-worker"),
                    "status": "RUNNING"
                }
                # Optional: Include simple metrics in heartbeat
                if parse_times:
                    heartbeat_data["avg_parse_time_ms"] = round(sum(parse_times) / len(parse_times), 2)
                
                await redis_client.set("supervision:worker:heartbeat", json.dumps(heartbeat_data), ex=90)
                last_redis_heartbeat = now
                logger.info(f"[METRIC] heartbeat_updated run_id={poll_run_id}")
            except Exception as e:
                logger.error(f"Failed to update Redis heartbeat: {e}")

        # Update Docker healthcheck file
        heartbeat_path.touch()

        # Phase P3: Daily Catalog Update
        now_dt = datetime.now()
        current_day = now_dt.date()
        if last_catalog_update_day != current_day:
            # On déclenche la mise à jour une fois par jour (idéalement après les gros imports de journée)
            # Pour le test on peut juste vérifier que le jour a changé
            logger.info(f"[P3] Changement de jour détecté ({current_day}). Déclenchement de la mise à jour de l'annuaire...")
            try:
                # On écrit dans le dossier docs relatif au worker (/app/docs)
                # Qui correspond à backend/docs sur l'hôte
                await CatalogService.generate_catalog(docs_dir="docs")
                last_catalog_update_day = current_day
                logger.info("[P3] Annuaire mis à jour avec succès.")
            except Exception as e:
                logger.error(f"[P3] Erreur lors de la mise à jour automatique de l'annuaire : {e}")

        logger.info(f"[METRIC] event=poll_cycle_start run_id={poll_run_id}")

        try:
            items_by_msg = {} # source_message_id -> list[(adapter, item)]
            orphans = []
            queue_depth = 0
            
            async for adapter, item in registry.poll_all():
                queue_depth += 1
                msg_id = item.source_message_id
                if msg_id:
                    if msg_id not in items_by_msg:
                        items_by_msg[msg_id] = []
                    items_by_msg[msg_id].append((adapter, item))
                else:
                    orphans.append((adapter, item))
            
            # Store queue_depth in Redis for /health
            await redis_client.set("supervision:worker:queue_depth", queue_depth, ex=300)
            
            # 1. Process Groups (Fusion V1)
            for msg_id, group in items_by_msg.items():
                logger.info(f"[Group] Processing email group {msg_id} ({len(group)} items)")
                # Sort: XLS first
                group.sort(key=lambda x: 0 if x[1].filename.lower().endswith(('.xls', '.xlsx')) else 1)
                
                primary_import_id = None
                events_map = {"xls": [], "pdf": []}
                
                for adapter, item in group:
                    # Logic for grouping: pass existing_import_id if already set
                    t_parse_start = time.monotonic()
                    import_id, events = await process_ingestion_item(
                        adapter, item, redis_lock, redis_client, poll_run_id=poll_run_id, 
                        existing_import_id=primary_import_id
                    )
                    t_parse_end = time.monotonic()
                    parse_ms = (t_parse_end - t_parse_start) * 1000
                    parse_times.append(parse_ms)
                    if len(parse_times) > 100: parse_times.pop(0)
                    
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

        elapsed_ms = int((time.monotonic() - t_cycle_start) * 1000)
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
