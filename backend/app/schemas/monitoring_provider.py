from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class SmtpProviderRuleSchema(BaseModel):
    id: Optional[int] = None
    match_type: str
    match_value: str
    priority: int = 0
    expected_emails_per_day: Optional[int] = None
    expected_interval_minutes: Optional[int] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class MonitoringProviderCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=100)
    ui_color: Optional[str] = None
    is_active: bool = True
    recovery_email: Optional[str] = None
    expected_emails_per_day: int = 0
    expected_frequency_type: str = "daily"
    silence_threshold_minutes: int = 1440
    monitoring_enabled: bool = False
    accepted_attachment_types: List[str] = ["pdf", "xls", "xlsx"]
    email_match_keyword: Optional[str] = None
    expected_interval_minutes: Optional[int] = None

class MonitoringProviderSchema(MonitoringProviderCreate):
    id: int
    last_successful_import_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MonitoringProviderUpdate(BaseModel):
    code: Optional[str] = None
    label: Optional[str] = None
    ui_color: Optional[str] = None
    is_active: Optional[bool] = None
    recovery_email: Optional[str] = None
    expected_emails_per_day: Optional[int] = None
    expected_frequency_type: Optional[str] = None
    silence_threshold_minutes: Optional[int] = None
    monitoring_enabled: Optional[bool] = None
    accepted_attachment_types: Optional[List[str]] = None
    email_match_keyword: Optional[str] = None
    expected_interval_minutes: Optional[int] = None

class ProviderHealthStatus(BaseModel):
    id: int
    code: str
    label: str
    status: str  # OK, LATE, SILENT, UNCONFIGURED
    received_24h: int
    expected_24h: int
    completion_rate: Optional[float]
    last_successful_import_at: Optional[datetime]
    ui_color: Optional[str]

    class Config:
        from_attributes = True
