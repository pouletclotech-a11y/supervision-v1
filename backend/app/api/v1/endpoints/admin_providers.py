from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.auth import deps
from app.db.models import MonitoringProvider, SmtpProviderRule, User, AuditLog
from app.schemas.monitoring_provider import (
    MonitoringProviderCreate, 
    MonitoringProviderUpdate, 
    MonitoringProviderSchema,
    SmtpProviderRuleSchema
)

router = APIRouter()

# --- Providers CRUD ---

@router.get("/", response_model=List[MonitoringProviderSchema])
async def get_providers(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """Get all providers with full configuration."""
    stmt = select(MonitoringProvider).where(MonitoringProvider.deleted_at.is_(None))
    if provider_ids is not None:
        stmt = stmt.where(MonitoringProvider.id.in_(provider_ids))
    stmt = stmt.order_by(MonitoringProvider.label.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=MonitoringProviderSchema)
async def create_provider(
    provider_in: MonitoringProviderCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_super_admin),
) -> Any:
    """Create a new provider."""
    # Check if code already exists
    code_upper = provider_in.code.upper()
    stmt = select(MonitoringProvider).where(MonitoringProvider.code == code_upper)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Provider code {code_upper} already exists")
    
    provider_data = provider_in.model_dump()
    provider_data['code'] = code_upper
    
    provider = MonitoringProvider(**provider_data)
    db.add(provider)
    
    audit = AuditLog(user_id=current_user.id, action="CREATE_PROVIDER", target_type="PROVIDER", payload={"code": code_upper})
    db.add(audit)
    
    await db.commit()
    await db.refresh(provider)
    return provider

@router.patch("/{provider_id}", response_model=MonitoringProviderSchema)
async def update_provider(
    provider_id: int,
    provider_in: MonitoringProviderUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    """Update a provider."""
    if provider_ids is not None and provider_id not in provider_ids:
        raise HTTPException(status_code=403, detail="Not authorized for this provider")
        
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    update_data = provider_in.model_dump(exclude_unset=True)
    audit_payload = {}
    for field, value in update_data.items():
        current_val = getattr(provider, field)
        if value != current_val:
            audit_payload[field] = {"from": current_val, "to": value}
            
        if field == "code" and value is not None:
            setattr(provider, field, value.upper())
        else:
            setattr(provider, field, value)
            
    audit = AuditLog(user_id=current_user.id, action="UPDATE_PROVIDER", target_type="PROVIDER", target_id=str(provider_id), payload=audit_payload)
    db.add(audit)
    await db.commit()
    await db.refresh(provider)
    return provider

@router.post("/{provider_id}/archive")
async def archive_provider(
    provider_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    if provider_ids is not None and provider_id not in provider_ids:
        raise HTTPException(status_code=403, detail="Not authorized for this provider")
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id, MonitoringProvider.deleted_at.is_(None))
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.is_archived = True
    audit = AuditLog(user_id=current_user.id, action="ARCHIVE_PROVIDER", target_type="PROVIDER", target_id=str(provider_id))
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": "Provider archived"}

@router.post("/{provider_id}/unarchive")
async def unarchive_provider(
    provider_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    provider_ids: Optional[list[int]] = Depends(deps.get_user_provider_ids)
) -> Any:
    if provider_ids is not None and provider_id not in provider_ids:
        raise HTTPException(status_code=403, detail="Not authorized for this provider")
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id, MonitoringProvider.deleted_at.is_(None))
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.is_archived = False
    audit = AuditLog(user_id=current_user.id, action="UNARCHIVE_PROVIDER", target_type="PROVIDER", target_id=str(provider_id))
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": "Provider unarchived"}

@router.post("/{provider_id}/restore")
async def restore_provider(
    provider_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_super_admin),
) -> Any:
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.deleted_at = None
    provider.is_archived = False
    audit = AuditLog(user_id=current_user.id, action="RESTORE_PROVIDER", target_type="PROVIDER", target_id=str(provider_id))
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": "Provider restored"}

@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_super_admin),
) -> Any:
    """Soft delete a provider (trash 30 days)."""
    stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
        
    from datetime import datetime, timezone
    provider.deleted_at = datetime.now(timezone.utc)
    # Also ensure it's not archived if deleted, to avoid state collision in UI logic
    # provider.is_archived = False 
    
    audit = AuditLog(user_id=current_user.id, action="DELETE_PROVIDER", target_type="PROVIDER", target_id=str(provider_id))
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": "Provider moved to trash (30 days)"}

# --- SMTP Rules (Whitelist & Frequency) ---

@router.get("/{provider_id}/rules", response_model=List[SmtpProviderRuleSchema])
async def get_provider_rules(
    provider_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Get all SMTP rules for a specific provider."""
    stmt = select(SmtpProviderRule).where(SmtpProviderRule.provider_id == provider_id).order_by(SmtpProviderRule.priority.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{provider_id}/rules", response_model=SmtpProviderRuleSchema)
async def create_provider_rule(
    provider_id: int,
    rule_in: SmtpProviderRuleSchema,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Add a new SMTP rule to a provider."""
    rule_data = rule_in.model_dump(exclude={'id'})
    rule_data['provider_id'] = provider_id
    
    rule = SmtpProviderRule(**rule_data)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.patch("/rules/{rule_id}", response_model=SmtpProviderRuleSchema)
async def update_rule(
    rule_id: int,
    rule_in: SmtpProviderRuleSchema,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Update an SMTP rule."""
    stmt = select(SmtpProviderRule).where(SmtpProviderRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = rule_in.model_dump(exclude_unset=True, exclude={'id'})
    for field, value in update_data.items():
        setattr(rule, field, value)
            
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Delete an SMTP rule."""
    stmt = delete(SmtpProviderRule).where(SmtpProviderRule.id == rule_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "success"}
