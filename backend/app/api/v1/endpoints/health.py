from datetime import datetime
from typing import List, Any, Optional, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.repository import EventRepository
from pydantic import BaseModel

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


@router.get("/ingestion-summary", response_model=IngestionHealthSummary)
async def get_ingestion_summary(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a summary of ingestion health for today.
    Includes per-provider received vs expected files ratio.
    """
    from app.core.config_loader import app_config

    repo = EventRepository(db)
    today = datetime.now()
    raw_summary = await repo.get_ingestion_health_summary(today)

    # Config expected_files_per_day
    ingestion_cfg = app_config.get('monitoring', {}).get('ingestion', {})
    expected_cfg = ingestion_cfg.get('expected_files_per_day', {})
    default_expected = expected_cfg.get('default', 0)
    by_provider = expected_cfg.get('by_provider', {}) or {}

    processed_summary = []
    daily_receipt: List[Dict] = []

    for row in raw_summary:
        # Business Logic for Health Status
        status = "OK"
        if row["total_xls"] == 0 or row["total_events"] == 0:
            status = "CRITICAL"
        elif row["avg_integrity"] < 95 or row["missing_pdf"] > 0:
            status = "WARNING"

        row["health_status"] = status
        processed_summary.append(row)

        # Received vs Expected
        pcode = row["provider_code"]
        received = row["total_xls"]  # XLS files = real ingestion
        expected = by_provider.get(pcode, default_expected)

        if expected == 0:
            receipt_status = "OK"   # monitoring désactivé => pas d'alerte
        elif received == expected:
            receipt_status = "OK"    # VERT
        elif received < expected:
            receipt_status = "CRITICAL" # ROUGE
        else:
            receipt_status = "WARNING"  # ORANGE (over-receiving)

        daily_receipt.append({
            "provider_id": row["provider_id"],
            "provider_label": row["provider_label"],
            "provider_code": pcode,
            "received_today": received,
            "expected_today": expected,
            "delta": received - expected,
            "status": receipt_status,
        })

    # Sort by status priority: CRITICAL > WARNING > OK
    status_priority = {"CRITICAL": 0, "WARNING": 1, "OK": 2}
    processed_summary.sort(key=lambda x: status_priority.get(x["health_status"], 99))
    daily_receipt.sort(key=lambda x: status_priority.get(x["status"], 99))

    return {
        "date": today,
        "summary": processed_summary,
        "daily_receipt": daily_receipt,
    }
