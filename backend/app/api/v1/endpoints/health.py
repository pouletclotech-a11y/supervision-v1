from datetime import datetime, date, timedelta
from typing import List, Any, Optional, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.redis import get_redis_client
from app.services.repository import EventRepository
from pydantic import BaseModel, Field
import json
import time
from app.db.models import User
from app.auth.deps import get_current_user
from app.services.canonical_service import get_canonical_label

router = APIRouter()

class IngestionHealthRow(BaseModel):
    provider_id: int
    provider_label: str
    provider_code: str
    total_imports: int
    total_emails: int
    total_xls: int
    total_pdf: int
    total_events: int
    integrity_numerator: int
    integrity_denominator: int
    avg_integrity: float
    missing_pdf: int
    health_status: str  # OK, WARNING, CRITICAL


class DailyReceiptStatus(BaseModel):
    provider_id: int
    provider_label: str
    provider_code: str
    received_today: int
    expected_today: int
    delta: int
    status: str  # OK, WARNING, CRITICAL


class IngestionHealthSummary(BaseModel):
    date: datetime
    summary: List[IngestionHealthRow]
    daily_receipt: List[DailyReceiptStatus]

class CatalogItemV4(BaseModel):
    code: Optional[str] = "N/A"
    canonical_label: str
    top_message: Optional[str]
    providers: str
    category: Optional[str]
    occurrences: int
    variant_count: int
    confidence_score: float
    last_seen: Optional[datetime]
    token_stats: Optional[List[Dict[str, Any]]] = None

class CatalogResponseV4(BaseModel):
    items: List[CatalogItemV4]
    total: int

class MessageVariant(BaseModel):
    message: Optional[str]
    occurrences: int
    last_seen: Optional[datetime]

class VariantResponse(BaseModel):
    code: str
    variants: List[MessageVariant]


