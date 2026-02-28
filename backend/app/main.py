from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS]
if "http://localhost:3000" not in origins:
    origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.api import api_router
from app.db.session import engine
from app.db.models import Base, User
from sqlalchemy import select, text
from create_admin import create_admin as perform_admin_seed

app.include_router(api_router, prefix=settings.API_V1_STR)

logger = logging.getLogger(__name__)

# Ensure upload directory exists before mounting StaticFiles
if not os.path.exists(settings.UPLOAD_PATH):
    os.makedirs(settings.UPLOAD_PATH, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_PATH), name="uploads")

@app.on_event("startup")
async def init_tables():
    # Confirm active environment
    logger.info(f"--- Application Starting in ENVIRONMENT={settings.ENVIRONMENT} ---")
    
    # Roadmap V12: Dump Monitoring Settings (Merged)
    from app.db.models import Setting
    from app.db.session import AsyncSessionLocal
    import json
    
    async with AsyncSessionLocal() as session:
        merged = await settings.get_monitoring_settings(session)
        import json
        logger.info(f"MONITORING_SETTINGS_LOADED: {json.dumps(merged, indent=2)}")

    # 1. Database Schema Sync (STRICTLY DEVELOPMENT ONLY)
    if settings.ENVIRONMENT == "development":
        logger.warning("DEVELOPMENT MODE: Ensuring database schema (create_all)...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        logger.info("PRODUCTION MODE: Automatic schema sync disabled. Ensure migrations are applied.")

    # 2. Automagical Admin Seed
    if settings.AUTO_SEED_ADMIN:
        async with engine.connect() as conn:
            # Check if users table exists before seeding
            try:
                # We use a raw query to check table existence without crashing
                await conn.execute(text("SELECT 1 FROM users LIMIT 1"))
                table_exists = True
            except Exception:
                table_exists = False
                
            if not table_exists:
                logger.warning("Admin Seeding: 'users' table not found. Skipping seed (migrations needed).")
                return

        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            # Check if any admin exists
            stmt = select(User).where(User.role == "ADMIN")
            result = await session.execute(stmt)
            admins = result.scalars().all()
            
            if not admins:
                logger.info("No ADMIN user found. Triggering automatic seed...")
                if settings.ENVIRONMENT == "production" and not settings.DEFAULT_ADMIN_PASSWORD:
                    logger.error("SEED_FAILED: DEFAULT_ADMIN_PASSWORD must be set via ENV in production!")
                    return
                
                email = settings.DEFAULT_ADMIN_EMAIL
                password = settings.DEFAULT_ADMIN_PASSWORD or "SuperSecurePassword123"
                
                try:
                    await perform_admin_seed(email, password)
                    logger.info(f"Admin seed successful for {email}")
                except Exception as e:
                    logger.error(f"Admin seed failed: {e}")
            else:
                logger.debug("Admin users already exist. Skipping seed.")

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}

@app.get("/")
def root():
    return {"message": "Welcome to Supervision Tool V1 API"}
