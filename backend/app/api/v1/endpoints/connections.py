"""
Phase 3: Connections API - Stats & Drill-down for Site Connections by Provider
"""
from typing import List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import MonitoringProvider, SmtpProviderRule, SiteConnection, User
from app.auth.deps import get_current_user, get_current_operator_or_admin

router = APIRouter()


# ===== Schemas =====

class ProviderStats(BaseModel):
    code: str
    label: str
    count: int
    provider_id: int
    ui_color: Optional[str] = None

class StatsResponse(BaseModel):
    providers: List[ProviderStats]
    total: int

class SiteConnectionOut(BaseModel):
    id: int
    code_site: str
    client_name: Optional[str]
    first_seen_at: datetime
    first_import_id: Optional[int]
    provider_code: str
    provider_label: str
    
    class Config:
        from_attributes = True

class ConnectionListResponse(BaseModel):
    connections: List[SiteConnectionOut]
    total: int
    page: int
    limit: int

class GrowthItem(BaseModel):
    period: str  # YYYY-MM or YYYY
    provider_code: str
    count: int

class GrowthResponse(BaseModel):
    items: List[GrowthItem]

class SmtpRuleOut(BaseModel):
    id: int
    match_type: str
    match_value: str
    priority: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class SmtpRuleCreate(BaseModel):
    match_type: str  # EXACT, DOMAIN, REGEX
    match_value: str
    priority: int = 0
    is_active: bool = True

class SmtpRuleUpdate(BaseModel):
    match_type: Optional[str] = None
    match_value: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

from app.schemas.monitoring_provider import MonitoringProviderCreate, MonitoringProviderUpdate, ProviderHealthStatus

# Local legacy schemas (kept for ref but moving to centralized ones)
class ProviderOut(BaseModel):
    id: int
    code: str
    label: str
    ui_color: Optional[str] = None
    is_active: bool
    # Monitoring fields
    recovery_email: Optional[str] = None
    expected_emails_per_day: int = 0
    expected_frequency_type: str = "daily"
    silence_threshold_minutes: int = 1440
    monitoring_enabled: bool = False
    
    class Config:
        from_attributes = True

# We can remove ProviderCreate/Update if we use the central ones


# ===== Endpoints =====

@router.get("/stats", response_model=StatsResponse)
async def get_connection_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get total distinct site connections per provider."""
    stmt = (
        select(
            MonitoringProvider.id,
            MonitoringProvider.code,
            MonitoringProvider.label,
            MonitoringProvider.ui_color,
            func.count(SiteConnection.id).label('count')
        )
        .outerjoin(SiteConnection, SiteConnection.provider_id == MonitoringProvider.id)
        .where(MonitoringProvider.is_active == True)
        .group_by(MonitoringProvider.id, MonitoringProvider.code, MonitoringProvider.label, MonitoringProvider.ui_color)
        .order_by(MonitoringProvider.code)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    providers = [
        ProviderStats(
            provider_id=r.id,
            code=r.code,
            label=r.label,
            ui_color=r.ui_color,
            count=r.count or 0
        )
        for r in rows
    ]
    total = sum(p.count for p in providers)
    
    return StatsResponse(providers=providers, total=total)


@router.get("/list", response_model=ConnectionListResponse)
async def list_connections(
    provider_code: Optional[str] = Query(None, description="Filter by provider code"),
    search: Optional[str] = Query(None, description="Search code_site or client_name"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    sort_by: str = Query("client_name", description="Sort field: client_name or code_site"),
    sort_order: str = Query("asc", description="Sort direction: asc or desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """List site connections with filters, pagination and sorting (server-side)."""
    base_stmt = (
        select(SiteConnection, MonitoringProvider)
        .join(MonitoringProvider, MonitoringProvider.id == SiteConnection.provider_id)
    )

    if provider_code:
        base_stmt = base_stmt.where(MonitoringProvider.code == provider_code)

    if search:
        search_pattern = f"%{search}%"
        base_stmt = base_stmt.where(
            (SiteConnection.code_site.ilike(search_pattern)) |
            (SiteConnection.client_name.ilike(search_pattern))
        )

    # Count total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Resolve sort column
    sort_col_map = {
        "client_name": SiteConnection.client_name,
        "code_site": SiteConnection.code_site,
        "first_seen_at": SiteConnection.first_seen_at,
        "total_events": SiteConnection.total_events,
    }
    sort_col = sort_col_map.get(sort_by, SiteConnection.client_name)
    order_expr = sort_col.asc() if sort_order.lower() == "asc" else sort_col.desc()

    # Secondary sort always stable
    secondary = SiteConnection.code_site.asc()

    skip = (page - 1) * limit
    stmt = base_stmt.order_by(order_expr, secondary).offset(skip).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    connections = [
        SiteConnectionOut(
            id=sc.id,
            code_site=sc.code_site,
            client_name=sc.client_name,
            first_seen_at=sc.first_seen_at,
            first_import_id=sc.first_import_id,
            provider_code=mp.code,
            provider_label=mp.label
        )
        for sc, mp in rows
    ]

    return ConnectionListResponse(connections=connections, total=total, page=page, limit=limit)


@router.get("/growth", response_model=GrowthResponse)
async def get_connection_growth(
    granularity: str = Query("month", description="month or year"),
    provider_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get new connections growth by month or year."""
    if granularity == "month":
        period_expr = func.to_char(SiteConnection.first_seen_at, 'YYYY-MM')
    else:
        period_expr = func.to_char(SiteConnection.first_seen_at, 'YYYY')
    
    stmt = (
        select(
            period_expr.label('period'),
            MonitoringProvider.code.label('provider_code'),
            func.count(SiteConnection.id).label('count')
        )
        .join(MonitoringProvider, MonitoringProvider.id == SiteConnection.provider_id)
        .group_by(period_expr, MonitoringProvider.code)
        .order_by(period_expr.desc(), MonitoringProvider.code)
    )
    
    if provider_code:
        stmt = stmt.where(MonitoringProvider.code == provider_code)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    items = [
        GrowthItem(period=r.period, provider_code=r.provider_code, count=r.count)
        for r in rows
    ]
    
    return GrowthResponse(items=items)


