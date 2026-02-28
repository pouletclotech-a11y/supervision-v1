from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, ConfigDict

class ImportLogOut(BaseModel):
    id: int
    filename: str
    status: str
    events_count: int
    duplicates_count: int
    unmatched_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    archive_path: Optional[str] = None
    file_hash: Optional[str] = None
    adapter_name: Optional[str] = None
    source_message_id: Optional[str] = None
    archive_status: Optional[str] = None
    pdf_path: Optional[str] = None
    archived_pdf_hash: Optional[str] = None
    pdf_support_path: Optional[str] = None
    pdf_support_filename: Optional[str] = None
    match_pct: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class ImportListOut(BaseModel):
    imports: List[ImportLogOut]
    total: int

class TriggeredRuleSummary(BaseModel):
    id: int
    name: str
    matched_at: datetime

class EventOut(BaseModel):
    id: int
    time: datetime
    site_code: Optional[str] = None # Mapped from Site
    client_name: Optional[str] = None
    weekday_label: Optional[str] = None
    # zone_id: Optional[int] = None
    import_id: Optional[int] = None
    raw_message: str
    raw_code: Optional[str] = None
    normalized_type: Optional[str] = None
    sub_type: Optional[str] = None
    severity: Optional[str] = None
    zone_label: Optional[str] = None
    # event_metadata: Optional[dict] = None
    source_file: str
    # dup_count: int
    created_at: datetime
    triggered_rules: List[TriggeredRuleSummary] = []

    model_config = ConfigDict(from_attributes=True)

class EventListOut(BaseModel):
    events: List[EventOut]
    total: int

class TimeScopeEnum(str, Enum):
    NONE = "NONE"
    NIGHT = "NIGHT"
    WEEKEND = "WEEKEND"
    HOLIDAYS = "HOLIDAYS"
    OFF_BUSINESS_HOURS = "OFF_BUSINESS_HOURS"
    BUSINESS_HOURS = "BUSINESS_HOURS"

class AlertRuleBase(BaseModel):
    name: str
    condition_type: str
    value: str
    scope_site_code: Optional[str] = None
    
    # B1/V3 Frequency
    frequency_count: int = 1
    frequency_window: int = 0
    sliding_window_days: int = 0
    is_open_only: bool = False
    
    # Sequence (A -> B)
    sequence_enabled: bool = False
    seq_a_category: Optional[str] = None
    seq_a_keyword: Optional[str] = None
    seq_b_category: Optional[str] = None
    seq_b_keyword: Optional[str] = None
    seq_max_delay_seconds: int = 0
    seq_lookback_days: int = 2
    
    # Logic Tree (AST)
    logic_enabled: bool = False
    logic_tree: Optional[dict] = None
    
    # Keywords/Category Filter (V3)
    match_category: Optional[str] = None
    match_keyword: Optional[str] = None
    
    schedule_start: Optional[str] = None # HH:MM
    schedule_end: Optional[str] = None # HH:MM
    time_scope: Optional[TimeScopeEnum] = TimeScopeEnum.NONE
    email_notify: bool = False
    is_active: bool = True

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    condition_type: Optional[str] = None
    value: Optional[str] = None
    scope_site_code: Optional[str] = None
    
    frequency_count: Optional[int] = None
    frequency_window: Optional[int] = None
    sliding_window_days: Optional[int] = None
    is_open_only: Optional[bool] = None
    
    sequence_enabled: Optional[bool] = None
    seq_a_category: Optional[str] = None
    seq_a_keyword: Optional[str] = None
    seq_b_category: Optional[str] = None
    seq_b_keyword: Optional[str] = None
    seq_max_delay_seconds: Optional[int] = None
    seq_lookback_days: Optional[int] = None
    
    logic_enabled: Optional[bool] = None
    logic_tree: Optional[dict] = None
    
    match_category: Optional[str] = None
    match_keyword: Optional[str] = None
    
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    time_scope: Optional[TimeScopeEnum] = None
    email_notify: Optional[bool] = None
    is_active: Optional[bool] = None

class AlertRuleCreate(AlertRuleBase):
    pass

class AlertRuleOut(AlertRuleBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
