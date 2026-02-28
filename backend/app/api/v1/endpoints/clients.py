import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.schemas.response_models import ClientReportOut
from app.services.repository import EventRepository
from app.auth.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{site_code}/report", response_model=ClientReportOut)
async def get_client_report(
    site_code: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get a consolidated chronological report for a specific client.
    """
    repo = EventRepository(db)
    report = await repo.get_client_report(site_code=site_code, days=days)
    
    if not report:
        raise HTTPException(status_code=404, detail=f"Site {site_code} not found or no events recorded.")
        
    return report