# ===== Providers Management =====

@router.get("/providers", response_model=List[ProviderOut])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """List all monitoring providers."""
    stmt = select(MonitoringProvider).order_by(MonitoringProvider.code)
    result = await db.execute(stmt)
    providers = result.scalars().all()
    return [ProviderOut.model_validate(p) for p in providers]


@router.post("/providers", response_model=ProviderOut)
async def create_provider(
    provider_in: MonitoringProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """Create a new monitoring provider. ADMIN/OPERATOR only."""
    # Check if code already exists
    code_upper = provider_in.code.upper()
    existing_stmt = select(MonitoringProvider).where(MonitoringProvider.code == code_upper)
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Provider code {code_upper} already exists")
    
    # Use model_dump to get all fields including defaults from MonitoringProviderCreate
    provider_data = provider_in.model_dump()
    provider_data['code'] = code_upper
    
    provider = MonitoringProvider(**provider_data)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return ProviderOut.model_validate(provider)


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: int,
    provider_in: MonitoringProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """Update a monitoring provider. ADMIN/OPERATOR only."""
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Update only provided fields
    update_data = provider_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "code" and value is not None:
            setattr(provider, field, value.upper())
        else:
            setattr(provider, field, value)
        
    await db.commit()
    await db.refresh(provider)
    return ProviderOut.model_validate(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete a monitoring provider. ADMIN only."""
    # Strict RBAC: only check ADMIN role here
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can delete providers")
        
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
        
    await db.delete(provider)
    await db.commit()
    return {"status": "deleted", "provider_id": provider_id}


@router.get("/providers/{provider_id}/rules", response_model=List[SmtpRuleOut])
async def get_provider_rules(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get SMTP rules for a provider."""
    stmt = (
        select(SmtpProviderRule)
        .where(SmtpProviderRule.provider_id == provider_id)
        .order_by(SmtpProviderRule.priority.desc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [SmtpRuleOut.model_validate(r) for r in rules]


@router.post("/providers/{provider_id}/rules", response_model=SmtpRuleOut)
async def create_provider_rule(
    provider_id: int,
    rule_in: SmtpRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """Create a new SMTP rule for a provider. ADMIN/OPERATOR only."""
    # Validate provider exists
    provider_stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
    provider_result = await db.execute(provider_stmt)
    if not provider_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Validate match_type
    allowed_types = ["EXACT", "DOMAIN", "REGEX"]
    match_type = rule_in.match_type.upper()
    if match_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid match_type. Allowed: {allowed_types}")

    rule = SmtpProviderRule(
        provider_id=provider_id,
        match_type=match_type,
        match_value=rule_in.match_value,
        priority=rule_in.priority,
        is_active=rule_in.is_active
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return SmtpRuleOut.model_validate(rule)


@router.patch("/providers/{provider_id}/rules/{rule_id}", response_model=SmtpRuleOut)
async def update_provider_rule(
    provider_id: int,
    rule_id: int,
    rule_in: SmtpRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator_or_admin)
) -> Any:
    """Update an SMTP rule. ADMIN/OPERATOR only."""
    stmt = select(SmtpProviderRule).where(
        SmtpProviderRule.id == rule_id,
        SmtpProviderRule.provider_id == provider_id
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    if rule_in.match_type is not None:
        allowed_types = ["EXACT", "DOMAIN", "REGEX"]
        match_type = rule_in.match_type.upper()
        if match_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid match_type. Allowed: {allowed_types}")
        rule.match_type = match_type
        
    if rule_in.match_value is not None:
        rule.match_value = rule_in.match_value
    if rule_in.priority is not None:
        rule.priority = rule_in.priority
    if rule_in.is_active is not None:
        rule.is_active = rule_in.is_active
        
    await db.commit()
    await db.refresh(rule)
    return SmtpRuleOut.model_validate(rule)


@router.delete("/providers/{provider_id}/rules/{rule_id}")
async def delete_provider_rule(
    provider_id: int,
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete an SMTP rule. ADMIN only."""
    # Strict RBAC: only check ADMIN role here
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can delete rules")
        
    stmt = select(SmtpProviderRule).where(
        SmtpProviderRule.id == rule_id,
        SmtpProviderRule.provider_id == provider_id
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "rule_id": rule_id}
