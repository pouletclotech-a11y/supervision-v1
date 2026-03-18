from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import ValidationError

from app.db.session import AsyncSessionLocal
from app.auth import security
from app.db.models import User, UserProvider

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/access-token")

async def get_db() -> Generator:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    print(f"DEBUG AUTH: decoding token...")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            print("DEBUG AUTH: no sub in payload")
            raise credentials_exception
    except (JWTError, ValidationError) as e:
        print(f"DEBUG AUTH: decode failed: {e}")
        raise credentials_exception
        
    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        print(f"DEBUG AUTH: user {user_id} not found in DB")
        raise credentials_exception
    if not user.is_active:
        print(f"DEBUG AUTH: user {user_id} is INACTIVE")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    print(f"DEBUG AUTH: user {user.email} authenticated")
    return user

def get_current_active_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    print(f"DEBUG ROLE: user={current_user.email} role={current_user.role} checking for ADMIN/SUPER_ADMIN")
    if current_user.role not in ["ADMIN", "SUPER_ADMIN"]:
        print(f"DEBUG ROLE: REJECTED (not in ADMIN/SUPER_ADMIN)")
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user

def get_current_operator_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in ["ADMIN", "SUPER_ADMIN", "OPERATOR"]:
         raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user

def get_current_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    print(f"DEBUG ROLE: user={current_user.email} role={current_user.role} checking for SUPER_ADMIN")
    if current_user.role != "SUPER_ADMIN":
        print(f"DEBUG ROLE: REJECTED (not SUPER_ADMIN)")
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges. Super Admin required."
        )
    return current_user

async def get_user_provider_ids(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Optional[list[int]]:
    """Retourne la liste des IDs de providers autorisés, ou None si ADMIN/SUPER_ADMIN (accès à tout)."""
    print(f"DEBUG PERM: getting provider IDs for {current_user.email}")
    if current_user.role in ["SUPER_ADMIN", "ADMIN"]:
        return None
    
    stmt = select(UserProvider.provider_id).where(UserProvider.user_id == current_user.id)
    result = await db.execute(stmt)
    ids = list(result.scalars().all())
    print(f"DEBUG PERM: ids={ids}")
    return ids

