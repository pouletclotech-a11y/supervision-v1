from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class NormalizedEvent(BaseModel):
    """
    Pivot format for all incoming events (Excel, PDF, API).
    """
    id: Optional[int] = None
    timestamp: datetime
    site_code: str = Field(..., description="Client Site ID (e.g. C-69000)")
    secondary_code: Optional[str] = Field(None, description="Site Secondary Code (e.g. 32009)")
    client_name: Optional[str] = None
    weekday_label: Optional[str] = None
    
    event_type: str = Field(..., description="Normalized Event Code (e.g. BURGLARY, AC_POWER_LOSS)")
    normalized_type: Optional[str] = None
    sub_type: Optional[str] = None
    
    raw_message: str = Field(..., description="Original log message")
    normalized_message: Optional[str] = Field(None, description="Normalized version for keyword matching")
    raw_code: Optional[str] = None
    
    status: str = Field("INFO", description="Severity or Status (ALARM, RESTORE, INFO)")
    
    zone_label: Optional[str] = None
    category: Optional[str] = None
    alertable_default: bool = False
    metadata: Optional[dict] = Field(default_factory=dict)
    dup_count: int = 0
    
    source_file: str
    row_index: int = -1
    raw_data: Optional[str] = Field(None, description="Raw row content for debug")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ProcessingResult(BaseModel):
    file_path: str
    events_count: int
    success: bool
    error: Optional[str] = None
