from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table, Text, Float, JSON, select, func, BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase):
    pass

class Site(Base):
    __tablename__ = "sites"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code_client: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    secondary_code: Mapped[Optional[str]] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text)
    contact_info: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    status: Mapped[str] = mapped_column(String(20), default='ACTIVE')
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=[])
    config_override: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class Zone(Base):
    __tablename__ = "zones"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    code_zone: Mapped[str] = mapped_column(String(50))
    label: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(50), default='UNKNOWN')
    status: Mapped[str] = mapped_column(String(20), default='ACTIVE')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    
    # TimescaleDB hypertable - primary key logic handled by partition
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True) 
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    site_id: Mapped[Optional[int]] = mapped_column(Integer) # Loose FK for hypertable speed
    zone_id: Mapped[Optional[int]] = mapped_column(Integer)
    import_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("imports.id"))
    
    site_code: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    weekday_label: Mapped[Optional[str]] = mapped_column(String(20))
    raw_message: Mapped[Optional[str]] = mapped_column(Text)
    normalized_message: Mapped[Optional[str]] = mapped_column(Text, index=True)
    raw_code: Mapped[Optional[str]] = mapped_column(String(50))
    normalized_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    sub_type: Mapped[Optional[str]] = mapped_column(String(50))
    severity: Mapped[Optional[str]] = mapped_column(String(20))
    zone_label: Mapped[Optional[str]] = mapped_column(String(255))
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    source_file: Mapped[Optional[str]] = mapped_column(String(255))
    dup_count: Mapped[int] = mapped_column(Integer, default=0)
    in_maintenance: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data: Mapped[Optional[str]] = mapped_column(Text) # Raw source line for audit
    category: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    alertable_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Indices for performance (B1 - Frequency checks)
    __table_args__ = (
        Index('ix_events_site_time', 'site_code', 'time'),
        Index('ix_events_site_severity_time', 'site_code', 'severity', 'time'),
        Index('ix_events_site_type_time', 'site_code', 'normalized_type', 'time'),
    )

class ImportLog(Base):
    __tablename__ = "imports"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(50)) # PENDING, SUCCESS, ERROR, PROFILE_NOT_CONFIDENT
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_count: Mapped[int] = mapped_column(Integer, default=0)
    unmatched_count: Mapped[int] = mapped_column(Integer, default=0)
    adapter_name: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Traceability (Phase 3)
    import_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    raw_payload: Mapped[Optional[str]] = mapped_column(Text)
    
    # Source & Archive
    archive_path: Mapped[Optional[str]] = mapped_column(Text)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    archive_status: Mapped[str] = mapped_column(String(20), default='PENDING')
    
    # PDF Linking
    pdf_path: Mapped[Optional[str]] = mapped_column(Text)
    source_message_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    archived_pdf_hash: Mapped[Optional[str]] = mapped_column(String(64))
    
    # Phase 3: Provider attribution
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("monitoring_providers.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DBIngestionProfile(Base):
    __tablename__ = "ingestion_profiles"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    source_timezone: Mapped[str] = mapped_column(String(50), default="Europe/Paris")
    provider_code: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    
    # Versioning
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    
    # Threshold
    confidence_threshold: Mapped[float] = mapped_column(Float, default=2.0)
    
    # Technical Config (JSONB)
    detection: Mapped[dict] = mapped_column(JSONB)
    mapping: Mapped[list] = mapped_column(JSONB)
    parser_config: Mapped[dict] = mapped_column(JSONB, default={})
    extraction_rules: Mapped[dict] = mapped_column(JSONB, default={})
    normalization: Mapped[list] = mapped_column(JSONB, default={})
    
    # Specific options
    excel_options: Mapped[Optional[dict]] = mapped_column(JSONB)
    csv_options: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    condition_type: Mapped[str] = mapped_column(String(50)) # KEYWORD, SEVERITY
    value: Mapped[str] = mapped_column(String(255))
    
    # Advanced Scoping
    scope_site_code: Mapped[Optional[str]] = mapped_column(String(50)) # NULL = All Sites
    
    # Frequency Logic (X times in Y seconds)
    frequency_count: Mapped[int] = mapped_column(Integer, default=1)
    frequency_window: Mapped[int] = mapped_column(Integer, default=0) # Seconds. 0 = Instant
    
    # Schedule & Time Scope (B1)
    schedule_start: Mapped[Optional[str]] = mapped_column(String(5)) # HH:MM
    schedule_end: Mapped[Optional[str]] = mapped_column(String(5))   # HH:MM
    time_scope: Mapped[str] = mapped_column(String(50), default="NONE") # NONE, NIGHT, WEEKEND, etc.
    
    # V3 Advanced Scoping
    match_category: Mapped[Optional[str]] = mapped_column(String(50))
    match_keyword: Mapped[Optional[str]] = mapped_column(String(255))
    is_open_only: Mapped[bool] = mapped_column(Boolean, default=False)
    sliding_window_days: Mapped[int] = mapped_column(Integer, default=0) # 0 = B1 logic, >0 = V3

    # V3 Sequence (A -> B in Δt)
    sequence_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    seq_a_category: Mapped[Optional[str]] = mapped_column(String(50))
    seq_a_keyword: Mapped[Optional[str]] = mapped_column(String(255))
    seq_b_category: Mapped[Optional[str]] = mapped_column(String(50))
    seq_b_keyword: Mapped[Optional[str]] = mapped_column(String(255))
    seq_max_delay_seconds: Mapped[int] = mapped_column(Integer, default=0)
    seq_lookback_days: Mapped[int] = mapped_column(Integer, default=2)

    # V3 Logic Tree (AST)
    logic_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    logic_tree: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Actions
    email_notify: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ReplayJob(Base):
    __tablename__ = "replay_jobs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default='RUNNING') # RUNNING, SUCCESS, ERROR
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    events_scanned: Mapped[int] = mapped_column(Integer, default=0)
    alerts_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

class Setting(Base):
    __tablename__ = "settings"
    
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text) # JSON or simple string
    description: Mapped[Optional[str]] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default='VIEWER') # ADMIN, OPERATOR, VIEWER
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_photo: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EventRuleHit(Base):
    __tablename__ = "event_rule_hits"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(BigInteger, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True)
    rule_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_event_rule_hit_unique', 'event_id', 'rule_id', unique=True),
    )

