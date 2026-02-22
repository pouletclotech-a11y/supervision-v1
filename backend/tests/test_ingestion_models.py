import pytest
from datetime import datetime
from pydantic import ValidationError
from app.ingestion.models import NormalizedEvent

def test_normalized_event_valid():
    """Valid event with mandatory fields."""
    event = NormalizedEvent(
        timestamp=datetime.now(),
        site_code="69000",
        event_type="BURGLARY",
        raw_message="Test message",
        source_file="test.xls",
        tenant_id="default-tenant"
    )
    assert event.tenant_id == "default-tenant"

def test_normalized_event_missing_tenant():
    """Should fail if tenant_id is missing."""
    with pytest.raises(ValidationError) as excinfo:
        NormalizedEvent(
            timestamp=datetime.now(),
            site_code="69000",
            event_type="BURGLARY",
            raw_message="Test message",
            source_file="test.xls"
        )
    assert "tenant_id" in str(excinfo.value)

def test_normalized_event_extra_field():
    """Should fail if extra field is provided (extra='forbid')."""
    with pytest.raises(ValidationError) as excinfo:
        NormalizedEvent(
            timestamp=datetime.now(),
            site_code="69000",
            event_type="BURGLARY",
            raw_message="Test message",
            source_file="test.xls",
            tenant_id="default-tenant",
            unknown_field="intruder"
        )
    assert "Extra inputs are not permitted" in str(excinfo.value) or "extra fields not permitted" in str(excinfo.value)

def test_normalized_event_wrong_type():
    """Should fail if type is incorrect (strict-ish)."""
    with pytest.raises(ValidationError) as excinfo:
        NormalizedEvent(
            timestamp="yesterday", # Not a datetime
            site_code="69000",
            event_type="BURGLARY",
            raw_message="Test message",
            source_file="test.xls",
            tenant_id="default-tenant"
        )
    assert "datetime" in str(excinfo.value)

def test_normalized_event_validate_assignment():
    """Should fail if an invalid value is assigned after creation."""
    event = NormalizedEvent(
        timestamp=datetime.now(),
        site_code="69000",
        event_type="BURGLARY",
        raw_message="Test message",
        source_file="test.xls",
        tenant_id="default-tenant"
    )
    with pytest.raises(ValidationError):
        event.tenant_id = None # Should fail due to validate_assignment=True
