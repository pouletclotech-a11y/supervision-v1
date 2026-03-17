from datetime import datetime
import os
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.auth import deps
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.db.models import ImportLog, Event, MonitoringProvider
from app.schemas.response_models import ImportLogOut, ImportListOut, EventOut, EventListOut, ImportQualitySummary
from app.services.repository import EventRepository

router = APIRouter()

@router.get("/", response_model=ImportListOut)
async def read_imports(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """
    Retrieve file import history with filters and pagination.
    """
    from sqlalchemy import func
    
    # Base query for filter counting and data fetching
    base_stmt = select(ImportLog)
    
    if status:
        base_stmt = base_stmt.where(ImportLog.status == status)
    if date_from:
        base_stmt = base_stmt.where(ImportLog.created_at >= date_from)
    if date_to:
        base_stmt = base_stmt.where(ImportLog.created_at <= date_to)
    if provider_ids is not None:
        base_stmt = base_stmt.where(ImportLog.provider_id.in_(provider_ids))

    # Count Total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch Data
    stmt = base_stmt.order_by(desc(ImportLog.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    # Fetch Monitoring Providers for thresholds (Phase 5)
    providers_stmt = select(MonitoringProvider)
    providers_res = await db.execute(providers_stmt)
    providers_map = {p.id: p for p in providers_res.scalars().all()}

    processed_logs = []
    for log in logs:
        out = ImportLogOut.model_validate(log)
        
        # Phase 6.2 Regression Fix: Populate pdf_support fields for UI
        meta = log.import_metadata or {}
        pdf_support = meta.get("pdf_support")
        
        # Support both new dict format and legacy string format
        if log.archive_path_pdf:
            out.pdf_support_path = f"/api/v1/imports/{log.id}/download?file_type=pdf"
            out.pdf_support_filename = os.path.basename(log.archive_path_pdf)
        elif pdf_support:
            out.pdf_support_path = f"/api/v1/imports/{log.id}/download?file_type=pdf"
            if isinstance(pdf_support, dict):
                out.pdf_support_filename = pdf_support.get("filename")
            else:
                out.pdf_support_filename = str(pdf_support)
        elif log.pdf_path:
            out.pdf_support_path = f"/api/v1/imports/{log.id}/download?file_type=pdf"
            out.pdf_support_filename = "Support.pdf"

        # Integrity match percentage
        if "integrity_check" in meta:
            try:
                out.match_pct = float(meta["integrity_check"].get("match_pct", 0))
            except (ValueError, TypeError):
                out.match_pct = 0.0

        # Phase 5: Quality Summary (Lightweight)
        q_report = log.quality_report or {}
        p_report = log.pdf_match_report or {}
        
        rows_detected = q_report.get("rows_detected", 0)
        events_created = q_report.get("events_created", 0)
        
        # Correction 2: created_ratio semantics
        if rows_detected > 0:
            created_ratio = events_created / rows_detected
        else:
            created_ratio = 1.0 if events_created == 0 else 0.0

        # Correction 3: quality_status (non-blocking)
        provider = providers_map.get(log.provider_id)
        threshold = provider.quality_min_created_ratio if provider else 0.8
        
        status = "OK"
        if created_ratio < threshold:
            status = "WARN"
        skipped_reasons = q_report.get("skipped_reasons", {})
        top_reasons = sorted(skipped_reasons.keys(), key=lambda x: skipped_reasons[x], reverse=True)[:3]
        
        # New Ratios Phase 5 (Step Ratios)
        # Events created are those with TIME. So with_time_ratio on CREATED is 1.0.
        # But we want it on TOTAL detected if possible? 
        # User said: with_time / total. 
        # total here corresponds to events_created + skipped.
        
        missing_time = q_report.get("missing_time_count", 0)
        missing_action = q_report.get("missing_action_count", 0)
        with_code = q_report.get("with_code_count", 0)
        
        with_time_ratio = 1.0
        with_action_ratio = 1.0
        with_code_ratio = 0.0
        
        if events_created > 0:
            # Events with time are all those created
            # If we want a ratio vs total detected: (events_created) / (rows_detected)
            # which is already created_ratio. 
            # We'll follow user prompt: with_action_ratio and with_code_ratio are on created events.
            with_action_ratio = max(0, (events_created - missing_action) / events_created)
            with_code_ratio = min(1.0, with_code / events_created)

        # Phase 5.5: Refined Quality Status
        # Priority: with_time_ratio (100% required) and with_action_ratio (90% target)
        # with_code_ratio is informative only.
        
        status = "OK"
        if with_time_ratio < 1.0:
            status = "CRITICAL"
        elif with_action_ratio < 0.9:
            status = "WARN"
        
        # Override with created_ratio if extremely low
        if created_ratio < 0.5 and status == "OK":
            status = "WARN"
        if created_ratio < 0.1:
            status = "CRITICAL"

        out.quality_summary = ImportQualitySummary(
            created_ratio=created_ratio,
            skipped_count=log.duplicates_count + (rows_detected - events_created),
            top_reasons=list(q_report.get("skipped_reasons", {}).keys()),
            pdf_match_ratio=p_report.get("match_ratio"),
            with_time_ratio=with_time_ratio,
            with_action_ratio=with_action_ratio,
            with_code_ratio=with_code_ratio,
            status=status
        )
        
        # Correction 4: Hide full reports in list
        out.quality_report = None
        out.pdf_match_report = None

        processed_logs.append(out)

    return {
        "imports": processed_logs,
        "total": total
    }

@router.get("/{id}/quality-report")
async def get_quality_report(
    id: int, 
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
):
    """Fetch full quality report JSONB."""
    stmt = select(ImportLog).where(ImportLog.id == id)
    if provider_ids is not None:
        stmt = stmt.where(ImportLog.provider_id.in_(provider_ids))
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
    return log.quality_report or {}

@router.get("/{id}/pdf-match-report")
async def get_pdf_match_report(
    id: int, 
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
):
    """Fetch full PDF match report JSONB."""
    stmt = select(ImportLog).where(ImportLog.id == id)
    if provider_ids is not None:
        stmt = stmt.where(ImportLog.provider_id.in_(provider_ids))
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
    return log.pdf_match_report or {}

@router.get("/{id}/events", response_model=EventListOut)
async def read_import_events(
    id: int,
    skip: int = 0,
    limit: int = 100,
    unmatched_only: bool = False,
    critical_only: bool = False,
    sort_by: str = 'time',
    order: str = 'asc',
    rule_name: Optional[str] = None,
    action_filter: Optional[str] = None,
    code_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """
    Retrieve events for a specific import job with filters, pagination, and sorting.
    """
    from sqlalchemy import func

    # Base Query
    base_stmt = select(Event).where(Event.import_id == id)
    
    if provider_ids is not None:
        # Validate that this import belongs to the user's allowed providers
        stmt_import = select(ImportLog.id).where(ImportLog.id == id, ImportLog.provider_id.in_(provider_ids))
        if not (await db.execute(stmt_import)).scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not authorized to view events for this import")
    
    if unmatched_only:
        base_stmt = base_stmt.where((Event.normalized_type == 'UNKNOWN') | (Event.normalized_type.is_(None)))
        
    if critical_only:
        base_stmt = base_stmt.where(Event.severity == 'CRITICAL')

    if rule_name:
        from app.db.models import EventRuleHit
        base_stmt = base_stmt.join(EventRuleHit, EventRuleHit.event_id == Event.id).where(EventRuleHit.rule_name.ilike(f"%{rule_name}%"))

    if action_filter:
        base_stmt = base_stmt.where(Event.normalized_type.ilike(f"%{action_filter}%"))

    if code_filter:
        base_stmt = base_stmt.where(Event.raw_code.ilike(f"%{code_filter}%"))

    # Count Total (Efficient)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Sorting
    sort_column = Event.time
    if sort_by == 'severity':
        sort_column = Event.severity
    elif sort_by == 'site_code':
        sort_column = Event.site_code
    elif sort_by == 'id':
        sort_column = Event.id
    
    if order.lower() == 'desc':
        base_stmt = base_stmt.order_by(desc(sort_column))
    else:
        base_stmt = base_stmt.order_by(sort_column.asc())

    # Fetch Page
    stmt = base_stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    # 3. Fetch Rule Hits (Phase 1)
    repo = EventRepository(db)
    event_ids = [e.id for e in events]
    hits_map = await repo.get_rule_hits_for_events(event_ids)

    processed_events = []
    for e in events:
        out = EventOut.model_validate(e)
        out.triggered_rules = hits_map.get(e.id, [])
        processed_events.append(out)

    return {
        "events": processed_events,
        "total": total
    }

from fastapi import HTTPException
from fastapi.responses import FileResponse
import os

@router.get("/{id}/download")
async def download_archived_file(
    id: int,
    file_type: str = 'source', # 'source' or 'pdf'
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
):
    """
    Download or view the archived file.
    file_type: 'source' (XLS/CSV) or 'pdf' (Linked PDF)
    """
    stmt = select(ImportLog).where(ImportLog.id == id)
    if provider_ids is not None:
        stmt = stmt.where(ImportLog.provider_id.in_(provider_ids))
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
    
    target_path = log.archive_path
    
    if file_type == 'pdf':
        # Priority: 1. archive_path_pdf (New deterministic) 2. pdf_path (Legacy/Worker temporary)
        target_path = log.archive_path_pdf or log.pdf_path
        if not target_path:
             raise HTTPException(status_code=404, detail="No linked PDF found for this import")

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found on server")
        
    # Determine media type
    media_type = 'application/octet-stream'
    lower_path = target_path.lower()
    if lower_path.endswith('.pdf'):
        media_type = 'application/pdf'
    elif lower_path.endswith('.xls'):
        media_type = 'application/vnd.ms-excel'
    elif lower_path.endswith('.xlsx'):
        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
    return FileResponse(
        target_path, 
        filename=os.path.basename(target_path), 
        media_type=media_type,
        content_disposition_type='inline'
    )

from app.services.inspection_service import InspectionService

@router.get("/{id}/inspect")
async def inspect_import(
    id: int,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
):
    """
    Inspect the archived file to extract headers/text and suggest a profile.
    """
    stmt = select(ImportLog).where(ImportLog.id == id)
    if provider_ids is not None:
        stmt = stmt.where(ImportLog.provider_id.in_(provider_ids))
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
    
    if not log.archive_path or not os.path.exists(log.archive_path):
        raise HTTPException(status_code=400, detail="Archived file not found for inspection")
    
    inspection_result = InspectionService.inspect_file(log.archive_path)
    return inspection_result

@router.get("/{id}/diagnostic")
async def get_import_diagnostic(
    id: int,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
):
    """
    Diagnostic complet pour comprendre les écarts PDF/XLS.
    """
    from sqlalchemy import func
    
    stmt = select(ImportLog).where(ImportLog.id == id)
    if provider_ids is not None:
        stmt = stmt.where(ImportLog.provider_id.in_(provider_ids))
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
        
    meta = log.import_metadata or {}
    integrity = meta.get("integrity_check", {})
    
    # Preview logic (XLS events)
    events_stmt = select(Event).where(Event.import_id == id).limit(5)
    events_result = await db.execute(events_stmt)
    sample_events = events_result.scalars().all()
    
    # Aggregations stats
    top_codes_stmt = select(Event.raw_code, func.count()).where(Event.import_id == id).group_by(Event.raw_code).order_by(func.count().desc()).limit(10)
    top_codes = (await db.execute(top_codes_stmt)).all()
    
    top_types_stmt = select(Event.normalized_type, func.count()).where(Event.import_id == id).group_by(Event.normalized_type).order_by(func.count().desc()).limit(10)
    top_types = (await db.execute(top_types_stmt)).all()

    return {
        "id": id,
        "filename": log.filename,
        "status": log.status,
        "metadata": meta,
        "integrity": integrity,
        "previews": {
            "xls_sample": [EventOut.model_validate(e) for e in sample_events]
        },
        "stats": {
            "top_raw_codes": [{"code": c, "count": cnt} for c, cnt in top_codes],
            "top_types": [{"type": t, "count": cnt} for t, cnt in top_types],
            "total_events": log.events_count,
            "total_duplicates": log.duplicates_count
        }
    }
