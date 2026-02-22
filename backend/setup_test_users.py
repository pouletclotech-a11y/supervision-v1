import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.auth.security import get_password_hash
from sqlalchemy import select

async def setup_test_users():
    users = [
        {"email": "viewer_test@test.com", "password": "password123", "role": "VIEWER"},
        {"email": "operator_test@test.com", "password": "password123", "role": "OPERATOR"},
        {"email": "admin_test@test.com", "password": "password123", "role": "ADMIN"},
    ]
    
    async with AsyncSessionLocal() as session:
        for u in users:
            stmt = select(User).where(User.email == u["email"])
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            
            if existing:
                existing.hashed_password = get_password_hash(u["password"])
                existing.role = u["role"]
                existing.is_active = True
            else:
                new_user = User(
                    email=u["email"],
                    hashed_password=get_password_hash(u["password"]),
                    full_name=f"{u['role']} Test User",
                    role=u["role"],
                    is_active=True
                )
                session.add(new_user)
        await session.commit()
    print("Test users created/updated with password 'password123'")

if __name__ == "__main__":
    asyncio.run(setup_test_users())
