import logging
import pytz
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from app.db.models import (
    Event, Site, ImportLog, AlertRule, EventRuleHit, SiteConnection, 
    RuleCondition, AuditLog, ProfileRevision, ReprocessJob, DBIngestionProfile,
    MonitoringProvider
)
from app.ingestion.models import NormalizedEvent
from app.ingestion.normalizer import normalize_site_code

logger = logging.getLogger("db-repository")

class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_monitoring_provider(self, provider_id: int) -> Optional[MonitoringProvider]:
        if not provider_id:
            return None
        stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_monitoring_provider_by_code(self, code: str) -> Optional[MonitoringProvider]:
        if not code:
            return None
        stmt = select(MonitoringProvider).where(MonitoringProvider.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_rules(self) -> List[AlertRule]:
        stmt = select(AlertRule).where(AlertRule.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_or_create_site(self, code_client: str, secondary_code: Optional[str] = None) -> Site:
        # Cache layer could go here if needed
        stmt = select(Site).where(Site.code_client == code_client)
        result = await self.session.execute(stmt)
        site = result.scalar_one_or_none()

        if not site:
            logger.warning(f"Unknown Site detected: {code_client}. Creating on the fly.")
            site = Site(
                code_client=code_client,
                secondary_code=secondary_code,
                name=f"Site {code_client}", # Fallback name
                status='UNKNOWN'
            )
            self.session.add(site)
            # Need flush to get ID
            await self.session.flush()
        
        return site

    async def get_import_by_hash(self, file_hash: str) -> Optional[ImportLog]:
        stmt = select(ImportLog).where(ImportLog.file_hash == file_hash).order_by(ImportLog.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_import_log(self, filename: str, file_hash: str = None, provider_id: int = None, import_metadata: dict = None, raw_payload: str = None) -> ImportLog:
        # User requested 8-32KB truncation
        truncated_payload = None
        if raw_payload:
            truncated_payload = raw_payload[:32768] # 32KB max
            
        log = ImportLog(
            filename=filename,
            file_hash=file_hash,
            status="PENDING",
            provider_id=provider_id,
            import_metadata=import_metadata or {},
            raw_payload=truncated_payload,
            created_at=datetime.utcnow()
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def update_import_log(self, import_id: int, status: str, events_count: int, duplicates_count: int, error_message: str = None, import_metadata: dict = None, raw_payload: str = None):
        values = {
            "status": status, 
            "events_count": events_count, 
            "duplicates_count": duplicates_count,
            "error_message": error_message
        }
        if import_metadata:
            values["import_metadata"] = import_metadata
        if raw_payload:
            values["raw_payload"] = raw_payload[:32768] # 32KB max
            
        stmt = (
            update(ImportLog)
            .where(ImportLog.id == import_id)
            .values(**values)
        )
        await self.session.execute(stmt)

    async def update_import_archive_info(self, import_id: int, archive_path: str, file_hash: str, archived_at: datetime):
        stmt = (
            update(ImportLog)
            .where(ImportLog.id == import_id)
            .values(
                archive_path=archive_path,
                file_hash=file_hash,
                archived_at=archived_at,
                archive_status="ARCHIVED"
            )
        )
        await self.session.execute(stmt)

    async def count_recent_matches(self, site_code: str, condition_type: str, value: str, window_seconds: int, reference_time: Optional[datetime] = None) -> int:
        from datetime import timedelta
        # Calculate cutoff time
        ref = reference_time or datetime.utcnow()
        cutoff = ref - timedelta(seconds=window_seconds)
        
        stmt = select(func.count(Event.id)).where(Event.time >= cutoff)
        
        # Upper bound: Don't count future events relative to reference (important for Replay)
        stmt = stmt.where(Event.time <= ref)
        
        # Site Filter (Direct column check)
        stmt = stmt.where(Event.site_code == site_code)
        
        if condition_type == 'SEVERITY':
             stmt = stmt.where(func.upper(Event.severity) == value.upper())
        elif condition_type == 'KEYWORD':
             stmt = stmt.where(Event.raw_message.ilike(f"%{value}%"))
             
        result = await self.session.execute(stmt)
        return result.scalar() or 0
        
    async def record_rule_hit(self, event_id: int, rule_id: int, rule_name: str, hit_metadata: Optional[dict] = None):
        """
        Record that a specific rule matched an event. 
        Idempotent via unique index (event_id, rule_id).
        """
        from sqlalchemy.dialects.postgresql import insert
        stmt = insert(EventRuleHit).values(
            event_id=event_id,
            rule_id=rule_id,
            rule_name=rule_name,
            hit_metadata=hit_metadata
        ).on_conflict_do_nothing(index_elements=['event_id', 'rule_id'])
        
        await self.session.execute(stmt)
        # Note: Do not commit here, handled by caller (e.g. at end of batch)
        
    async def get_rule_hits_for_events(self, event_ids: List[int]) -> Dict[int, List[Dict]]:
        """
        Fetch all triggered rules for a list of events.
        Returns map: event_id -> [{id, name}, ...]
        """
        if not event_ids: return {}
        
        stmt = select(EventRuleHit).where(EventRuleHit.event_id.in_(event_ids))
        result = await self.session.execute(stmt)
        hits = result.scalars().all()
        
        mapping = {eid: [] for eid in event_ids}
        for h in hits:
            mapping[h.event_id].append({
                "id": h.rule_id, 
                "name": h.rule_name,
                "matched_at": h.created_at
            })
        return mapping

    async def get_rule_conditions_by_codes(self, codes: List[str]) -> Dict[str, RuleCondition]:
        """Fetches a map of rule conditions by their unique codes."""
        if not codes:
            return {}
        stmt = select(RuleCondition).where(RuleCondition.code.in_(codes)).where(RuleCondition.is_active == True)
        result = await self.session.execute(stmt)
        conditions = result.scalars().all()
        return {c.code: c for c in conditions}

    async def count_v3_matches(
        self,
        site_code: str,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        days: int = 1,
        open_only: bool = False,
        reference_time: Optional[datetime] = None
    ) -> int:
        """
        Alerting V3: Counts occurrences in a sliding window (days).
        If open_only is True, only counts events that are currently part of an OPEN incident.
        """
        ref = reference_time or datetime.utcnow()
        start_date = ref - timedelta(days=days)
        
        if open_only:
            # Join Incidents with their opening Events
            from app.db.models import Incident
            stmt = (
                select(func.count(Incident.id))
                .join(Event, Event.id == Incident.open_event_id)
                .where(Incident.site_code == site_code)
                .where(Incident.status == 'OPEN')
                .where(Incident.opened_at >= start_date)
                .where(Incident.opened_at <= ref)
            )
            # Apply filters on the opening event
            if category:
                stmt = stmt.where(Event.category == category)
            if keyword:
                stmt = stmt.where(Event.raw_message.ilike(f"%{keyword}%"))
            
            # Action constraint (APPARITION only for V3 counting)
            stmt = stmt.where(Event.normalized_type == 'APPARITION')
        else:
            # Standard event count
            stmt = (
                select(func.count(Event.id))
                .where(Event.site_code == site_code)
                .where(Event.time >= start_date)
                .where(Event.time <= ref)
                .where(Event.normalized_type == 'APPARITION')
            )
            if category:
                stmt = stmt.where(Event.category == category)
            if keyword:
                stmt = stmt.where(Event.raw_message.ilike(f"%{keyword}%"))
                
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def find_sequence_match(
        self,
        site_code: str,
        a_cat: Optional[str],
        a_key: Optional[str],
        b_cat: Optional[str],
        b_key: Optional[str],
        max_delay_seconds: int,
        lookback_days: int = 2,
        reference_time: Optional[datetime] = None
    ) -> Optional[dict]:
        """
        Step 6: Finds if an event A is followed by event B within max_delay_seconds.
        """
        ref = reference_time or datetime.utcnow()
        lookback_start = ref - timedelta(days=lookback_days)
        
        # We manually build the query to handle the complex self-join and filters
        from sqlalchemy.orm import aliased
        from sqlalchemy import and_
        EvA = aliased(Event)
        EvB = aliased(Event)
        
        stmt = (
            select(
                EvA.id.label("a_id"), 
                EvB.id.label("b_id"), 
                EvA.time.label("a_time"), 
                EvB.time.label("b_time")
            )
            .join(EvB, EvA.site_code == EvB.site_code)
            .where(EvA.site_code == site_code)
            .where(EvA.normalized_type == 'APPARITION')
            .where(EvB.normalized_type == 'APPARITION')
            .where(EvA.time >= lookback_start)
            .where(EvA.time <= ref)
            .where(EvB.time > EvA.time)
            .where(EvB.time <= EvA.time + timedelta(seconds=max_delay_seconds))
        )
        
        # A Filters
        if a_cat:
            stmt = stmt.where(EvA.category == a_cat)
        if a_key:
            stmt = stmt.where(EvA.raw_message.ilike(f"%{a_key}%"))
            
        # B Filters
        if b_cat:
            stmt = stmt.where(EvB.category == b_cat)
        if b_key:
            stmt = stmt.where(EvB.raw_message.ilike(f"%{b_key}%"))
            
        # Determinism
        stmt = stmt.order_by(EvA.time.asc(), EvA.id.asc(), EvB.time.asc(), EvB.id.asc()).limit(1)
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if row:
            return {
                "a_id": row.a_id,
                "b_id": row.b_id,
                "a_time": row.a_time,
                "b_time": row.b_time
            }
        return None

    async def create_batch(self, events: List[NormalizedEvent], import_id: Optional[int] = None) -> List[Event]:
        if not events:
            return []
            
        # 1. Resolve Site UUIDs
        # Optimization: distinct sites only
        unique_site_codes = {e.site_code: e.secondary_code for e in events}
        site_map = {} # Code -> ID
        
        for code, sec in unique_site_codes.items():
            site = await self.get_or_create_site(code, sec)
            site_map[code] = site.id
            
        # 2. Build Event Models
        db_events = []
        for e in events:
            db_events.append(Event(
                time=e.timestamp,
                site_id=site_map.get(e.site_code),
                site_code=e.site_code,
                client_name=e.client_name,
                weekday_label=e.weekday_label,
                # zone_id handled later
                import_id=import_id,
                raw_message=e.raw_message,
                normalized_message=e.normalized_message,
                raw_code=e.raw_code,
                normalized_type=e.normalized_type or e.event_type, # Prefer normalized
                sub_type=e.sub_type,
                severity=e.status, 
                zone_label=e.zone_label,
                event_metadata=e.metadata, # Pydantic model has 'metadata', DB has 'event_metadata'
                source_file=e.source_file,
                dup_count=e.dup_count or 0,
                raw_data=e.raw_data,
                category=e.category,
                alertable_default=e.alertable_default
            ))
            
        self.session.add_all(db_events)
        return db_events
    
    async def populate_site_connections(
        self, 
        events: List[NormalizedEvent], 
        provider_id: int, 
        import_id: int
    ) -> int:
        """
        Phase 3: Populate site_connections table with unique code_site per provider.
        Uses INSERT ON CONFLICT DO NOTHING for idempotency.
        Returns count of newly added connections.
        """
        if not events or not provider_id:
            return 0
        
        # Extract unique code_site -> client_name mapping
        site_map = {}
        for e in events:
            norm_code = normalize_site_code(e.site_code)
            if norm_code and norm_code not in site_map:
                site_map[norm_code] = e.client_name
        
        if not site_map:
            return 0
        
        # Build insert statements with ON CONFLICT DO NOTHING
        added = 0
        for code_site, client_name in site_map.items():
            stmt = insert(SiteConnection).values(
                provider_id=provider_id,
                code_site=code_site,
                client_name=client_name,
                first_import_id=import_id
            ).on_conflict_do_nothing(
                index_elements=['provider_id', 'code_site']
            )
            result = await self.session.execute(stmt)
            # rowcount tells us if insert happened (1) or conflict (0)
            if result.rowcount > 0:
                added += 1
        
        logger.info(f"Populated site_connections: {added} new, {len(site_map) - added} existing (provider={provider_id})")
        return added

    async def upsert_site_connection(self, provider_id: int, code_site: str, client_name: str, seen_at: datetime):
        """
        Idempotent upsert for SiteConnection. Increment total_events and update last_seen_at.
        Uses SELECT ... FOR UPDATE pattern for strict transactional safety (Roadmap 4).
        """
        code_site = normalize_site_code(code_site)
        
        # 1. SELECT FOR UPDATE to lock the row (or the gap if not exist? Postgres gap locks are complex, but this is the requested pattern)
        stmt = (
            select(SiteConnection)
            .where(SiteConnection.provider_id == provider_id)
            .where(SiteConnection.code_site == code_site)
            .with_for_update()
        )
        
        result = await self.session.execute(stmt)
        connection = result.scalar_one_or_none()
        
        if connection:
            # 2. UPDATE existing
            connection.last_seen_at = seen_at
            connection.total_events = (connection.total_events or 0) + 1
            if client_name:
                connection.client_name = client_name
        else:
            # 3. INSERT new
            new_conn = SiteConnection(
                provider_id=provider_id,
                code_site=code_site,
                client_name=client_name,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                total_events=1
            )
            self.session.add(new_conn)
            # Flush to ensure it's in the DB within the transaction
            await self.session.flush()

    async def get_business_summary(self):
        """Totals by provider"""
        stmt = (
            select(
                MonitoringProvider.label,
                MonitoringProvider.code,
                func.count(SiteConnection.id).label("total_sites"),
                func.sum(SiteConnection.total_events).label("total_events")
            )
            .join(SiteConnection, MonitoringProvider.id == SiteConnection.provider_id, isouter=True)
            .group_by(MonitoringProvider.id)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def update_provider_last_import(self, provider_id: int, timestamp: datetime):
        """Update last_successful_import_at for health monitoring."""
        if not provider_id:
            return
        stmt = update(MonitoringProvider).where(MonitoringProvider.id == provider_id).values(
            last_successful_import_at=timestamp
        )
        await self.session.execute(stmt)

    async def get_ingestion_health_summary(self, target_date: datetime) -> List[Dict]:
        """
        Aggregates ingestion metrics per provider for a given date.
        """
        from sqlalchemy import cast, Numeric, func as f
        
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        # Labels subquery
        provider_stmt = select(MonitoringProvider.id, MonitoringProvider.label, MonitoringProvider.code)
        providers_res = await self.session.execute(provider_stmt)
        providers_map = {p.id: {"label": p.label, "code": p.code} for p in providers_res.all()}

        # Aggregation query
        stmt = (
            select(
                ImportLog.provider_id,
                func.count(ImportLog.id).label("total_imports"),
                func.count(func.distinct(ImportLog.source_message_id)).label("total_emails"),
                func.count().filter(ImportLog.filename.ilike("%.xls%")).label("total_xls"),
                func.count().filter(ImportLog.filename.ilike("%.pdf%")).label("total_pdf"),
                func.sum(ImportLog.events_count).label("total_events"),
                func.avg(
                    cast(
                        func.nullif(
                            func.jsonb_extract_path_text(ImportLog.import_metadata, 'integrity_check', 'match_pct'),
                            ''
                        ),
                        Numeric
                    )
                ).label("avg_integrity"),
                func.count().filter(
                    ImportLog.filename.ilike("%.xls%"),
                    func.jsonb_extract_path_text(ImportLog.import_metadata, 'pdf_support').is_(None)
                ).label("missing_pdf")
            )
            .where(
                ImportLog.created_at >= start_date,
                ImportLog.created_at < end_date
            )
            .group_by(ImportLog.provider_id)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        summary = []
        for row in rows:
            p_info = providers_map.get(row.provider_id, {"label": f"Unknown ({row.provider_id})", "code": "UNKNOWN"})
            
            data = {
                "provider_id": row.provider_id,
                "provider_label": p_info["label"],
                "provider_code": p_info["code"],
                "total_imports": row.total_imports,
                "total_emails": row.total_emails,
                "total_xls": row.total_xls,
                "total_pdf": row.total_pdf,
                "total_events": int(row.total_events or 0),
                "avg_integrity": float(row.avg_integrity or 0),
                "missing_pdf": row.missing_pdf
            }
            summary.append(data)

        return summary

    async def get_rule_trigger_summary(self, target_date: datetime) -> List[Dict]:
        """
        Agrège les déclenchements de règles par règle et par provider pour une date donnée.
        """
        from sqlalchemy import distinct
        
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        # On rejoint event_rule_hits -> events -> imports pour avoir le provider_id
        stmt = (
            select(
                EventRuleHit.rule_id,
                EventRuleHit.rule_name,
                ImportLog.provider_id,
                func.count(EventRuleHit.id).label("total_triggers"),
                func.count(func.distinct(Event.site_code)).label("distinct_sites"),
                func.max(EventRuleHit.created_at).label("last_trigger_at")
            )
            .join(Event, EventRuleHit.event_id == Event.id)
            .join(ImportLog, Event.import_id == ImportLog.id)
            .where(
                EventRuleHit.created_at >= start_date,
                EventRuleHit.created_at < end_date
            )
            .group_by(EventRuleHit.rule_id, EventRuleHit.rule_name, ImportLog.provider_id)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        # Récupération des labels de providers pour enrichir
        provider_stmt = select(MonitoringProvider.id, MonitoringProvider.label)
        p_res = await self.session.execute(provider_stmt)
        p_map = {p.id: p.label for p in p_res.all()}

        summary = []
        for row in rows:
            summary.append({
                "rule_id": row.rule_id,
                "rule_name": row.rule_name,
                "provider_id": row.provider_id,
                "provider_label": p_map.get(row.provider_id, f"Unknown ({row.provider_id})"),
                "total_triggers": row.total_triggers,
                "distinct_sites": row.distinct_sites,
                "last_trigger_at": row.last_trigger_at
            })
            
        return summary

class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_unmatched_imports(self, skip: int = 0, limit: int = 20, status: Optional[str] = None) -> List[ImportLog]:
        error_statuses = ["PROFILE_NOT_CONFIDENT", "NO_PROFILE_MATCH", "PARSER_FAILED", "VALIDATION_REJECTED", "ERROR"]
        
        stmt = select(ImportLog)
        if status:
            stmt = stmt.where(ImportLog.status == status)
        else:
            stmt = stmt.where(ImportLog.status.in_(error_statuses))
            
        stmt = stmt.order_by(ImportLog.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_audit_log(self, user_id: int, action: str, target_type: str, target_id: str = None, payload: dict = None) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def create_profile_revision(self, profile_id: int, version: int, data: dict, user_id: int, reason: str = None) -> ProfileRevision:
        rev = ProfileRevision(
            profile_id=profile_id,
            version_number=version,
            profile_data=data,
            change_reason=reason,
            updated_by=user_id
        )
        self.session.add(rev)
        return rev

    async def create_reprocess_job(self, scope: dict, audit_log_id: int) -> ReprocessJob:
        job = ReprocessJob(
            status="PENDING",
            scope=scope,
            audit_log_id=audit_log_id
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_reprocess_job(self, job_id: int, status: str, error_message: str = None):
        values = {"status": status}
        if status in ["SUCCESS", "FAILED"]:
            values["ended_at"] = datetime.utcnow()
        if error_message:
            values["error_message"] = error_message
            
        stmt = update(ReprocessJob).where(ReprocessJob.id == job_id).values(**values)
        await self.session.execute(stmt)

    async def delete_import_data(self, import_id: int):
        """
        Purges all data related to an import (Events, Rule Hits, Incidents) 
        and resets the ImportLog for reprocessing.
        """
        from sqlalchemy import delete
        from app.db.models import Incident, Event, EventRuleHit, ImportLog
        
        # 1. Delete EventRuleHit
        hit_stmt = delete(EventRuleHit).where(EventRuleHit.event_id.in_(
            select(Event.id).where(Event.import_id == import_id)
        ))
        await self.session.execute(hit_stmt)
        
        # 2. Delete Incidents
        inc_stmt = delete(Incident).where((Incident.open_event_id.in_(
            select(Event.id).where(Event.import_id == import_id)
        )) | (Incident.close_event_id.in_(
            select(Event.id).where(Event.import_id == import_id)
        )))
        await self.session.execute(inc_stmt)
        
        # 3. Delete Events
        evt_stmt = delete(Event).where(Event.import_id == import_id)
        await self.session.execute(evt_stmt)
        
        # 4. Reset ImportLog status
        log_stmt = update(ImportLog).where(ImportLog.id == import_id).values(
            status="PENDING",
            events_count=0,
            duplicates_count=0,
            error_message=None
        )
        await self.session.execute(log_stmt)

    async def get_providers_health(self) -> List[dict]:
        """Calculates health status for all active providers."""
        # 1. Get all active providers
        stmt = select(MonitoringProvider).where(MonitoringProvider.is_active == True)
        result = await self.session.execute(stmt)
        providers = result.scalars().all()

        # 2. Get import counts in last 24h
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        import_stmt = (
            select(ImportLog.provider_id, func.count(ImportLog.id).label("count"))
            .where(ImportLog.created_at >= yesterday)
            .where(ImportLog.status == "SUCCESS")
            .group_by(ImportLog.provider_id)
        )
        import_result = await self.session.execute(import_stmt)
        import_counts = {p_id: count for p_id, count in import_result.all() if p_id}

        # 3. Composite health logic
        health_reports = []
        
        for p in providers:
            received = import_counts.get(p.id, 0)
            expected = p.expected_emails_per_day
            
            completion_rate = None
            if expected > 0:
                completion_rate = received / expected
            
            # Default Status
            status = "OK"
            
            if not p.monitoring_enabled and expected == 0:
                status = "UNCONFIGURED"
            elif p.monitoring_enabled:
                if not p.last_successful_import_at:
                    status = "SILENT"
                else:
                    last_import = p.last_successful_import_at
                    if last_import.tzinfo is None:
                        last_import = last_import.replace(tzinfo=timezone.utc)
                        
                    delta_min = (now - last_import).total_seconds() / 60
                    if delta_min > p.silence_threshold_minutes:
                        status = "SILENT"
                    elif expected > 0 and received < expected:
                        status = "LATE"
            elif expected > 0 and received < expected:
                status = "LATE"

            health_reports.append({
                "id": p.id,
                "code": p.code,
                "label": p.label,
                "status": status,
                "received_24h": received,
                "expected_24h": expected,
                "completion_rate": completion_rate,
                "last_successful_import_at": p.last_successful_import_at,
                "ui_color": p.ui_color
            })
            
        return health_reports

    async def get_active_alerts(self, skip: int = 0, limit: int = 100) -> List[dict]:
        """
        Retrieves currently active alerts (Latest Hit > Latest Disparition).
        """
        # Using a raw SQL approach for complex grouping/joining logic
        # We group by site_code, rule_name, and zone_id (from metadata)
        sql = """
        WITH latest_hits AS (
            SELECT 
                erh.rule_name,
                e.site_code,
                erh.hit_metadata->>'zone_id' as zone_id,
                MAX(e.time) as last_hit_time,
                MIN(e.time) as first_hit_time,
                MAX(e.id) as last_event_id,
                COUNT(erh.id) as count_hits
            FROM event_rule_hits erh
            JOIN events e ON e.id = erh.event_id
            GROUP BY 1, 2, 3
        ),
        latest_disps AS (
            SELECT 
                site_code,
                zone_id::text as zone_id,
                MAX(time) as last_disp_time
            FROM events
            WHERE normalized_type LIKE '%%DISPARITION%%'
            GROUP BY 1, 2
        )
        SELECT 
            h.rule_name,
            'ACTIVE' as status,
            h.site_code,
            h.first_hit_time as first_seen,
            h.last_hit_time as last_seen,
            h.count_hits,
            h.last_event_id as recent_event_id,
            p.code as provider_code
        FROM latest_hits h
        LEFT JOIN latest_disps d ON d.site_code = h.site_code 
            AND (d.zone_id = h.zone_id OR (d.zone_id IS NULL AND h.zone_id IS NULL))
        JOIN site_connections s ON s.code_site = h.site_code
        JOIN monitoring_providers p ON p.id = s.provider_id
        WHERE d.last_disp_time IS NULL OR d.last_disp_time < h.last_hit_time
        ORDER BY h.last_hit_time DESC
        OFFSET :skip LIMIT :limit
        """
        from sqlalchemy import text
        result = await self.session.execute(text(sql), {"skip": skip, "limit": limit})
        return [dict(row._mapping) for row in result]

    async def get_archived_alerts(self, days: int = 7, skip: int = 0, limit: int = 100) -> List[dict]:
        """
        Retrieves archived alerts (Disparition occurred after the hit).
        """
        sql = """
        WITH latest_hits AS (
            SELECT 
                erh.rule_name,
                e.site_code,
                erh.hit_metadata->>'zone_id' as zone_id,
                MAX(e.time) as last_hit_time,
                MIN(e.time) as first_hit_time,
                MAX(e.id) as last_event_id,
                COUNT(erh.id) as count_hits
            FROM event_rule_hits erh
            JOIN events e ON e.id = erh.event_id
            GROUP BY 1, 2, 3
        ),
        latest_disps AS (
            SELECT 
                site_code,
                zone_id::text as zone_id,
                MAX(time) as last_disp_time
            FROM events
            WHERE normalized_type LIKE '%%DISPARITION%%'
            GROUP BY 1, 2
        )
        SELECT 
            h.rule_name,
            'ARCHIVED' as status,
            h.site_code,
            h.first_hit_time as first_seen,
            h.last_hit_time as last_seen,
            d.last_disp_time as closed_at,
            h.count_hits,
            h.last_event_id as recent_event_id,
            p.code as provider_code
        FROM latest_hits h
        JOIN latest_disps d ON d.site_code = h.site_code 
            AND (d.zone_id = h.zone_id OR (d.zone_id IS NULL AND h.zone_id IS NULL))
        JOIN site_connections s ON s.code_site = h.site_code
        JOIN monitoring_providers p ON p.id = s.provider_id
        WHERE d.last_disp_time >= h.last_hit_time
          AND d.last_disp_time >= NOW() - INTERVAL '1 day' * :days
        ORDER BY d.last_disp_time DESC
        OFFSET :skip LIMIT :limit
        """
        from sqlalchemy import text
        result = await self.session.execute(text(sql), {"days": days, "skip": skip, "limit": limit})
        return [dict(row._mapping) for row in result]

    async def get_client_report(self, site_code: str, days: int = 30) -> dict:
        """Consolidated report for a specific client."""
        # 1. Fetch Summary KPIs
        # 2. Fetch Active/Archived Alerts for this site
        # 3. Fetch Site Info
        
        # Site Info
        stmt_site = select(SiteConnection, MonitoringProvider.label).join(
            MonitoringProvider, SiteConnection.provider_id == MonitoringProvider.id
        ).where(SiteConnection.code_site == site_code)
        res_site = await self.session.execute(stmt_site)
        site_data = res_site.first()
        if not site_data:
            return None
        
        site_obj, provider_label = site_data
        
        # Summary
        sql_summary = """
        SELECT 
            COUNT(*) as total_events,
            (SELECT COUNT(DISTINCT rule_name) FROM event_rule_hits erh JOIN events e ON e.id = erh.event_id WHERE e.site_code = :site_code) as total_alerts
        FROM events 
        WHERE site_code = :site_code AND time >= NOW() - INTERVAL '1 day' * :days
        """
        from sqlalchemy import text
        res_summary = await self.session.execute(text(sql_summary), {"site_code": site_code, "days": days})
        summary_row = res_summary.first()
        
        # Alerts (Active + Archived for this site)
        # Re-using logic from get_active/archived but filtered by site
        active = await self.get_active_alerts_by_site(site_code)
        archived = await self.get_archived_alerts_by_site(site_code, days)
        
        # Timeline
        stmt_timeline = select(Event).where(
            Event.site_code == site_code
        ).order_by(Event.time.desc()).limit(500)
        res_timeline = await self.session.execute(stmt_timeline)
        timeline = res_timeline.scalars().all()
        
        # Enrich timeline with rule info
        event_ids = [e.id for e in timeline]
        hits_map = await self.get_rule_hits_for_events(event_ids)
        
        # Format timeline for Pydantic (EventOut compatibility)
        # Note: EventOut expects triggered_rules: List[TriggeredRuleSummary]
        # Our repository already has Event models, but we need to attach triggered_rules
        for evt in timeline:
            evt.triggered_rules = hits_map.get(evt.id, [])

        return {
            "site_code": site_code,
            "provider": provider_label,
            "summary": {
                "total_events": summary_row.total_events if summary_row else 0,
                "total_alerts": summary_row.total_alerts if summary_row else 0,
                "active_alerts": len(active),
                "archived_alerts": len(archived)
            },
            "alerts": active + archived,
            "timeline": timeline
        }

    async def get_active_alerts_by_site(self, site_code: str) -> List[dict]:
        sql = """
        WITH latest_hits AS (
            SELECT 
                erh.rule_name,
                e.site_code,
                erh.hit_metadata->>'zone_id' as zone_id,
                MAX(e.time) as last_hit_time,
                MIN(e.time) as first_hit_time,
                MAX(e.id) as last_event_id,
                COUNT(erh.id) as count_hits
            FROM event_rule_hits erh
            JOIN events e ON e.id = erh.event_id
            WHERE e.site_code = :site_code
            GROUP BY 1, 2, 3
        ),
        latest_disps AS (
            SELECT 
                site_code,
                zone_id::text as zone_id,
                MAX(time) as last_disp_time
            FROM events
            WHERE site_code = :site_code AND normalized_type LIKE '%%DISPARITION%%'
            GROUP BY 1, 2
        )
        SELECT 
            h.rule_name,
            'ACTIVE' as status,
            h.site_code,
            h.first_hit_time as first_seen,
            h.last_hit_time as last_seen,
            h.count_hits,
            h.last_event_id as recent_event_id
        FROM latest_hits h
        LEFT JOIN latest_disps d ON d.site_code = h.site_code 
            AND (d.zone_id = h.zone_id OR (d.zone_id IS NULL AND h.zone_id IS NULL))
        WHERE d.last_disp_time IS NULL OR d.last_disp_time < h.last_hit_time
        """
        from sqlalchemy import text
        result = await self.session.execute(text(sql), {"site_code": site_code})
        return [dict(row._mapping) for row in result]

    async def get_archived_alerts_by_site(self, site_code: str, days: int) -> List[dict]:
        sql = """
        WITH latest_hits AS (
            SELECT 
                erh.rule_name,
                e.site_code,
                erh.hit_metadata->>'zone_id' as zone_id,
                MAX(e.time) as last_hit_time,
                MIN(e.time) as first_hit_time,
                MAX(e.id) as last_event_id,
                COUNT(erh.id) as count_hits
            FROM event_rule_hits erh
            JOIN events e ON e.id = erh.event_id
            WHERE e.site_code = :site_code
            GROUP BY 1, 2, 3
        ),
        latest_disps AS (
            SELECT 
                site_code,
                zone_id::text as zone_id,
                MAX(time) as last_disp_time
            FROM events
            WHERE site_code = :site_code AND normalized_type LIKE '%%DISPARITION%%'
            GROUP BY 1, 2
        )
        SELECT 
            h.rule_name,
            'ARCHIVED' as status,
            h.site_code,
            h.first_hit_time as first_seen,
            h.last_hit_time as last_seen,
            d.last_disp_time as closed_at,
            h.count_hits,
            h.last_event_id as recent_event_id
        FROM latest_hits h
        JOIN latest_disps d ON d.site_code = h.site_code 
            AND (d.zone_id = h.zone_id OR (d.zone_id IS NULL AND h.zone_id IS NULL))
        WHERE d.last_disp_time >= h.last_hit_time
          AND d.last_disp_time >= NOW() - INTERVAL '1 day' * :days
        """
        from sqlalchemy import text
        result = await self.session.execute(text(sql), {"site_code": site_code, "days": days})
        return [dict(row._mapping) for row in result]
