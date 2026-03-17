from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile
import os
import shutil
from datetime import datetime
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import deps
from app.auth import security
from app.db.models import User, UserProvider, AuditLog
from sqlalchemy import delete
from app.schemas.user import UserCreate, UserUpdate, UserOut

router = APIRouter()

# -----------------------------------------------------------------------------
# GET /me
# -----------------------------------------------------------------------------
@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get current user with providers if applicable.
    """
    if current_user.role != "SUPER_ADMIN":
        stmt = select(UserProvider.provider_id).where(UserProvider.user_id == current_user.id)
        result = await db.execute(stmt)
        current_user.provider_ids = list(result.scalars().all())
    else:
        current_user.provider_ids = None
    return current_user

# -----------------------------------------------------------------------------
# GET / (List Users) - Admin Only
# -----------------------------------------------------------------------------
@router.get("", response_model=List[UserOut])
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Retrieve users.
    """
    query = select(User).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    if users:
        user_ids = [u.id for u in users]
        up_stmt = select(UserProvider).where(UserProvider.user_id.in_(user_ids))
        up_result = await db.execute(up_stmt)
        user_providers = up_result.scalars().all()
        
        up_map = {u.id: [] for u in users}
        for up in user_providers:
            up_map[up.user_id].append(up.provider_id)
            
        for u in users:
            u.provider_ids = up_map[u.id] if u.role != "SUPER_ADMIN" else None

    return users

# -----------------------------------------------------------------------------
# POST / (Create User) - Admin Only
# -----------------------------------------------------------------------------
@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Create new user.
    """
    # Check duplicate email
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    # Hash password
    hashed_password = security.get_password_hash(user_in.password)
    
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=user_in.is_active,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    if user_in.provider_ids is not None:
        for p_id in user_in.provider_ids:
            db.add(UserProvider(user_id=db_user.id, provider_id=p_id))
        db_user.provider_ids = user_in.provider_ids
            
    audit = AuditLog(user_id=current_user.id, action="CREATE_USER", target_type="USER", target_id=str(db_user.id), payload={"role": user_in.role})
    db.add(audit)
    await db.commit()
    return db_user

# -----------------------------------------------------------------------------
# PATCH /{id} (Update User) - Admin Only
# -----------------------------------------------------------------------------
@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Update a user.
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )

    update_data = user_in.model_dump(exclude_unset=True)
    
    audit_payload = {}
    
    if "role" in update_data and update_data["role"] != user.role:
        audit_payload["role_change"] = {"from": user.role, "to": update_data["role"]}
    
    if "password" in update_data and update_data["password"]:
        hashed_password = security.get_password_hash(update_data["password"])
        del update_data["password"]
        user.hashed_password = hashed_password

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    
    if user_in.provider_ids is not None:
        up_stmt = select(UserProvider.provider_id).where(UserProvider.user_id == user.id)
        current_providers = list((await db.execute(up_stmt)).scalars().all())
        if set(current_providers) != set(user_in.provider_ids):
            audit_payload["providers_change"] = {"from": current_providers, "to": user_in.provider_ids}

        await db.execute(delete(UserProvider).where(UserProvider.user_id == user.id))
        for p_id in set(user_in.provider_ids):
            db.add(UserProvider(user_id=user.id, provider_id=p_id))
        user.provider_ids = user_in.provider_ids
            
    audit = AuditLog(user_id=current_user.id, action="UPDATE_USER", target_type="USER", target_id=str(user.id), payload=audit_payload)
    db.add(audit)
    
    await db.commit()
    await db.refresh(user)
    
    if not hasattr(user, "provider_ids") or user.provider_ids is None:
        # Fetch current if not updated to return proper model
        up_stmt = select(UserProvider.provider_id).where(UserProvider.user_id == user.id)
        up_result = await db.execute(up_stmt)
        user.provider_ids = list(up_result.scalars().all())

    return user

# -----------------------------------------------------------------------------
# DELETE /{id} (Soft Delete) - Admin Only
# -----------------------------------------------------------------------------
@router.delete("/{user_id}", response_model=UserOut)
async def delete_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Soft delete a user (set is_active=False).
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none() # type: User

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    
    # Optional: Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account",
        )

    user.is_active = False
    db.add(user)
    
    audit = AuditLog(user_id=current_user.id, action="DELETE_USER", target_type="USER", target_id=str(user.id))
    db.add(audit)
    
    await db.commit()
    await db.refresh(user)
    return user

# -----------------------------------------------------------------------------
# PHOTO UPLOAD
# -----------------------------------------------------------------------------

async def save_profile_photo(db: AsyncSession, user: User, file: UploadFile) -> User:
    # 1. Validation
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed")
    
    # Check size (5MB)
    MAX_SIZE = 5 * 1024 * 1024
    file_content = await file.read()
    if len(file_content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Image size is too large (max 5MB)")
    await file.seek(0)

    # 2. File saving
    ext = os.path.splitext(file.filename)[1] or (".png" if file.content_type == "image/png" else ".jpg")
    timestamp = int(datetime.utcnow().timestamp())
    filename = f"user_{user.id}_{timestamp}{ext}"
    file_path = os.path.join(settings.UPLOAD_PATH, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Update DB
    user.profile_photo = f"/uploads/{filename}"
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/me/photo", response_model=UserOut)
async def upload_my_photo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Upload profile photo for current user.
    """
    return await save_profile_photo(db, current_user, file)

@router.post("/{user_id}/photo", response_model=UserOut)
async def upload_user_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Upload profile photo for a user (Admin only).
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return await save_profile_photo(db, user, file)

