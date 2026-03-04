import logging
import re
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.auth import deps
from app.db.models import ImportLog, Event, User, MonitoringProvider
from app.services.repository import EventRepository, AdminRepository
from app.parsers.factory import ParserFactory
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.ingestion.worker import detect_file_format
from pathlib import Path

router = APIRouter()
logger = logging.getLogger("ingestion-api")

@router.post("/replay-last-48h")
async def replay_last_48h(
    force: bool = Query(..., description="Must be true to proceed"),
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.get_current_active_admin)
):
    """
    Scans imports from the last 48 hours and re-parses them using the new deterministic logic.
    Provides a before/after event count delta.
    """
    if not force:
        raise HTTPException(status_code=400, detail="Param 'force=true' is mandatory")

    # Cutoff 48h in UTC
    cutoff = datetime.utcnow() - timedelta(hours=48)
    
    # 1. Fetch imports
    stmt = select(ImportLog).where(
        ImportLog.created_at >= cutoff,
        ImportLog.status.in_(["SUCCESS", "ERROR", "PROFILE_NOT_CONFIDENT", "REPLAY_REQUESTED"])
    )
    result = await db.execute(stmt)
    imports = result.scalars().all()
    
    if not imports:
        return {
            "message": "No imports found in the last 48 hours",
            "imports_replayed": 0,
            "events_before": 0,
            "events_after": 0,
            "delta": 0,
            "errors_count": 0
        }

    events_before = sum(i.events_count or 0 for i in imports)
    replayed_count = 0
    events_after_total = 0
    errors = []

    pm = ProfileManager()
    await pm.load_profiles(db)
    matcher = ProfileMatcher(pm)
    repo = EventRepository(db)
    admin_repo = AdminRepository(db)

    for imp in imports:
        imp_id = imp.id 
        imp_filename = imp.filename
        archive_path_str = imp.archive_path
        provider_id = imp.provider_id
        
        try:
            if not archive_path_str:
                continue
            
            file_path = Path(archive_path_str)
            if not file_path.exists():
                # Fallback to absolute /app prefix if needed
                if not str(file_path).startswith("/app"):
                    file_path = Path("/app") / str(file_path).lstrip('/')
                
                if not file_path.exists():
                    errors.append({"import_id": imp_id, "error": f"File not found: {archive_path_str}"})
                    continue

            # Detect and Match
            kind = detect_file_format(file_path)
            
            provider = await repo.get_monitoring_provider(provider_id)
            provider_code = provider.code if provider else "UNKNOWN"
            
            profiles = pm.list_profiles()
            matched_profile = None
            potential_profiles = [
                p for p in profiles 
                if (not p.provider_code or p.provider_code == provider_code) 
                and p.format_kind == kind
            ]
            
            for p in sorted(potential_profiles, key=lambda x: x.priority, reverse=True):
                if p.filename_regex:
                    if re.search(p.filename_regex, imp_filename, re.IGNORECASE):
                        matched_profile = p
                        break
                else:
                    matched_profile = p
                    break
            
            if not matched_profile:
                # Fallback matcher
                from app.ingestion.utils import get_file_probe
                headers, text = get_file_probe(file_path)
                matched_profile, _ = matcher.match(file_path, headers=headers, text_content=text)

            if not matched_profile:
                errors.append({"import_id": imp_id, "error": "No profile matched during replay"})
                continue

            # Parser Selection
            parser = ParserFactory.get_parser_by_kind(matched_profile.format_kind) or ParserFactory.get_parser(file_path.suffix)
            if not parser:
                errors.append({"import_id": imp_id, "error": f"No parser for kind {matched_profile.format_kind}"})
                continue

            # Transactional Clear & Parse
            async with db.begin_nested():
                # Purge old data
                await admin_repo.delete_import_data(imp_id)
                
                # Re-parse
                parsed_events = parser.parse(
                    str(file_path),
                    source_timezone=matched_profile.source_timezone,
                    parser_config={
                        "mapping": matched_profile.mapping,
                        "action_config": matched_profile.action_config
                    }
                )
                
                # Import mapping into schema-aware list
                db_evts = await repo.create_batch(parsed_events, import_id=imp_id)
                
                # Update counts
                imp.status = "SUCCESS"
                imp.events_count = len(db_evts)
                events_after_total += len(db_evts)
                replayed_count += 1

            await db.commit() # Commit this import
            
        except Exception as e:
            logger.error(f"Error replaying import {imp_id}: {str(e)}")
            errors.append({"import_id": imp_id, "error": str(e)})
            # nested transaction handled by 'async with db.begin_nested()'

    return {
        "status": "COMPLETED",
        "imports_replayed": replayed_count,
        "events_before": events_before,
        "events_after": events_after_total,
        "delta": events_after_total - events_before,
        "errors_count": len(errors),
        "replay_errors": errors
    }

@router.get("/{import_id}/quality-report")
async def get_quality_report(
    import_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Returns the data quality report for a specific import.
    """
    result = await db.execute(select(ImportLog).where(ImportLog.id == import_id))
    import_log = result.scalars().first()
    if not import_log:
        raise HTTPException(status_code=404, detail="Import not found")
    
    return import_log.quality_report or {}

@router.get("/{import_id}/pdf-match-report")
async def get_pdf_match_report(
    import_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Returns the PDF matching report for a specific import.
    """
    result = await db.execute(select(ImportLog).where(ImportLog.id == import_id))
    import_log = result.scalars().first()
    if not import_log:
        raise HTTPException(status_code=404, detail="Import not found")
    
    return import_log.pdf_match_report or {}
