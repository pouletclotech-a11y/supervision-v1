import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.ingestion.models import NormalizedEvent
from app.utils.text import normalize_text

logger = logging.getLogger("pdf-match-service")

class PdfMatchService:
    """
    Service for soft-matching events between Excel extracted data and PDF extracted data.
    """

    def calculate_match_report(
        self, 
        excel_events: List[NormalizedEvent], 
        pdf_events: List[NormalizedEvent],
        provider_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates a matching report between two sets of events.
        """
        if not excel_events:
            return {"status": "NO_EXCEL_DATA", "ratio": 0}
        if not pdf_events:
            return {"status": "NO_PDF_DATA", "ratio": 0}

        provider_code = provider_config.get("code", "UNKNOWN")
        ignore_case = provider_config.get("pdf_ignore_case", True)
        ignore_accents = provider_config.get("pdf_ignore_accents", True)

        # Strategy-based key building
        strategy = provider_config.get("pdf_match_strategy", "DEFAULT")
        
        def build_match_key(event: Any, source: str) -> str:
            # Common parts
            site = event.site_code or ""
            evt_dt = getattr(event, 'timestamp', getattr(event, 'time', None))
            dt = evt_dt.strftime("%Y-%m-%d %H:%M:%S") if evt_dt else ""
            
            if strategy == "SITE_TIME_CODE_ACTION":
                # Matches SPGO-like logic
                code = (event.raw_code or "").strip()
                action = (getattr(event, 'status', getattr(event, 'severity', "")) or "").strip().upper()
                return f"{site}|{dt}|{code}|{action}"
            elif strategy == "SITE_TIME_CODE_MSGPREFIX":
                # Matches CORS-like logic
                msg_norm = normalize_text(event.raw_message or "")
                # Extract code from message if not present
                code = event.raw_code or ""
                if not code:
                    match_code = re.search(r'\$?(\d{3,})', msg_norm)
                    if match_code: code = match_code.group(1)
                
                return f"{site}|{dt}|{code}|{msg_norm[:20]}"
            else:
                # Default fallback key: SITE_TIME_MSGPREFIX
                return f"{site}|{dt}|{normalize_text(event.raw_message or '')[:15]}"

        # Index PDF events
        pdf_keys = {}
        for p_evt in pdf_events:
            key = build_match_key(p_evt, "PDF")
            pdf_keys[key] = pdf_keys.get(key, 0) + 1

        matched_count = 0
        unmatched_samples = []

        for e_evt in excel_events:
            key = build_match_key(e_evt, "EXCEL")
            if key in pdf_keys and pdf_keys[key] > 0:
                matched_count += 1
                pdf_keys[key] -= 1
            else:
                # Try fallback: Check if strategy permits or defines fallback logic
                pass
                
                if len(unmatched_samples) < 10:
                    evt_dt = getattr(e_evt, 'timestamp', getattr(e_evt, 'time', None))
                    unmatched_samples.append({
                        "site": e_evt.site_code,
                        "time": evt_dt.isoformat() if evt_dt else None,
                        "msg": e_evt.raw_message[:50],
                        "key_attempted": key
                    })

        total_excel = len(excel_events)
        ratio = matched_count / total_excel if total_excel > 0 else 0
        
        status = "OK"
        if ratio < provider_config.get("pdf_critical_threshold", 0.7):
            status = "CRITICAL"
        elif ratio < provider_config.get("pdf_warning_threshold", 0.9):
            status = "WARNING"

        return {
            "status": status,
            "match_ratio": round(ratio, 4),
            "matched_count": matched_count,
            "excel_events_count": total_excel,
            "pdf_events_count": len(pdf_events),
            "unmatched_count": total_excel - matched_count,
            "unmatched_samples": unmatched_samples,
            "strategy_used": strategy,
            "thresholds": {
                "warning": provider_config.get("pdf_warning_threshold"),
                "critical": provider_config.get("pdf_critical_threshold")
            }
        }
