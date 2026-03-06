from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from typing import Any, Optional
import shutil
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import deps
from app.db.models import User
from app.schemas.config_schema import ConfigExportSchema, ImportSummarySchema
from app.services.config_sync_service import ConfigSyncService
from app.services.preview_parse_service import PreviewParseService

router = APIRouter()

@router.get("/export", response_model=ConfigExportSchema)
async def export_config(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Export all providers and profiles config.
    Restricted to Admin.
    """
    service = ConfigSyncService(db)
    return await service.export_config()

@router.post("/import", response_model=ImportSummarySchema)
async def import_config(
    config: ConfigExportSchema,
    dry_run: bool = Query(True),
    mode: str = Query("merge", regex="^(merge|replace)$"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Import providers and profiles config.
    Supports dry_run and merge/replace modes.
    Restricted to Admin.
    """
    service = ConfigSyncService(db)
    summary = await service.import_config(
        config=config,
        dry_run=dry_run,
        mode=mode,
        user_id=current_user.id
    )
    
    if summary.errors:
        raise HTTPException(status_code=400, detail=f"Import failed: {summary.errors}")
        
    return summary

@router.post("/onboarding/preview")
async def onboarding_preview(
    file: UploadFile = File(...),
    provider_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Preview an onboarding file.
    Uploads to /tmp, parses in-memory, returns metrics.
    """
    temp_dir = Path("/tmp/onboarding_previews")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename
    
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        service = PreviewParseService()
        result = await service.preview_file(db, temp_path, provider_code=provider_code)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
            
        return result
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@router.post("/onboarding/finalize")
async def onboarding_finalize(
    config: dict,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Finalize onboarding: Create/Update provider and profile.
    """
    from app.db.models import MonitoringProvider, DBIngestionProfile
    
    provider_data = config.get("provider", {})
    profile_data = config.get("profile", {})
    
    if not provider_data.get("code"):
        raise HTTPException(status_code=400, detail="Provider code is required")
    
    # 1. Ensure Provider
    stmt = select(MonitoringProvider).where(MonitoringProvider.code == provider_data.get("code"))
    res = await db.execute(stmt)
    prov = res.scalar_one_or_none()
    
    if not prov:
        prov = MonitoringProvider(**provider_data)
        db.add(prov)
        await db.flush()
    else:
        # Update existing
        for k, v in provider_data.items():
            setattr(prov, k, v)
    
    # 2. Ensure Profile
    profile_id = profile_data.get("profile_id")
    if profile_id:
        stmt_prof = select(DBIngestionProfile).where(DBIngestionProfile.profile_id == profile_id)
        res_prof = await db.execute(stmt_prof)
        existing_prof = res_prof.scalar_one_or_none()
        
        if not existing_prof:
            profile_data["provider_code"] = prov.code
            new_prof = DBIngestionProfile(**profile_data)
            db.add(new_prof)
        else:
             for k, v in profile_data.items():
                setattr(existing_prof, k, v)
    
    await db.commit()
    return {"status": "success", "provider_id": prov.id}
