import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.db.models import AlertRule, Event, ReplayJob, User, RuleCondition
from app.schemas.response_models import AlertRuleOut, AlertRuleCreate, AlertRuleUpdate
from app.services.alerting import AlertingService
from app.services.repository import EventRepository
from app.auth.deps import get_current_operator_or_admin

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/active", response_model=List[Any]) # Use Any or AlertOut if imported
async def get_active_alerts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """Get currently active alerts."""
    repo = EventRepository(db)
    return await repo.get_active_alerts(skip=skip, limit=limit)

@router.get("/archived", response_model=List[Any])
async def get_archived_alerts(
    days: int = 7,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """Get archived alerts for the last N days."""
    repo = EventRepository(db)
    return await repo.get_archived_alerts(days=days, skip=skip, limit=limit)


@router.get("/rules", response_model=List[AlertRuleOut])
async def read_alert_rules(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Retrieve alert rules.
    """
    stmt = select(AlertRule).order_by(AlertRule.id.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
    
@router.get("/conditions", response_model=List[dict])
async def read_rule_conditions(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Retrieve rule conditions library.
    """
    stmt = select(RuleCondition).where(RuleCondition.is_active == True)
    result = await db.execute(stmt)
    conditions = result.scalars().all()
    return [{"code": c.code, "label": c.label, "type": c.type, "payload": c.payload} for c in conditions]

@router.post("/rules", response_model=AlertRuleOut)
async def create_alert_rule(
    rule_in: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """
    Create a new alert rule.
    """
    rule = AlertRule(
        name=rule_in.name,
        condition_type=rule_in.condition_type,
        value=rule_in.value,
        scope_site_code=rule_in.scope_site_code,
        
        # V3 / Sliding Window
        frequency_count=rule_in.frequency_count,
        frequency_window=rule_in.frequency_window,
        sliding_window_days=rule_in.sliding_window_days,
        is_open_only=rule_in.is_open_only,
        
        # Sequences
        sequence_enabled=rule_in.sequence_enabled,
        seq_a_category=rule_in.seq_a_category,
        seq_a_keyword=rule_in.seq_a_keyword,
        seq_b_category=rule_in.seq_b_category,
        seq_b_keyword=rule_in.seq_b_keyword,
        seq_max_delay_seconds=rule_in.seq_max_delay_seconds,
        seq_lookback_days=rule_in.seq_lookback_days,
        
        # Logic
        logic_enabled=rule_in.logic_enabled,
        logic_tree=rule_in.logic_tree,
        
        # Filters
        match_category=rule_in.match_category,
        match_keyword=rule_in.match_keyword,

        schedule_start=rule_in.schedule_start,
        schedule_end=rule_in.schedule_end,
        time_scope=rule_in.time_scope.value if rule_in.time_scope else "NONE",
        email_notify=rule_in.email_notify,
        is_active=rule_in.is_active
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/rules/{id}", response_model=AlertRuleOut)
async def delete_alert_rule(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """
    Delete an alert rule.
    """
    stmt = select(AlertRule).where(AlertRule.id == id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    await db.delete(rule)
    await db.commit()
    return rule

@router.put("/rules/{id}", response_model=AlertRuleOut)
async def update_alert_rule(
    id: int,
    rule_in: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """
    Update an alert rule.
    """
    stmt = select(AlertRule).where(AlertRule.id == id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Update fields
    rule.name = rule_in.name
    rule.condition_type = rule_in.condition_type
    rule.value = rule_in.value
    rule.scope_site_code = rule_in.scope_site_code
    
    rule.frequency_count = rule_in.frequency_count
    rule.frequency_window = rule_in.frequency_window
    rule.sliding_window_days = rule_in.sliding_window_days
    rule.is_open_only = rule_in.is_open_only
    
    rule.sequence_enabled = rule_in.sequence_enabled
    rule.seq_a_category = rule_in.seq_a_category
    rule.seq_a_keyword = rule_in.seq_a_keyword
    rule.seq_b_category = rule_in.seq_b_category
    rule.seq_b_keyword = rule_in.seq_b_keyword
    rule.seq_max_delay_seconds = rule_in.seq_max_delay_seconds
    rule.seq_lookback_days = rule_in.seq_lookback_days
    
    rule.logic_enabled = rule_in.logic_enabled
    rule.logic_tree = rule_in.logic_tree
    
    rule.match_category = rule_in.match_category
    rule.match_keyword = rule_in.match_keyword
    
    rule.schedule_start = rule_in.schedule_start
    rule.schedule_end = rule_in.schedule_end
    rule.time_scope = rule_in.time_scope.value if rule_in.time_scope else "NONE"
    rule.email_notify = rule_in.email_notify
    rule.is_active = rule_in.is_active
    
    await db.commit()
    await db.refresh(rule)
    return rule

@router.patch("/rules/{id}", response_model=AlertRuleOut)
async def patch_alert_rule(
    id: int,
    rule_in: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """
    Partially update an alert rule.
    """
    stmt = select(AlertRule).where(AlertRule.id == id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = rule_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    await db.commit()
    await db.refresh(rule)
    return rule

@router.post("/rules/{id}/dry-run")
async def dry_run_alert_rule(
    id: int,
    import_id: Optional[int] = None,
    reference_time_override: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """
    Test a rule definition against real events with time override.
    """
    stmt_rule = select(AlertRule).where(AlertRule.id == id)
    res_rule = await db.execute(stmt_rule)
    rule = res_rule.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Fetch events to test against
    stmt_events = select(Event).order_by(Event.time.desc())
    if import_id:
        stmt_events = stmt_events.where(Event.import_id == import_id)
    stmt_events = stmt_events.limit(limit)
    
    res_events = await db.execute(stmt_events)
    events = res_events.scalars().all()
    
    service = AlertingService()
    repo = EventRepository(db)
    
    results = []
    matched_count = 0
    
    for evt in events:
        res = await service.evaluate_rule(
            evt, rule, repo=repo, 
            reference_time_override=reference_time_override
        )
        if res["triggered"]:
            matched_count += 1
            results.append({
                "event_id": evt.id,
                "event_time": evt.time.isoformat(),
                "site_code": evt.site_code,
                "triggered": True,
                "explanations": res["details"] or ["Matched all criteria"]
            })
        elif len(results) < 5: # Sample non-matches too or just first hits
             # Filter details to only show relevant failures
             results.append({
                "event_id": evt.id,
                "event_time": evt.time.isoformat(),
                "triggered": False,
                "explanations": res["details"]
            })

    return {
        "rule_name": rule.name,
        "evaluated_count": len(events),
        "matched_count": matched_count,
        "results": results[:20] # Limit response size
    }

@router.post("/rules/test")
async def test_alert_rule(
    rule: AlertRuleCreate,
    sample_text: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy rule tester (simple string match).
    """
    from app.ingestion.models import NormalizedEvent
    from datetime import datetime
    
    event = NormalizedEvent(
        timestamp=datetime.now(),
        site_code=rule.scope_site_code or "TEST-SITE",
        event_type="TEST",
        raw_message=sample_text,
        status="INFO",
        source_file="TEST_INPUT"
    )
    
    service = AlertingService()
    res = await service.evaluate_rule(event, rule)
    
    return {
        "matched": res["triggered"],
        "rule_name": rule.name,
        "sample_analyzed": sample_text,
        "detected_site": event.site_code,
        "details": res["details"]
    }


async def reprocess_alerts_task(db: AsyncSession, job_id: int):
    """
    Background task to replay all events against active rules.
    """
    from datetime import datetime
    
    # 0. Fetch Job
    stmt_job = select(ReplayJob).where(ReplayJob.id == job_id)
    res_job = await db.execute(stmt_job)
    job = res_job.scalar_one_or_none()
    if not job: return

    # 1. Fetch Active Rules
    repo = EventRepository(db)
    active_rules = await repo.get_active_rules()
    
    if not active_rules:
        job.status = 'SUCCESS'
        job.ended_at = datetime.utcnow()
        await db.commit()
        return
        
    alerting_service = AlertingService()
    
    # 2. Iterate ALL events (Batch Processing)
    batch_size = 1000
    last_id = 0
    total_processed = 0
    alerts_triggered = 0
    
    try:
        while True:
            # Fetch batch
            stmt = (
                select(Event)
                .where(Event.id > last_id)
                .order_by(Event.id.asc())
                .limit(batch_size)
            )
            result = await db.execute(stmt)
            events = result.scalars().all()
            
            if not events:
                break
                
            from app.ingestion.models import NormalizedEvent
            from app.db.models import EventRuleHit
            
            # Phase 2.0: Strategy REPLACE - Clear previous hits for these events
            event_ids = [e.id for e in events]
            await db.execute(
                delete(EventRuleHit).where(EventRuleHit.event_id.in_(event_ids))
            )
            
            batch_updates = 0
            for db_event in events:
                last_id = db_event.id
                
                simulated_event = NormalizedEvent(
                    timestamp=db_event.time,
                    site_code=db_event.site_code or "REPLAY",
                    event_type=db_event.normalized_type or 'UNKNOWN',
                    raw_message=db_event.raw_message,
                    status=db_event.severity or 'INFO',
                    source_file=db_event.source_file or "REPLAY"
                )
                # Phase 1: Ensure hit recording can find the event ID
                simulated_event.id = db_event.id
                
                # Check alerts
                await alerting_service.check_and_trigger_alerts(simulated_event, active_rules, repo=repo)
                
                # If modified to CRITICAL, update DB
                if simulated_event.status == 'CRITICAL' and db_event.severity != 'CRITICAL':
                    db_event.severity = 'CRITICAL'
                    batch_updates += 1
                    alerts_triggered += 1
                    
            # Commit batch & Update Job
            total_processed += len(events)
            job.events_scanned = total_processed
            job.alerts_created = alerts_triggered
            await db.commit()
            
            print(f"Replay Task: Job {job_id} | Processed {total_processed}. Alerts: {alerts_triggered}")
            
        job.status = 'SUCCESS'
        job.ended_at = datetime.utcnow()
        await db.commit()
        
    except Exception as e:
        logger.error(f"Replay Job {job_id} failed: {e}")
        job.status = 'ERROR'
        job.error_message = str(e)
        job.ended_at = datetime.utcnow()
        await db.commit()

@router.post("/replay")
async def replay_alerts(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Trigger a background replay of all historical events against current rules.
    """
    job = ReplayJob(status='RUNNING')
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    background_tasks.add_task(run_replay_safe, job.id)
    return {"message": "Replay started", "job_id": job.id}

async def run_replay_safe(job_id: int):
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await reprocess_alerts_task(session, job_id)
