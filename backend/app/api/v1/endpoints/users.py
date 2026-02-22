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
from app.db.models import User
from app.schemas.user import UserCreate, UserUpdate, UserOut

router = APIRouter()

# -----------------------------------------------------------------------------
# GET /me
# -----------------------------------------------------------------------------
@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get current user.
    """
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
    
    if "password" in update_data and update_data["password"]:
        hashed_password = security.get_password_hash(update_data["password"])
        del update_data["password"]
        user.hashed_password = hashed_password

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    await db.commit()
    await db.refresh(user)
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

