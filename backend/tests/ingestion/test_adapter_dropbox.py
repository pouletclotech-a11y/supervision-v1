import pytest
import os
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from app.ingestion.adapters.dropbox import DropboxAdapter
from app.ingestion.adapters.base import AdapterItem

@pytest.fixture
def temp_dirs(tmp_path):
    ingress = tmp_path / "ingress"
    archive = tmp_path / "archive"
    ingress.mkdir()
    archive.mkdir()
    return ingress, archive

@pytest.mark.asyncio
async def test_dropbox_poll_filters_and_sorts(temp_dirs):
    ingress, archive = temp_dirs
    # Create some files
    (ingress / "test1.xls").write_text("content1")
    (ingress / "test2.pdf").write_text("content2")
    (ingress / "ignored.txt").write_text("ignored")
    (ingress / ".hidden").write_text("hidden")
    
    adapter = DropboxAdapter(ingress_dir=str(ingress), archive_dir=str(archive))
    items = await adapter.poll()
    
    assert len(items) == 2
    assert any(i.filename == "test1.xls" for i in items)
    assert any(i.filename == "test2.pdf" for i in items)
    assert not any(i.filename == "ignored.txt" for i in items)

@pytest.mark.asyncio
async def test_dropbox_ack_success_moves_to_date_tree(temp_dirs):
    ingress, archive = temp_dirs
    f = ingress / "sample.xls"
    f.write_text("data")
    
    adapter = DropboxAdapter(ingress_dir=str(ingress), archive_dir=str(archive))
    item = AdapterItem(
        path=str(f),
        filename=f.name,
        size_bytes=len("data"),
        mtime=datetime.utcnow(),
        source="dropbox",
        sha256="fakehash"
    )
    
    await adapter.ack_success(item, import_id=123)
    
    # Check move
    assert not f.exists()
    
    # Check destination path (YYYY/MM/DD)
    now = datetime.utcnow()
    expected_path = archive / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d") / "sample.xls"
    assert expected_path.exists()

@pytest.mark.asyncio
async def test_dropbox_ack_duplicate_moves_to_duplicates(temp_dirs):
    ingress, archive = temp_dirs
    f = ingress / "dup.xls"
    f.write_text("data")
    
    adapter = DropboxAdapter(ingress_dir=str(ingress), archive_dir=str(archive))
    item = AdapterItem(
        path=str(f),
        filename=f.name,
        size_bytes=len("data"),
        mtime=datetime.utcnow(),
        source="dropbox",
        sha256="fakehash"
    )
    
    await adapter.ack_duplicate(item, existing_import_id=1)
    
    assert not f.exists()
    assert (archive / "duplicates" / "dup.xls").exists()

@pytest.mark.asyncio
async def test_dropbox_ack_unmatched_moves_to_unmatched_date_tree(temp_dirs):
    ingress, archive = temp_dirs
    f = ingress / "unmatched.xls"
    f.write_text("data")
    
    adapter = DropboxAdapter(ingress_dir=str(ingress), archive_dir=str(archive))
    item = AdapterItem(
        path=str(f),
        filename=f.name,
        size_bytes=len("data"),
        mtime=datetime.utcnow(),
        source="dropbox",
        sha256="fakehash"
    )
    
    await adapter.ack_unmatched(item, reason="No profile")
    
    now = datetime.utcnow()
    expected_path = archive / "unmatched" / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d") / "unmatched.xls"
    assert expected_path.exists()

@pytest.mark.asyncio
async def test_dropbox_ack_error_moves_to_error_date_tree(temp_dirs):
    ingress, archive = temp_dirs
    f = ingress / "error.xls"
    f.write_text("data")
    
    adapter = DropboxAdapter(ingress_dir=str(ingress), archive_dir=str(archive))
    item = AdapterItem(
        path=str(f),
        filename=f.name,
        size_bytes=len("data"),
        mtime=datetime.utcnow(),
        source="dropbox",
        sha256="fakehash"
    )
    
    await adapter.ack_error(item, reason="Crash")
    
    now = datetime.utcnow()
    expected_path = archive / "error" / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d") / "error.xls"
    assert expected_path.exists()
