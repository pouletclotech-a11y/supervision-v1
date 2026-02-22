"""
test_idempotence.py — Non-regression test for SHA256 idempotence.

Invariant: if the same SHA256 is already in DB with status=SUCCESS,
process_ingestion_item must call ack_duplicate (not ack_success).
No duplicate import must be created.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path
from datetime import datetime

from app.ingestion.adapters.base import AdapterItem


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_item(path="/tmp/idempotence_test/sample.xls", sha256=None):
    return AdapterItem(
        path=path,
        filename="sample.xls",
        size_bytes=1024,
        mtime=datetime.utcnow(),
        source="dropbox",
        sha256=sha256,
        metadata={}
    )


def _make_existing_import(import_id=42, status="SUCCESS"):
    existing = MagicMock()
    existing.id = import_id
    existing.status = status
    return existing


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sha256_duplicate_calls_ack_duplicate():
    """
    INVARIANT: same SHA256 already SUCCESS in DB → ack_duplicate, NOT ack_success.
    Simulates a worker restart that re-encounters the same file.
    """
    import tempfile, os
    # Setup a real temp file so compute_sha256 works
    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as f:
        f.write(b"\x00" * 512)
        tmp_path = f.name

    try:
        item = _make_item(path=tmp_path)
        adapter = MagicMock()
        adapter.ack_duplicate = AsyncMock()
        adapter.ack_success = AsyncMock()
        adapter.ack_error = AsyncMock()
        adapter.__class__.__name__ = "DropboxAdapter"

        existing = _make_existing_import(import_id=99, status="SUCCESS")

        redis_lock = MagicMock()
        redis_lock.acquire = AsyncMock(return_value=True)
        redis_lock.release = AsyncMock()
        redis_client = MagicMock()

        mock_repo = MagicMock()
        mock_repo.get_import_by_hash = AsyncMock(return_value=existing)
        mock_repo.create_import_log = AsyncMock()
        mock_repo.get_active_rules = AsyncMock(return_value=[])

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        with patch("app.ingestion.worker.AsyncSessionLocal", return_value=mock_session):
            with patch("app.ingestion.worker.EventRepository", return_value=mock_repo):
                from app.ingestion.worker import process_ingestion_item
                await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id="test0001")

        # CRITICAL ASSERTIONS
        adapter.ack_duplicate.assert_called_once_with(item, 99)
        adapter.ack_success.assert_not_called()
        mock_repo.create_import_log.assert_not_called()

    finally:
        os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_sha256_not_in_db_proceeds_normally():
    """
    If SHA256 is NOT in DB or status != SUCCESS → processing continues normally.
    """
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as f:
        f.write(b"\x01" * 512)
        tmp_path = f.name

    try:
        item = _make_item(path=tmp_path)
        adapter = MagicMock()
        adapter.ack_duplicate = AsyncMock()
        adapter.ack_success = AsyncMock()
        adapter.ack_error = AsyncMock()
        adapter.ack_unmatched = AsyncMock()
        adapter.__class__.__name__ = "DropboxAdapter"

        redis_lock = MagicMock()
        redis_lock.acquire = AsyncMock(return_value=True)
        redis_lock.release = AsyncMock()
        redis_client = MagicMock()

        mock_repo = MagicMock()
        # Not in DB
        mock_repo.get_import_by_hash = AsyncMock(return_value=None)
        mock_repo.create_import_log = AsyncMock()
        mock_repo.update_import_log = AsyncMock()
        mock_repo.get_active_rules = AsyncMock(return_value=[])

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        # Profile matcher returns None → UNMATCHED path
        with patch("app.ingestion.worker.AsyncSessionLocal", return_value=mock_session):
            with patch("app.ingestion.worker.EventRepository", return_value=mock_repo):
                with patch("app.ingestion.worker.profile_matcher") as mock_matcher:
                    mock_matcher.match = MagicMock(return_value=None)
                    from app.ingestion.worker import process_ingestion_item
                    await process_ingestion_item(adapter, item, redis_lock, redis_client, poll_run_id="test0002")

        # Should proceed to UNMATCHED, not duplicate
        adapter.ack_duplicate.assert_not_called()
        adapter.ack_unmatched.assert_called_once()

    finally:
        os.unlink(tmp_path)
