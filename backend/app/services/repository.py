import logging
import pytz
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from app.db.models import Event, Site, ImportLog, AlertRule, EventRuleHit, SiteConnection, RuleCondition
from app.ingestion.models import NormalizedEvent

logger = logging.getLogger("db-repository")

class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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
        log = ImportLog(
            filename=filename,
            file_hash=file_hash,
            status="PENDING",
            provider_id=provider_id,
            import_metadata=import_metadata or {},
            raw_payload=raw_payload,
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
            values["raw_payload"] = raw_payload
            
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
        
    async def record_rule_hit(self, event_id: int, rule_id: int, rule_name: str):
        """
        Record that a specific rule matched an event. 
        Idempotent via unique index (event_id, rule_id).
        """
        from sqlalchemy.dialects.postgresql import insert
        stmt = insert(EventRuleHit).values(
            event_id=event_id,
            rule_id=rule_id,
            rule_name=rule_name
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

    async def create_batch(self, events: List[NormalizedEvent], import_id: Optional[int] = None) -> int:
        if not events:
            return 0
            
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
        return len(db_events)
    
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
            if e.site_code and e.site_code not in site_map:
                site_map[e.site_code] = e.client_name
        
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
