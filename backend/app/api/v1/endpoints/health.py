from datetime import datetime
from typing import List, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.repository import EventRepository
from pydantic import BaseModel

router = APIRouter()

class IngestionHealthRow(BaseModel):
    provider_id: int
    provider_label: str
    provider_code: str
    total_imports: int
    total_emails: int
    total_xls: int
    total_pdf: int
    total_events: int
    avg_integrity: float
    missing_pdf: int
    health_status: str # OK, WARNING, CRITICAL

class IngestionHealthSummary(BaseModel):
    date: datetime
    summary: List[IngestionHealthRow]

@router.get("/ingestion-summary", response_model=IngestionHealthSummary)
async def get_ingestion_summary(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a summary of ingestion health for today.
    """
    repo = EventRepository(db)
    today = datetime.now()
    raw_summary = await repo.get_ingestion_health_summary(today)
    
    processed_summary = []
    for row in raw_summary:
        # Business Logic for Health Status
        status = "OK"
        
        # 1. Critical cases
        if row["total_xls"] == 0 or row["total_events"] == 0:
            status = "CRITICAL"
        # 2. Warning cases
        elif row["avg_integrity"] < 95 or row["missing_pdf"] > 0:
            status = "WARNING"
            
        row["health_status"] = status
        processed_summary.append(row)
        
    # Sort by status priority: CRITICAL > WARNING > OK
    status_priority = {"CRITICAL": 0, "WARNING": 1, "OK": 2}
    processed_summary.sort(key=lambda x: status_priority.get(x["health_status"], 99))
    
    return {
        "date": today,
        "summary": processed_summary
    }
