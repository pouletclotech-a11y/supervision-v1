import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.db.session import get_db
from app.db.models import Event, EventRuleHit, MonitoringProvider, ImportLog, SiteConnection, User
from app.schemas.response_models import ClientSiteSummaryOut, EventListOut, AlertListResponse, EventOut, AlertListItem
from app.auth.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{site_code}/summary", response_model=ClientSiteSummaryOut)
async def get_site_summary(
    site_code: str,
    days: int = Query(7, ge=1, le=90),
    events_page: int = 1,
    alerts_page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Phase 3: Aggregate KPIs and paginated timelines for a specific site.
    """
    # 1. Lookup site/client/provider
    site_stmt = (
        select(
            SiteConnection.code_site.label("site_code"),
            SiteConnection.client_name,
            MonitoringProvider.label.label("provider_name")
        )
        .outerjoin(MonitoringProvider, SiteConnection.provider_id == MonitoringProvider.id)
        .where(SiteConnection.code_site == site_code)
    )
    site_res = await db.execute(site_stmt)
    site_info = site_res.first()
    
    if not site_info:
        # Fallback to events if connection not found
        site_info = {"site_code": site_code, "client_name": "Unknown", "provider_name": "Unknown"}

    date_limit = datetime.utcnow() - timedelta(days=days)

    # 2. KPIs
    # Events Count
    count_evt = await db.execute(
        select(func.count(Event.id))
        .where(Event.site_code == site_code, Event.time >= date_limit)
    )
    events_count = count_evt.scalar() or 0

    # Last Event
    last_evt_stmt = await db.execute(
        select(func.max(Event.time))
        .where(Event.site_code == site_code)
    )
    last_event_at = last_evt_stmt.scalar()

    # Alerts Count
    count_alrt_stmt = (
        select(func.count(EventRuleHit.id))
        .join(Event, EventRuleHit.event_id == Event.id)
        .where(Event.site_code == site_code, EventRuleHit.created_at >= date_limit)
    )
    count_alrt = await db.execute(count_alrt_stmt)
    alerts_count = count_alrt.scalar() or 0

    # Last Alert
    last_alrt_stmt = await db.execute(
        select(func.max(EventRuleHit.created_at))
        .join(Event, EventRuleHit.event_id == Event.id)
        .where(Event.site_code == site_code)
    )
    last_alert_at = last_alrt_stmt.scalar()

    # Top Rules
    top_rules_stmt = (
        select(EventRuleHit.rule_name, func.count(EventRuleHit.id).label("count"))
        .join(Event, EventRuleHit.event_id == Event.id)
        .where(Event.site_code == site_code, EventRuleHit.created_at >= date_limit)
        .group_by(EventRuleHit.rule_name)
        .order_by(desc("count"))
        .limit(5)
    )
    top_rules_res = await db.execute(top_rules_stmt)
    top_rules = [{"rule_name": r.rule_name, "count": r.count} for r in top_rules_res.all()]

    # 3. Timelines (Paginated)
    # Events timeline
    evt_skip = (events_page - 1) * limit
    evt_stmt = (
        select(Event)
        .where(Event.site_code == site_code)
        .order_by(desc(Event.time))
        .offset(evt_skip)
        .limit(limit)
    )
    evt_res = await db.execute(evt_stmt)
    events_items = evt_res.scalars().all()
    
    # Total events for this site (not just the last N days for the list)
    total_evts_stmt = await db.execute(select(func.count(Event.id)).where(Event.site_code == site_code))
    total_events = total_evts_stmt.scalar() or 0

    # Alerts timeline
    alrt_skip = (alerts_page - 1) * limit
    alrt_stmt = (
        select(
            EventRuleHit.id.label("hit_id"),
            EventRuleHit.rule_id,
            EventRuleHit.rule_name,
            EventRuleHit.score,
            EventRuleHit.created_at,
            Event.site_code,
            Event.client_name,
            MonitoringProvider.label.label("provider_name"),
            Event.id.label("event_id"),
            Event.import_id
        )
        .join(Event, EventRuleHit.event_id == Event.id)
        .outerjoin(ImportLog, Event.import_id == ImportLog.id)
        .outerjoin(MonitoringProvider, ImportLog.provider_id == MonitoringProvider.id)
        .where(Event.site_code == site_code)
        .order_by(desc(EventRuleHit.created_at))
        .offset(alrt_skip)
        .limit(limit)
    )
    alrt_res = await db.execute(alrt_stmt)
    alerts_items = alrt_res.all()

    # Total alerts for this site
    total_alrts_stmt = await db.execute(
        select(func.count(EventRuleHit.id))
        .join(Event, EventRuleHit.event_id == Event.id)
        .where(Event.site_code == site_code)
    )
    total_alerts = total_alrts_stmt.scalar() or 0

    return {
        "site_code": site_info["site_code"] if isinstance(site_info, dict) else site_info.site_code,
        "client_name": site_info["client_name"] if isinstance(site_info, dict) else site_info.client_name,
        "provider_name": site_info["provider_name"] if isinstance(site_info, dict) else site_info.provider_name,
        "kpis": {
            "events_count": events_count,
            "alerts_count": alerts_count,
            "last_event_at": last_event_at,
            "last_alert_at": last_alert_at,
            "top_rules": top_rules
        },
        "timeline": {
            "events": {
                "events": events_items,
                "total": total_events
            },
            "alerts": {
                "items": alerts_items,
                "total": total_alerts,
                "page": alerts_page,
                "limit": limit
            }
        }
    }
