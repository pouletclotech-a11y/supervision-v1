from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import deps
from app.db.models import User, ImportLog, ReprocessJob
from app.services.repository import AdminRepository
from app.schemas.admin import ReprocessJobOut
from app.db.session import AsyncSessionLocal

router = APIRouter()

@router.get("/jobs", response_model=List[ReprocessJobOut])
async def list_reprocess_jobs(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    from sqlalchemy import select
    stmt = select(ReprocessJob).order_by(ReprocessJob.started_at.desc()).limit(50)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/import/{import_id}", response_model=ReprocessJobOut)
async def reprocess_import(
    import_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Reprocess a specific import by clearing its data and setting it back to PENDING.
    """
    repo = AdminRepository(db)
    
    # 1. Check if import exists
    from sqlalchemy import select
    stmt = select(ImportLog).where(ImportLog.id == import_id)
    result = await db.execute(stmt)
    import_log = result.scalar_one_or_none()
    if not import_log:
        raise HTTPException(status_code=404, detail="Import not found")

    # 2. Create Audit Log
    audit = await repo.create_audit_log(
        user_id=current_user.id,
        action="REPROCESS_IMPORT",
        target_type="IMPORT",
        target_id=str(import_id),
        payload={"filename": import_log.filename}
    )
    
    # 3. Create Reprocess Job
    job = await repo.create_reprocess_job(
        scope={"import_id": import_id, "filename": import_log.filename},
        audit_log_id=audit.id
    )
    
    # 4. Background task to purge and reset
    background_tasks.add_task(run_reprocess_import_task, job.id, import_id)
    
    await db.commit()
    await db.refresh(job)
    return job

async def run_reprocess_import_task(job_id: int, import_id: int):
    """
    Background logic for reprocessing.
    Uses its own session to avoid closing issues.
    """
    async with AsyncSessionLocal() as db:
        repo = AdminRepository(db)
        try:
            await repo.update_reprocess_job(job_id, "RUNNING")
            await db.commit()
            
            await repo.delete_import_data(import_id)
            await db.commit()
            
            await repo.update_reprocess_job(job_id, "SUCCESS")
            await db.commit()
            # The worker will pick it up automatically because status is now PENDING
        except Exception as e:
            await db.rollback()
            await repo.update_reprocess_job(job_id, "FAILED", error_message=str(e))
            await db.commit()
