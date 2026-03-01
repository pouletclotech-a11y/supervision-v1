from datetime import datetime, date
from typing import List, Any, Optional, Dict
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import AlertRule
from app.services.repository import EventRepository
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter()


class RuleTriggerRow(BaseModel):
    rule_id: int
    rule_name: str
    provider_id: Optional[int]
    provider_label: str
    total_triggers: int
    distinct_sites: int
    last_trigger_at: datetime
    health_status: str  # HIGH_ACTIVITY, LOW_ACTIVITY, NORMAL


class RuleTriggerSummary(BaseModel):
    date: date
    summary: List[RuleTriggerRow]


class ReplayResult(BaseModel):
    status: str
    events_processed: int
    hits_before: int
    hits_after: int
    delta: int


class ActiveRuleOut(BaseModel):
    id: int
    name: str
    condition_type: str
    value: str
    is_active: bool
    logic_enabled: bool
    logic_tree: Optional[Dict] = None

    class Config:
        from_attributes = True


@router.get("/trigger-summary", response_model=RuleTriggerSummary)
async def get_rule_trigger_summary(
    target_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a summary of rule triggers for a specific date.
    """
    repo = EventRepository(db)
    dt = datetime.combine(target_date, datetime.min.time())

    raw_summary = await repo.get_rule_trigger_summary(dt)

    from app.core.config_loader import app_config
    rules_cfg = app_config.get('monitoring', {}).get('rules', {})
    high_threshold = rules_cfg.get('RULE_MONITORING_HIGH_THRESHOLD', 100)
    low_threshold = rules_cfg.get('RULE_MONITORING_LOW_THRESHOLD', 1)

    processed_summary = []
    for row in raw_summary:
        status = "NORMAL"
        if row["total_triggers"] > high_threshold:
            status = "HIGH_ACTIVITY"
        elif row["total_triggers"] < low_threshold:
            status = "LOW_ACTIVITY"

        row["health_status"] = status
        processed_summary.append(row)

    processed_summary.sort(key=lambda x: x["total_triggers"], reverse=True)

    return {
        "date": target_date,
        "summary": processed_summary
    }


@router.get("/active", response_model=List[ActiveRuleOut])
async def list_active_rules(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """List all currently active alert rules."""
    result = await db.execute(
        select(AlertRule).where(AlertRule.is_active == True).order_by(AlertRule.id)
    )
    return list(result.scalars().all())


class ReplayRequest(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    mode: str = "REPLACE" # "REPLACE" or "FULL"
    force: bool = False


@router.post("/replay-all", response_model=ReplayResult)
async def replay_all_rules(
    req: ReplayRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Phase 2A Hotfix: Replay business rules safely.
    - Mode REPLACE (default): Atomic per batch.
    - Mode FULL: Requires setting replay_allow_full_clear=True AND force=True.
    """
    from app.services.business_rules import replay_all_rules as _replay
    
    if req.mode.upper() == "FULL" and not req.force:
        raise HTTPException(
            status_code=400, 
            detail="FULL mode requires force=true and specific DB setting enabled."
        )

    try:
        stats = await _replay(
            db, 
            date_from=req.date_from, 
            date_to=req.date_to, 
            mode=req.mode, 
            force_full=req.force
        )
        return ReplayResult(
            status="OK",
            events_processed=stats["events_processed"],
            hits_before=stats["hits_before"],
            hits_after=stats["hits_after"],
            delta=stats["delta"],
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[API_REPLAY_ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Replay failed: {str(e)}")
