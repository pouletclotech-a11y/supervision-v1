import re
import csv
import logging
from typing import List, Optional
from datetime import datetime
from app.parsers.base import BaseParser
from app.ingestion.models import NormalizedEvent
from app.utils.text import clean_excel_value
from app.ingestion.normalizer import normalize_site_code

logger = logging.getLogger("tsv-parser")

class TsvParser(BaseParser):
    """
    Parser for Tab-Separated Values files (often disguised as .xls).
    Supports latin-1 encoding and Excel formula cleanup.
    """

    def supported_extensions(self) -> List[str]:
        return ['.xls', '.tsv']

    def parse(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        logger.info(f"[TSV_PARSE_START] file={file_path}")
        events = []
        
        mapping = parser_config.get("mapping", {}) if parser_config else {}
        action_config = parser_config.get("action_config", {}) if parser_config else {}
        
        # Context for inheritance
        ctx_site_code = None
        ctx_site_code_raw = None
        
        try:
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                lines = f.readlines()
            
            # Manual split to handle inconsistent column counts
            raw_data = [line.strip().split('\t') for line in lines]
            
            for row_idx, raw_row in enumerate(raw_data, 1):
                if not raw_row or (len(raw_row) == 1 and not raw_row[0]):
                    continue
                
                # Clean row elements (remove ="...")
                clean_row = [clean_excel_value(c) for c in raw_row]
                
                # 1. Site Code Propagation
                # If mapping says site_code is "row_start" or if first col looks like a code
                potential_site = clean_row[0].strip()
                if len(potential_site) >= 5 and any(c.isdigit() for c in potential_site):
                    # Check if it's a new site block
                    if re.match(r'^\d{5,8}$', potential_site) or (potential_site.startswith('C-') and len(potential_site) > 5):
                        ctx_site_code_raw = potential_site
                        ctx_site_code = normalize_site_code(potential_site)
                        # If this row ONLY has site info, skip to next
                        if len(clean_row) < 3:
                            continue

                # 2. Extract Data using Mapping (Indices start at 0)
                # Helper to get by index or letter
                def get_val(key):
                    idx_val = mapping.get(key)
                    if idx_val is None: return None
                    if isinstance(idx_val, str) and len(idx_val) == 1:
                        # Convert A -> 0, B -> 1
                        idx = ord(idx_val.upper()) - ord('A')
                    else:
                        idx = int(idx_val)
                    return clean_row[idx] if idx < len(clean_row) else None

                raw_dt = get_val("date_time")
                if not raw_dt:
                    # Try split date/time
                    d = get_val("date")
                    t = get_val("time")
                    if d and t:
                        raw_dt = f"{d} {t}"
                
                if not raw_dt:
                    if row_idx <= 20:
                        logger.debug(f"[ROW_SKIPPED] row={row_idx} reason=MISSING_DATE_TIME")
                    continue

                # Parse Date
                try:
                    # Support common formats found in logs
                    dt = None
                    for fmt in ["%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%y %H:%M:%S"]:
                        try:
                            dt = datetime.strptime(raw_dt, fmt)
                            break
                        except: continue
                    
                    if not dt:
                        raise ValueError(f"Unknown date format: {raw_dt}")
                except Exception as e:
                    if row_idx <= 20: logger.warning(f"[ROW_SKIPPED] row={row_idx} reason=DATE_PARSE_ERROR val={raw_dt}")
                    continue

                # 3. Message / Code
                msg = get_val("message") or ""
                code = get_val("raw_code") or ""
                
                # 4. Action Derivation
                action = "INFO"
                mode = action_config.get("mode", "NONE")
                if mode == "COLUMN":
                    action = get_val("action") or "INFO"
                elif mode == "REGEX_DERIVE":
                    source = msg if action_config.get("source_field") == "message" else code
                    # Apparition
                    for reg in action_config.get("regex_app", []):
                        if re.search(reg, source, re.IGNORECASE):
                            action = "APPARITION"
                            break
                    # Disparition
                    if action == "INFO":
                        for reg in action_config.get("regex_dis", []):
                            if re.search(reg, source, re.IGNORECASE):
                                action = "DISPARITION"
                                break
                
                # 5. Site Code fallback (if not set by header/heuristic)
                if not ctx_site_code:
                    row_site_code = get_val("site_code")
                    if row_site_code:
                        ctx_site_code_raw = row_site_code
                        ctx_site_code = normalize_site_code(row_site_code)

                if not ctx_site_code:
                    if row_idx <= 20: 
                        logger.debug(f"[ROW_SKIPPED] row={row_idx} reason=NO_SITE_CONTEXT row_data={raw_row}")
                    continue

                # Create Event
                evt = NormalizedEvent(
                    timestamp=dt,
                    site_code=ctx_site_code,
                    site_code_raw=ctx_site_code_raw,
                    event_type="GENERIC", # Will be refined by normalizer
                    raw_message=msg,
                    raw_code=code,
                    status=action, # <--- CRITICAL: Pass the derived action/status
                    source_file=file_path,
                    row_index=row_idx,
                    raw_data="\t".join(raw_row),
                    tenant_id="default"
                )
                events.append(evt)

        except Exception as e:
            logger.error(f"[TSV_FATAL_ERROR] {file_path}: {e}")
            raise e
            
        logger.info(f"[TSV_PARSE_DONE] events={len(events)}")
        return events
