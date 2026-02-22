import asyncio
import argparse
import sys
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.auth.security import get_password_hash
from sqlalchemy import select

async def create_admin(email, password):
    print(f"--- ADMIN SEED START: {email} ---")
    async with AsyncSessionLocal() as session:
        # Check if exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        updated = False
        if existing:
            print("User already exists. Updating password and roles...")
            existing.hashed_password = get_password_hash(password)
            existing.role = 'ADMIN'
            existing.is_active = True
            existing.is_superuser = True # Ensure superuser if model supports it
            updated = True
        else:
            print("Creating new admin user...")
            new_user = User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name="System Administrator",
                role="ADMIN",
                is_active=True
            )
            # Some versions use is_superuser
            if hasattr(new_user, "is_superuser"):
                new_user.is_superuser = True
                
            session.add(new_user)
        
        await session.commit()
    print(f"ADMIN_SEEDED email={email} updated={str(updated).lower()}")
    print("--- ADMIN SEED DONE ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or update an admin user.")
    parser.add_argument("--email", default="admin@supervision.local", help="Admin email")
    parser.add_argument("--password", default="SuperSecurePassword123", help="Admin password")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(create_admin(args.email, args.password))
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
