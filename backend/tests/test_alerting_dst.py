import pytest
import pytz
import json
from datetime import datetime, timedelta
from app.ingestion.models import NormalizedEvent
from app.services.alerting import AlertingService
from app.services.repository import EventRepository
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_alerting_dst_transition_march():
    service = AlertingService()
    repo = AsyncMock(spec=EventRepository)
    
    rule = MagicMock()
    rule.id = 1
    rule.match_category = "INTRUSION"
    rule.match_keyword = None
    rule.frequency_count = 2
    rule.sliding_window_days = 1
    rule.time_scope = "NONE"
    rule.logic_enabled = False
    rule.is_active = True
    rule.scope_site_code = None
    rule.condition_type = None
    rule.schedule_start = None
    rule.schedule_end = None
    rule.sequence_enabled = False
    
    paris_tz = pytz.timezone("Europe/Paris")
    dt2_utc = paris_tz.localize(datetime(2026, 3, 29, 10, 0, 0)).astimezone(pytz.UTC)
    
    event2 = NormalizedEvent(
        timestamp=dt2_utc,
        site_code="SITE1",
        event_type="INTRUSION",
        normalized_type="APPARITION",
        category="INTRUSION",
        raw_message="Intrusion",
        tenant_id="test-tenant",
        source_file="test.pdf"
    )
    
    repo.count_v3_matches.return_value = 1
    res = await service.evaluate_rule(event2, rule, repo=repo)
    
    assert res["condition_ok"] is True
    repo.count_v3_matches.assert_called_once()
    assert res["triggered"] is True

@pytest.mark.asyncio
async def test_alerting_dst_transition_october():
    service = AlertingService()
    repo = AsyncMock(spec=EventRepository)
    
    rule = MagicMock()
    rule.id = 2
    rule.match_category = "TEST"
    rule.match_keyword = None
    rule.frequency_count = 2 # ADDED
    rule.sliding_window_days = 1
    rule.logic_enabled = False
    rule.is_active = True
    rule.time_scope = "NONE"
    rule.scope_site_code = None
    rule.condition_type = None
    rule.schedule_start = None
    rule.schedule_end = None
    rule.sequence_enabled = False

    paris_tz = pytz.timezone("Europe/Paris")
    dt2_utc = paris_tz.localize(datetime(2026, 10, 25, 10, 0, 0)).astimezone(pytz.UTC)
    
    event2 = NormalizedEvent(
        timestamp=dt2_utc, 
        site_code="SITE1", 
        event_type="TEST",
        normalized_type="APPARITION",
        category="TEST",
        raw_message="Test",
        tenant_id="test-tenant",
        source_file="test.pdf"
    )
    
    repo.count_v3_matches.return_value = 1
    res = await service.evaluate_rule(event2, rule, repo=repo)
    
    assert res["condition_ok"] is True
    repo.count_v3_matches.assert_called_once()
    assert res["triggered"] is True
