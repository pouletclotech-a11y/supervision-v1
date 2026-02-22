from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.auth import deps
from app.db.models import User, DBIngestionProfile, ProfileRevision
from app.services.repository import AdminRepository
from app.schemas.ingestion_profile import IngestionProfile as ProfileSchema
from app.schemas.admin import ProfileRevisionOut

router = APIRouter()

@router.get("", response_model=List[ProfileSchema])
async def list_profiles(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    List all ingestion profiles in the database.
    """
    stmt = select(DBIngestionProfile).order_by(DBIngestionProfile.priority.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{profile_id_pk}", response_model=ProfileSchema)
async def get_profile(
    profile_id_pk: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    stmt = select(DBIngestionProfile).where(DBIngestionProfile.id == profile_id_pk)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Profile not found")
    return obj

@router.post("", response_model=ProfileSchema)
async def create_profile(
    *,
    db: AsyncSession = Depends(deps.get_db),
    profile_in: ProfileSchema,
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Create a new ingestion profile with version 1 and audit log.
    """
    repo = AdminRepository(db)
    
    # Check duplicate
    stmt = select(DBIngestionProfile).where(DBIngestionProfile.profile_id == profile_in.profile_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Profile ID already exists")

    # Exclude technical fields from initial commit
    data = profile_in.model_dump(exclude={"updated_at", "version_number", "version"})
    db_obj = DBIngestionProfile(
        **data,
        version_number=1
    )
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)

    # Audit & Revision
    await repo.create_audit_log(
        user_id=current_user.id,
        action="CREATE_PROFILE",
        target_type="PROFILE",
        target_id=db_obj.profile_id,
        payload=profile_in.model_dump(mode="json")
    )
    await repo.create_profile_revision(
        profile_id=db_obj.id,
        version=1,
        data=profile_in.model_dump(mode="json"),
        user_id=current_user.id,
        reason="Initial creation"
    )
    
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

@router.patch("/{profile_id_pk}", response_model=ProfileSchema)
async def update_profile(
    *,
    db: AsyncSession = Depends(deps.get_db),
    profile_id_pk: int,
    profile_in: ProfileSchema,
    change_reason: str = Body(None),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Update a profile, increment version and track revision.
    """
    repo = AdminRepository(db)
    stmt = select(DBIngestionProfile).where(DBIngestionProfile.id == profile_id_pk)
    result = await db.execute(stmt)
    db_obj = result.scalar_one_or_none()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Increment version
    new_version = db_obj.version_number + 1
    
    update_data = profile_in.model_dump(exclude_unset=True, exclude={"version_number", "version", "updated_at", "id"})
    for field, value in update_data.items():
        if hasattr(db_obj, field):
            setattr(db_obj, field, value)
    
    db_obj.version_number = new_version
    db.add(db_obj)
    
    # Audit & Revision
    await repo.create_audit_log(
        user_id=current_user.id,
        action="UPDATE_PROFILE",
        target_type="PROFILE",
        target_id=db_obj.profile_id,
        payload={"update": update_data, "reason": change_reason}
    )
    await repo.create_profile_revision(
        profile_id=db_obj.id,
        version=new_version,
        data=profile_in.model_dump(mode="json"),
        user_id=current_user.id,
        reason=change_reason
    )
    
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

@router.get("/{profile_id_pk}/revisions", response_model=List[ProfileRevisionOut])
async def get_profile_revisions(
    profile_id_pk: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    stmt = select(ProfileRevision).where(ProfileRevision.profile_id == profile_id_pk).order_by(ProfileRevision.version_number.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
