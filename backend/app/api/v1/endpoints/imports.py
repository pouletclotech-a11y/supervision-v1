from datetime import datetime
from typing import List, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.db.models import ImportLog, Event
from app.schemas.response_models import ImportLogOut, ImportListOut, EventOut, EventListOut
from app.services.repository import EventRepository

router = APIRouter()

@router.get("/", response_model=ImportListOut)
async def read_imports(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
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

    # Count Total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch Data
    stmt = base_stmt.order_by(desc(ImportLog.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    return {
        "imports": [ImportLogOut.model_validate(log) for log in logs],
        "total": total
    }

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
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Retrieve events for a specific import job with filters, pagination, and sorting.
    """
    from sqlalchemy import func

    # Base Query
    base_stmt = select(Event).where(Event.import_id == id)
    
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
    db: AsyncSession = Depends(get_db)
):
    """
    Download or view the archived file.
    file_type: 'source' (XLS/CSV) or 'pdf' (Linked PDF)
    """
    stmt = select(ImportLog).where(ImportLog.id == id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
    
    target_path = log.archive_path
    
    if file_type == 'pdf':
        if not log.pdf_path:
             raise HTTPException(status_code=404, detail="No linked PDF found for this import")
        target_path = log.pdf_path

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
    db: AsyncSession = Depends(get_db)
):
    """
    Inspect the archived file to extract headers/text and suggest a profile.
    """
    stmt = select(ImportLog).where(ImportLog.id == id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Import not found")
    
    if not log.archive_path or not os.path.exists(log.archive_path):
        raise HTTPException(status_code=400, detail="Archived file not found for inspection")
    
    inspection_result = InspectionService.inspect_file(log.archive_path)
    return inspection_result
