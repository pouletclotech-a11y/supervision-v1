"""
conftest.py — Fixtures partagées pour la suite de tests Phase 3.

Stratégie :
- `init_test_db` : crée les tables une seule fois (scope=session).
- `db_cleanup`   : TRUNCATE avant chaque test (autouse=True) → isolation parfaite.
- `db_session`   : engine dédié par test → pas de fuite de boucle asyncio.
- `redis_client` : stub MagicMock → aucune dépendance Redis.
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

@pytest_asyncio.fixture(scope="session")
async def init_test_db():
    """
    Drop and recreate all tables once per pytest session.
    Ensures the schema is exactly in sync with the current ORM models.
    """
    init_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=False)
    async with init_engine.begin() as conn:
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
