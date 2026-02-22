from typing import List, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.db.models import Event
from app.schemas.response_models import EventOut

router = APIRouter()

@router.get("/sample", response_model=List[EventOut])
async def debug_sample(
    limit: int = 50,
    source_file: Optional[str] = None,
    only_unmatched: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Debug endpoint to inspect normalization results.
    """
    query = select(Event).order_by(desc(Event.time)).limit(limit)
    
    if source_file:
        query = query.where(Event.source_file.ilike(f"%{source_file}%"))
        
    if only_unmatched:
        # Assuming unmatched means normalized_type is null or empty, or "GENERIC"
        query = query.where((Event.normalized_type == None) | (Event.normalized_type == ''))
        
    result = await db.execute(query)
    events = result.scalars().all()
    
    return [EventOut.model_validate(e) for e in events]

@router.get("/resolve-provider")
async def debug_resolve_provider(
    email: str = Query(..., description="Email address to resolve"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Debug endpoint to test provider resolution from email.
    """
    from app.services.provider_resolver import ProviderResolver
    from app.db.models import MonitoringProvider
    
    resolver = ProviderResolver()
    provider_id = await resolver.resolve_provider(email, db)
    
    if provider_id:
        provider = await resolver.get_provider_by_id(provider_id, db)
        return {
            "email": email,
            "matched": True,
            "provider_id": provider_id,
            "provider_code": provider.code if provider else None,
            "provider_label": provider.label if provider else None
        }
    
    return {
        "email": email,
        "matched": False,
        "provider_id": None,
        "provider_code": None,
        "provider_label": None
    }
