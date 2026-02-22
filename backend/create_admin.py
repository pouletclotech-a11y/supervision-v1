import asyncio
import sys
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.auth.security import get_password_hash
from sqlalchemy import select

async def create_admin(email, password):
    print(f"Creating Admin User: {email}")
    async with AsyncSessionLocal() as session:
        # Check if exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            print("User already exists. Updating password and role...")
            existing.hashed_password = get_password_hash(password)
            existing.role = 'ADMIN'
            existing.is_active = True
        else:
            new_user = User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name="System Administrator",
                role="ADMIN",
                is_active=True
            )
            session.add(new_user)
        
        await session.commit()
    print("Admin User Ready.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    asyncio.run(create_admin(email, password))