@router.get("/ingestion", response_model=Dict[str, Any])
async def get_ingestion_health(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a summary of ingestion health for a given date range.
    Includes per-provider received vs expected files ratio.
    """
    # Robust date parsing to handle empty strings from frontend
    def parse_date(d_str: Optional[str], default_val: date) -> date:
        if not d_str: return default_val
        try:
            return date.fromisoformat(d_str)
        except:
            return default_val

    d_from = parse_date(date_from, date.today())
    d_to = parse_date(date_to, d_from) # Default to d_from if empty

    from app.core.config_loader import app_config

    repo = EventRepository(db)
    
    start_dt = datetime.combine(d_from, datetime.min.time())
    end_dt = datetime.combine(d_to, datetime.min.time()) + timedelta(days=1)

    raw_summary = await repo.get_ingestion_health_summary(start_dt, end_dt)

    import pytz
    paris_tz = pytz.timezone("Europe/Paris")
    now_paris = datetime.now(paris_tz)
    
    # Calculate number of days in range
    from app.services.health import calculate_expected_today
    
    num_days = (d_to - d_from).days + 1

    processed_summary = []
    daily_receipt: List[Dict] = []

    for row in raw_summary:
        # 1. Ingestion Quality Status (XLS/Events/Integrity)
        quality_status = "OK"
        if row["total_xls"] == 0 or row["total_events"] == 0:
            quality_status = "CRITICAL"
        elif row["avg_integrity"] < 95 or row["missing_pdf"] > 0:
            quality_status = "WARNING"

        row["health_status"] = quality_status
        processed_summary.append(row)

        # 2. Monitoring Connectivity Status (Received vs Expected)
        pcode = row["provider_code"]
        received = row["total_xls"]
        monitoring_enabled = row.get("monitoring_enabled", False)
        
        # Source of truth: DB (fallback to 0)
        expected_per_day = row.get("expected_emails_per_day", 0)
        interval_min = row.get("expected_interval_minutes", 1440)
        
        # Smart Expected So Far calculation
        if not monitoring_enabled or expected_per_day == 0:
            expected_so_far = 0
            receipt_status = "OK"
        else:
            # Full expected for past days in range
            full_days_count = num_days
            is_range_ending_today = (not d_to or d_to >= now_paris.date())
            
            if is_range_ending_today:
                full_days_count = num_days - 1
            
            expected_so_far = full_days_count * expected_per_day
            
            if is_range_ending_today:
                # Add progress-based expected for the current day
                # We use the interval to determine how many 'slots' have passed
                minutes_passed = now_paris.hour * 60 + now_paris.minute
                slots_passed = minutes_passed // interval_min
                
                # Max slots in a day based on total expected
                # If 4 emails/day and 360min interval, slots are 06:00, 12:00, 18:00, 00:00
                day_expected_so_far = min(slots_passed, expected_per_day)
                expected_so_far += day_expected_so_far

            # Status determination with tolerance
            if received >= expected_so_far:
                receipt_status = "OK"
            elif received >= expected_so_far - 1 and expected_so_far > 0:
                receipt_status = "WARNING" # Slightly behind
            else:
                receipt_status = "CRITICAL" # Significant delay

        daily_receipt.append({
            "provider_id": row["provider_id"],
            "provider_label": row["provider_label"],
            "provider_code": pcode,
            "received_today": received,
            "expected_today": int(expected_per_day * num_days), # Display full range target
            "expected_so_far": int(expected_so_far), # Extra info if needed
            "delta": int(received - expected_so_far),
            "status": receipt_status,
        })

    # Sort by status priority: CRITICAL > WARNING > OK
    status_priority = {"CRITICAL": 0, "WARNING": 1, "OK": 2}
    processed_summary.sort(key=lambda x: status_priority.get(x["health_status"], 99))
    daily_receipt.sort(key=lambda x: status_priority.get(x["status"], 99))

    return {
        "date": start_dt,
        "summary": processed_summary,
        "daily_receipt": daily_receipt,
    }


@router.get("/catalog", response_model=CatalogResponseV4)
async def get_event_catalog(
    q: Optional[str] = None,
    code: Optional[str] = None,
    provider_status: str = "active",
    mode: str = "COMPACT",
    sort_by: str = "occurrences",
    sort_dir: str = "desc",
    skip: int = 0,
    limit: int = 100,
    invariance: float = Query(1.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get the advanced V4 catalog (Compact or Detailed).
    COMPACT: Each code has a canonical label (aggregated).
    """
    repo = EventRepository(db)
    result = await repo.get_event_catalog_v4(
        q=q, 
        code=code, 
        provider_status=provider_status,
        mode=mode,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit, 
        offset=skip
    )
    
    items = result["items"]
    total = result["total"]
    
    enriched_items = []
    
    # Optimisation Massiv (P4) : Charger toutes les variantes en UNE seule requête
    if mode == "COMPACT" and items:
        item_codes = [row["code"] for row in items]
        all_variants = await repo.get_many_event_variants(item_codes, provider_status=provider_status)
        
        for row in items:
            code = row["code"]
            variants = all_variants.get(code, [])
            # Calcul du label canonique à partir des variantes chargées par lot
            analysis = get_canonical_label(variants, code=code, threshold=invariance)
            
            enriched_items.append({
                **row,
                "canonical_label": analysis["label"],
                "confidence_score": analysis["confidence"],
                "top_message": analysis["most_frequent"],
                "token_stats": analysis.get("token_stats", [])
            })
    else:
        # Mode détaillé ou liste vide
        for row in items:
            enriched_items.append({
                **row,
                "canonical_label": row.get("message", "N/A"),
                "confidence_score": 1.0,
                "top_message": row.get("message", "N/A"),
                "variant_count": 1
            })
            
    return {
        "items": enriched_items,
        "total": total
    }

@router.get("/catalog/variants/{code}", response_model=VariantResponse)
async def get_catalog_variants(
    code: str,
    provider_status: str = "active",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get all message variants for a specific alarm code (Drilldown).
    """
    repo = EventRepository(db)
    variants = await repo.get_event_variants(code, provider_status=provider_status)
    return {
        "code": code,
        "variants": variants
    }
# --- Phase 6: System Health ---

class SystemComponentStatus(BaseModel):
    status: str # OK, WARN, CRIT
    details: Optional[str] = None
    age_seconds: Optional[float] = None

class SystemHealthSchema(BaseModel):
    status: str
    database: SystemComponentStatus
    redis: SystemComponentStatus
    worker: SystemComponentStatus
    timestamp: datetime = Field(default_factory=datetime.now)

@router.get("", response_model=SystemHealthSchema)
async def get_system_health(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Check overall system health: Database, Redis, and Ingestion Worker.
    """
    health = {
        "status": "OK",
        "database": {"status": "OK"},
        "redis": {"status": "OK"},
        "worker": {"status": "OK"}
    }
    
    # 1. Database Check
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
    except Exception as e:
        health["database"] = {"status": "CRIT", "details": str(e)}
        health["status"] = "CRIT"
        
    # 2. Redis Check
    redis_client = None
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
    except Exception as e:
        health["redis"] = {"status": "CRIT", "details": str(e)}
        health["status"] = "CRIT"
        
    # 3. Worker Heartbeat Check
    if redis_client:
        try:
            hb_json = await redis_client.get("supervision:worker:heartbeat")
            if hb_json:
                hb_data = json.loads(hb_json)
                hb_ts = datetime.fromisoformat(hb_data["timestamp"])
                age = (datetime.now() - hb_ts).total_seconds()
                
                health["worker"]["age_seconds"] = age
                if age > 120:
                    health["worker"]["status"] = "CRIT"
                    health["worker"]["details"] = f"Heartbeat is too old: {age}s"
                    if health["status"] != "CRIT": health["status"] = "CRIT"
                elif age > 60:
                    health["worker"]["status"] = "WARN"
                    health["worker"]["details"] = f"Heartbeat is stale: {age}s"
                    if health["status"] == "OK": health["status"] = "WARN"
            else:
                health["worker"] = {"status": "CRIT", "details": "No heartbeat found in Redis"}
                health["status"] = "CRIT"
        except Exception as e:
            health["worker"] = {"status": "CRIT", "details": f"Error checking heartbeat: {e}"}
            health["status"] = "CRIT"
            
    return health
