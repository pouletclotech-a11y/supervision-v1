from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AuditLogOut(BaseModel):
    id: int
    user_id: int
    action: str
    target_type: str
    target_id: Optional[str]
    payload: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

class ProfileRevisionOut(BaseModel):
    id: int
    profile_id: int
    version_number: int
    profile_data: Dict[str, Any]
    change_reason: Optional[str]
    updated_by: int
    created_at: datetime

    class Config:
        from_attributes = True

class ReprocessJobOut(BaseModel):
    id: int
    status: str
    scope: Dict[str, Any]
    audit_log_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True

class UnmatchedImportOut(BaseModel):
    id: int
    filename: str
    status: str
    created_at: datetime
    max_score: Optional[float] = None
    best_candidate: Optional[str] = None
    import_metadata: Dict[str, Any]
    raw_payload: Optional[str]

    class Config:
        from_attributes = True

class SandboxResultOut(BaseModel):
    matched_profile_id: Optional[str]
    best_candidate_id: Optional[str]
    best_score: float
    threshold: float
    is_matched: bool
    events_preview: List[Dict[str, Any]]
    total_events: int

class AdminActionSummary(BaseModel):
    action: str
    target_id: Optional[str]
    timestamp: datetime
