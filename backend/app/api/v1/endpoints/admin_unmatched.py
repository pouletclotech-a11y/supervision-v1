from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import deps
from app.db.models import User, ImportLog
from app.services.repository import AdminRepository
from app.schemas.admin import UnmatchedImportOut

router = APIRouter()

@router.get("", response_model=List[UnmatchedImportOut])
async def read_unmatched(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = Query(None, description="Filter by specific error status"),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Retrieve unmatched imports or imports with ingestion failures.
    Incs: PROFILE_NOT_CONFIDENT, NO_PROFILE_MATCH, PARSER_FAILED, VALIDATION_REJECTED, ERROR.
    """
    repo = AdminRepository(db)
    imports = await repo.get_unmatched_imports(skip=skip, limit=limit, status=status)
    return imports

@router.get("/{import_id}", response_model=UnmatchedImportOut)
async def read_unmatched_detail(
    import_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get details of a specific failed import.
    """
    from sqlalchemy import select
    stmt = select(ImportLog).where(ImportLog.id == import_id)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Import not found")
    return obj
