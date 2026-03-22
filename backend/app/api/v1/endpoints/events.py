from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.auth import deps
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.db.models import Event
from app.schemas.response_models import EventOut, EventDetailOut
from app.services.repository import EventRepository

router = APIRouter()

@router.get("/", response_model=List[EventOut])
async def read_events(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """
    Retrieve latest events.
    """
    stmt = select(Event)
    
    if provider_ids is not None:
        from app.db.models import ImportLog
        stmt = stmt.join(ImportLog, Event.import_id == ImportLog.id).where(ImportLog.provider_id.in_(provider_ids))
        
    stmt = stmt.order_by(desc(Event.time)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    # 3. Fetch Rule Hits (Phase 1)
    repo = EventRepository(db)
    event_ids = [e.id for e in events]
    hits_map = await repo.get_rule_hits_for_events(event_ids)
    
    # 4. Conversion and injection
    out = []
    for evt in events:
        evt_out = EventOut.model_validate(evt)
        evt_out.triggered_rules = hits_map.get(evt.id, [])
        out.append(evt_out)
        
    return out
@router.get("/{id}", response_model=EventDetailOut)
async def get_event_details(
    id: int,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """
    Phase 3: Detailed view of a single event.
    """
    from app.db.models import EventRuleHit
    from sqlalchemy import func

    # Query event
    stmt = select(Event).where(Event.id == id)
    
    if provider_ids is not None:
        from app.db.models import ImportLog
        stmt = stmt.join(ImportLog, Event.import_id == ImportLog.id).where(ImportLog.provider_id.in_(provider_ids))
        
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get score if any
    hit_stmt = select(EventRuleHit.score).where(EventRuleHit.event_id == id).limit(1)
    hit_res = await db.execute(hit_stmt)
    score = hit_res.scalar()

    # Model map
    out = EventDetailOut.model_validate(event)
    out.score = score
    out.created_at = event.created_at # Ensure mapping if needed
    
    return out
@router.get("/{id}/context", response_model=List[EventOut])
async def get_event_context(
    id: int,
    window_minutes: int = 10,
    db: AsyncSession = Depends(get_db),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """
    Fetch events surrounding a specific event (±N minutes) for the same site.
    Useful for understanding the context of an alert.
    """
    from datetime import timedelta
    
    # 1. Fetch reference event
    stmt_ref = select(Event).where(Event.id == id)
    res_ref = await db.execute(stmt_ref)
    ref_event = res_ref.scalar_one_or_none()
    
    if not ref_event:
        raise HTTPException(status_code=404, detail="Reference event not found")
        
    # 2. Define time window
    start_time = ref_event.time - timedelta(minutes=window_minutes)
    end_time = ref_event.time + timedelta(minutes=window_minutes)
    
    # 3. Query surrounding events for the same site
    stmt = (
        select(Event)
        .where(Event.site_code == ref_event.site_code)
        .where(Event.time >= start_time)
        .where(Event.time <= end_time)
    )
    
    if provider_ids is not None:
        from app.db.models import ImportLog
        stmt = stmt.join(ImportLog, Event.import_id == ImportLog.id).where(ImportLog.provider_id.in_(provider_ids))
        
    stmt = stmt.order_by(Event.time.asc())
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    # 4. Fetch Rule Hits (identical to list view)
    repo = EventRepository(db)
    event_ids = [e.id for e in events]
    hits_map = await repo.get_rule_hits_for_events(event_ids)
    
    # 5. Conversion and injection
    out = []
    for evt in events:
        evt_out = EventOut.model_validate(evt)
        evt_out.triggered_rules = hits_map.get(evt.id, [])
        out.append(evt_out)
        
    return out
