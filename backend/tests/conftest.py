"""
conftest.py — Specialized fixtures for Phase 3 testing with mandatory isolated DB.

Safety Strategy:
- FORCE_TEST_DB: Automatically redirects SQLALCHEMY_DATABASE_URI to 'supervision_test'.
- PROTECT_MAIN_DB: Explicitly raises RuntimeError if 'supervision' (main) is targeted.
- init_test_db: Drop and recreate tables once per session on the test DB.
- db_cleanup: DELETE from sensitive tables before each test for isolation.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.db.models import Base
from app.core.config import settings


# ──────────────────────────────────────────────
# DB: create tables once per session
# ──────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_test_db():
    """
    Drop and recreate all tables once per pytest session on the DEDICATED test database.
    """
    # 1. Force the URI to point to supervision_test regardless of .env/settings
    original_uri = settings.SQLALCHEMY_DATABASE_URI
    if "supervision_test" not in original_uri:
        # Construct the test URI
        base_uri = original_uri.rsplit('/', 1)[0]
        test_uri = f"{base_uri}/supervision_test"
        settings.SQLALCHEMY_DATABASE_URI = test_uri
        print(f"\n[TEST_GUARD] Redirecting DB to: {test_uri}")

    # 2. Hard block against the main 'supervision' database
    db_name = settings.SQLALCHEMY_DATABASE_URI.split('/')[-1].split('?')[0]
    if db_name == "supervision":
        raise RuntimeError(
            "CRITICAL SECURITY BLOCKED: Pytest attempted to run on the MAIN 'supervision' database. "
            "Execution halted to prevent data loss."
        )
    
    if not db_name.endswith("_test"):
        raise RuntimeError(f"CRITICAL: Target database '{db_name}' does not end with '_test'. Aborting.")

    init_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=False)
    
    async with init_engine.begin() as conn:
        print(f"[TEST_DB] Initializing schema on {db_name}...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    await init_engine.dispose()


# ──────────────────────────────────────────────
# DB: clean relevant tables before each test
# ──────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def db_cleanup(init_test_db):
    """
    Truncate test-sensitive tables before each test.
    Prevents UniqueViolationErrors from DB state persisting across pytest runs.
    """
    clean_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=False)
    async with AsyncSession(clean_engine, expire_on_commit=False) as session:
        await session.execute(text("DELETE FROM ingestion_profiles"))
        await session.execute(text("DELETE FROM imports"))
        await session.commit()
    await clean_engine.dispose()
    yield


# ──────────────────────────────────────────────
# DB: per-test session with its own engine
# ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session(db_cleanup):
    """
    Provides an isolated AsyncSession per test.
    Creates its own engine to prevent event loop cross-contamination.
    Rolls back at the end.
    """
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ──────────────────────────────────────────────
# Redis: stub (no real Redis dependency in unit tests)
# ──────────────────────────────────────────────

@pytest.fixture
def redis_client():
    """Stub Redis client. Prevents real network calls in unit tests."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=0)
    mock.exists = AsyncMock(return_value=False)
    return mock
