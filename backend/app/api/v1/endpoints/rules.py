from datetime import datetime, date
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
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
    health_status: str # HIGH_ACTIVITY, LOW_ACTIVITY, NORMAL

class RuleTriggerSummary(BaseModel):
    date: date
    summary: List[RuleTriggerRow]

@router.get("/trigger-summary", response_model=RuleTriggerSummary)
async def get_rule_trigger_summary(
    target_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a summary of rule triggers for a specific date.
    """
    repo = EventRepository(db)
    # Convert date to datetime for repository
    dt = datetime.combine(target_date, datetime.min.time())
    
    raw_summary = await repo.get_rule_trigger_summary(dt)
    
    # Récupération des seuils depuis la table settings ou config
    from app.core.config_loader import app_config
    
    high_threshold = app_config.get('monitoring', {}).get('RULE_MONITORING_HIGH_THRESHOLD', 100)
    low_threshold = app_config.get('monitoring', {}).get('RULE_MONITORING_LOW_THRESHOLD', 1)
    
    processed_summary = []
    for row in raw_summary:
        status = "NORMAL"
        if row["total_triggers"] > high_threshold:
            status = "HIGH_ACTIVITY"
        elif row["total_triggers"] < low_threshold:
            status = "LOW_ACTIVITY"
            
        row["health_status"] = status
        processed_summary.append(row)
        
    # Tri par triggers desc
    processed_summary.sort(key=lambda x: x["total_triggers"], reverse=True)
    
    return {
        "date": target_date,
        "summary": processed_summary
    }
