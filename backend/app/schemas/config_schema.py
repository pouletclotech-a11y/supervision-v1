from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class ProviderConfigSchema(BaseModel):
    code: str
    label: str
    ui_color: Optional[str] = None
    is_active: bool = True
    recovery_email: Optional[str] = None
    expected_emails_per_day: int = 0
    expected_frequency_type: str = 'daily'
    silence_threshold_minutes: int = 1440
    monitoring_enabled: bool = False
    accepted_attachment_types: List[str] = ["pdf", "xls", "xlsx"]
    email_match_keyword: Optional[str] = None
    expected_interval_minutes: Optional[int] = None
    quality_min_created_ratio: float = 0.8
    quality_alert_enabled: bool = True
    
    # PDF Soft-Match Config
    pdf_warning_threshold: float = 0.9
    pdf_critical_threshold: float = 0.7
    pdf_ignore_case: bool = True
    pdf_ignore_accents: bool = True

class ProfileConfigSchema(BaseModel):
    profile_id: str
    name: str
    description: Optional[str] = None
    priority: int = 0
    format_kind: str
    provider_code: Optional[str] = None
    source_timezone: str = "Europe/Paris"
    detection: Optional[Any] = {}
    mapping: Optional[Any] = {}
    action_config: Optional[Any] = {}
    filename_regex: Optional[str] = None
    is_active: bool = True

class ConfigExportSchema(BaseModel):
    version: str = "1.0"
    exported_at: datetime = Field(default_factory=datetime.now)
    providers: List[ProviderConfigSchema]
    profiles: List[ProfileConfigSchema]

class ImportDiffItem(BaseModel):
    key: str
    action: str # "CREATE", "UPDATE", "UNCHANGED", "DISABLE", "ERROR"
    details: Optional[str] = None

class ImportSummarySchema(BaseModel):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    disabled: int = 0
    errors: List[str] = []
    diff: List[ImportDiffItem] = []