# Phase 3: Compteurs Raccordements par Télésurveilleur

class MonitoringProvider(Base):
    __tablename__ = "monitoring_providers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # SPGO, CORS
    label: Mapped[str] = mapped_column(String(100))  # Affichage UI
    ui_color: Mapped[Optional[str]] = mapped_column(String(20)) # Hex color or CSS color
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Phase 2.B: Monitoring Layer
    recovery_email: Mapped[Optional[str]] = mapped_column(String(255))
    expected_emails_per_day: Mapped[int] = mapped_column(Integer, default=0)
    expected_frequency_type: Mapped[str] = mapped_column(String(20), default='daily')
    silence_threshold_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_successful_import_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Phase Architecture: Security & Refined Monitoring
    accepted_attachment_types: Mapped[dict] = mapped_column(JSONB, default=["pdf", "xls", "xlsx"])
    email_match_keyword: Mapped[Optional[str]] = mapped_column(String(255))
    expected_interval_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SmtpProviderRule(Base):
    __tablename__ = "smtp_provider_rules"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("monitoring_providers.id", ondelete="CASCADE"), index=True)
    match_type: Mapped[str] = mapped_column(String(20))  # EXACT, DOMAIN, REGEX
    match_value: Mapped[str] = mapped_column(String(255))  # email, domain, pattern
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher = tested first
    
    # Provider-Centric Security (v2): Frequency per rule
    expected_emails_per_day: Mapped[Optional[int]] = mapped_column(Integer)
    expected_interval_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SiteConnection(Base):
    __tablename__ = "site_connections"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("monitoring_providers.id", ondelete="CASCADE"), index=True)
    code_site: Mapped[str] = mapped_column(String(50), index=True)  # Code client
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    first_import_id: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Phase 2.A: Business Metrics
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_events: Mapped[int] = mapped_column(Integer, default=0)
    
    __table_args__ = (
        Index('ix_site_connection_unique', 'provider_id', 'code_site', unique=True),
    )

class Incident(Base):
    __tablename__ = "incidents"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    site_code: Mapped[str] = mapped_column(String(50), index=True)
    incident_key: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[Optional[str]] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='OPEN') # OPEN, CLOSED
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    open_event_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    close_event_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('site_code', 'incident_key', 'opened_at', name='uq_incident_unique'),
    )

class EventCodeCatalog(Base):
    __tablename__ = "event_code_catalog"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20), default='info')
    alertable_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RuleCondition(Base):
    __tablename__ = "rule_conditions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20)) # SIMPLE_V3, SEQUENCE
    payload: Mapped[dict] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class EmailBookmark(Base):
    __tablename__ = "email_bookmarks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    folder: Mapped[str] = mapped_column(String(100), index=True, unique=True)
    last_uid: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# --- Phase 3 BIS : Admin Calibration Tool ---

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100)) # e.g., "CREATE_PROFILE", "REPROCESS"
    target_type: Mapped[str] = mapped_column(String(50)) # e.g., "PROFILE", "IMPORT"
    target_id: Mapped[Optional[str]] = mapped_column(String(50))
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ProfileRevision(Base):
    __tablename__ = "profile_revisions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("ingestion_profiles.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    profile_data: Mapped[dict] = mapped_column(JSONB)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ReprocessJob(Base):
    __tablename__ = "reprocess_jobs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default='PENDING') # PENDING, RUNNING, SUCCESS, FAILED
    scope: Mapped[dict] = mapped_column(JSONB) # {import_id: 1} or {range: [start, end], tenant_id: 2}
    audit_log_id: Mapped[int] = mapped_column(ForeignKey("audit_logs.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
