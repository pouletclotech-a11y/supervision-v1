from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.auth import deps
from app.db.models import SiteConnection, MonitoringProvider, SmtpProviderRule, User
from app.services.repository import EventRepository, AdminRepository
from app.schemas.monitoring_provider import MonitoringProviderUpdate, ProviderHealthStatus

router = APIRouter()

@router.get("/summary")
async def get_business_summary(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get summary of site connections per provider.
    """
    repo = EventRepository(db)
    summary = await repo.get_business_summary()
    
    return [
        {
            "provider_label": s.label,
            "provider_code": s.code,
            "total_sites": s.total_sites or 0,
            "total_events": int(s.total_events) if s.total_events else 0
        }
        for s in summary
    ]

@router.get("/timeseries")
async def get_business_timeseries(
    granularity: str = Query("month", regex="^(month|year)$"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get new site connections over time.
    """
    # PostgreSQL date_trunc for granularity
    stmt = (
        select(
            func.date_trunc(granularity, SiteConnection.first_seen_at).label("period"),
            func.count(SiteConnection.id).label("new_sites")
        )
        .group_by("period")
        .order_by("period")
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    return [
        {
            "period": r.period.isoformat(),
            "new_sites": r.new_sites
        }
        for r in rows
    ]

@router.get("/sites")
async def get_business_sites(
    provider_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Paginated list of site connections for drilldown.
    """
    stmt = select(SiteConnection, MonitoringProvider.label.label("provider_label"))\
        .join(MonitoringProvider, SiteConnection.provider_id == MonitoringProvider.id)
    
    if provider_id:
        stmt = stmt.where(SiteConnection.provider_id == provider_id)
    
    stmt = stmt.order_by(SiteConnection.last_seen_at.desc())\
        .offset((page - 1) * size)\
        .limit(size)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Total for pagination
    count_stmt = select(func.count(SiteConnection.id))
    if provider_id:
        count_stmt = count_stmt.where(SiteConnection.provider_id == provider_id)
    total = await db.scalar(count_stmt)
    
    return {
        "items": [
            {
                "id": r.SiteConnection.id,
                "code_site": r.SiteConnection.code_site,
                "client_name": r.SiteConnection.client_name,
                "provider_label": r.provider_label,
                "first_seen_at": r.SiteConnection.first_seen_at.isoformat(),
                "last_seen_at": r.SiteConnection.last_seen_at.isoformat(),
                "total_events": r.SiteConnection.total_events
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "size": size
    }

@router.get("/smtp-rules")
async def get_smtp_rules(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    stmt = select(SmtpProviderRule).order_by(SmtpProviderRule.priority.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/providers/health", response_model=List[ProviderHealthStatus])
async def get_providers_health(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get health status for all monitoring providers.
    """
    repo = AdminRepository(db)
    return await repo.get_providers_health()

@router.patch("/providers/{provider_id}/monitoring")
async def update_provider_monitoring(
    provider_id: int,
    data: MonitoringProviderUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Update monitoring configuration for a specific provider.
    """
    repo = AdminRepository(db)
    provider = await repo.update_provider_monitoring(provider_id, data.model_dump(exclude_unset=True))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    await db.commit()
    return {"status": "success"}

@router.get("/providers")
async def get_all_providers(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get all providers with full monitoring configuration.
    """
    stmt = select(MonitoringProvider).order_by(MonitoringProvider.label.asc())
    result = await db.execute(stmt)
    return result.scalars().all()
