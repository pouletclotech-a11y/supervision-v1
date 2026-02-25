import pytest
import uuid
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from app.ingestion.worker import worker_loop
from app.ingestion.adapters.base import AdapterItem, BaseAdapter
from app.db.models import ImportLog, Event
from app.db.session import AsyncSessionLocal
from sqlalchemy import select

class MockRegistry:
    def __init__(self, items):
        self.items = items
    async def poll_all(self):
        for adapter, item in self.items:
            yield adapter, item

class MockAdapter(BaseAdapter):
    async def poll(self): yield None
    async def ack_success(self, item, import_id): pass
    async def ack_duplicate(self, item, import_id): pass
    async def ack_error(self, item, error_msg): pass
    async def ack_unmatched(self, item, reason): pass

@pytest.mark.asyncio
async def test_worker_fusion_grouping(tmp_path):
    """Vérifie que le worker groupe les items par source_message_id et lie le PDF à l'XLS."""
    msg_id = f"test-email-{uuid.uuid4().hex}"
    
    # 1. Create dummy XLS and PDF
    xls_path = tmp_path / "data.xls"
    # Need a real-looking TSV for profiling
    xls_path.write_text("TITRE EXPORT\tSite\tDate\n69002\tClient A\t24/02/2026\n", encoding="latin-1")
    
    # PDF path (using an existing small file or dummy)
    pdf_path = tmp_path / "support.pdf"
    pdf_path.write_text("%PDF-1.4 dummy", encoding="latin-1")
    
    item_xls = AdapterItem(
        filename="data.xls",
        path=str(xls_path),
        size_bytes=xls_path.stat().st_size,
        mtime=os.path.getmtime(xls_path),
        source="email",
        source_message_id=msg_id,
        metadata={"sender_email": "test@alpha.pro"}
    )
    
    item_pdf = AdapterItem(
        filename="support.pdf",
        path=str(pdf_path),
        size_bytes=pdf_path.stat().st_size,
        mtime=os.path.getmtime(pdf_path),
        source="email",
        source_message_id=msg_id,
        metadata={"sender_email": "test@alpha.pro"}
    )
    
    adapter = MockAdapter()
    poll_run_id = "test-fusion"
    
    redis_client = AsyncMock()
    redis_lock = MagicMock()
    redis_lock.acquire = AsyncMock(return_value="token")
    redis_lock.release = AsyncMock()
    
    from app.ingestion.worker import process_ingestion_item
    from app.services.classification_service import ClassificationService
    from app.parsers.pdf_parser import PdfParser
    from app.db.models import MonitoringProvider
    
    # 0. Seed provider for the test
    async with AsyncSessionLocal() as session:
        # Check if exists
        stmt = select(MonitoringProvider).where(MonitoringProvider.id == 1)
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            p = MonitoringProvider(
                id=1, code="PROVIDER_TEST", label="Test Provider", 
                is_active=True, expected_emails_per_day=0, 
                expected_frequency_type="daily", silence_threshold_minutes=1440,
                monitoring_enabled=False, accepted_attachment_types=["pdf", "xls"]
            )
            session.add(p)
            await session.commit()
    
    from app.ingestion.profile_matcher import ProfileMatcher
    mock_profile = MagicMock()
    mock_profile.profile_id = 'test_profile'
    mock_report = {'best_score': 10.0}
    
    with patch.object(ClassificationService, 'classify_email', return_value=1), \
         patch.object(PdfParser, 'parse', return_value=[]), \
         patch.object(ProfileMatcher, 'match', return_value=(mock_profile, mock_report)):
        
        # Simuler le groupage : XLS en premier (pour être primary), puis PDF
        primary_id = await process_ingestion_item(adapter, item_xls, redis_lock, redis_client, poll_run_id)
        assert primary_id is not None
        
        # Deuxième appel avec le PDF et le primary_id
        res_id = await process_ingestion_item(adapter, item_pdf, redis_lock, redis_client, poll_run_id, existing_import_id=primary_id)
    
    # Verify in DB
    async with AsyncSessionLocal() as session:
        stmt = select(ImportLog).where(ImportLog.id == primary_id)
        res = await session.execute(stmt)
        import_log = res.scalars().one()
        
        assert import_log.status == "SUCCESS"
        assert import_log.filename == "data.xls"
        assert import_log.pdf_path is not None
        assert "support.pdf" in import_log.pdf_path
