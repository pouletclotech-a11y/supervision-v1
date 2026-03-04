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

    def _normalize_code(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        raw = str(raw).strip()
        # Remove one leading $
        if raw.startswith('$'):
            raw = raw[1:]
        return raw.strip().upper()

    def supported_extensions(self) -> List[str]:
        return ['.xls', '.tsv']

    def parse(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        logger.info(f"[TSV_PARSE_START] file={file_path}")
        events = []
        
        # Quality report metrics
        metrics = {
            "rows_detected": 0,
            "events_created": 0,
            "events_skipped_count": 0,
            "detail_lines_count": 0,
            "missing_time_count": 0,
            "missing_action_count": 0,
            "with_code_count": 0,
            "site_blocks_detected": 0,
            "skipped_reasons": {},
            "skipped_samples": [],
            "weekday_prefix_stripped_count": 0
        }

        def record_skip(reason, row_idx, sample=None):
            metrics["events_skipped_count"] += 1
            metrics["skipped_reasons"][reason] = metrics["skipped_reasons"].get(reason, 0) + 1
            if len(metrics["skipped_samples"]) < 20:
                metrics["skipped_samples"].append({"row": row_idx, "reason": reason, "data": sample})
            logger.info(f"[ROW_SKIPPED][{reason}] row={row_idx}")

        mapping_raw = parser_config.get("mapping", []) if parser_config else []
        action_config = parser_config.get("action_config", {}) if parser_config else {}
        
        # Convert List[MappingRule] to Dict for fast lookup
        mapping = {}
        if isinstance(mapping_raw, list):
            for m in mapping_raw:
                if isinstance(m, dict):
                    mapping[m.get("target")] = m.get("source")
                elif hasattr(m, "target") and hasattr(m, "source"):
                    mapping[m.target] = m.source
        else:
            mapping = mapping_raw
        
        # Context for inheritance
        ctx_site_code = None
        ctx_site_code_raw = None
        ctx_client_name = None
        ctx_date = None
        
        try:
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                lines = f.readlines()
            
            metrics["rows_detected"] = len(lines)
            # Split by tab but preserve leading empty columns by not stripping the whole line first
            raw_data = [line.rstrip('\r\n').split('\t') for line in lines]
            
            for row_idx, raw_row in enumerate(raw_data, 1):
                if not raw_row or (len(raw_row) == 1 and not raw_row[0]):
                    continue
                
                # Clean row elements (remove ="...")
                clean_row = [clean_excel_value(c) for c in raw_row]
                

                col_a = clean_row[0].strip() if len(clean_row) > 0 else ""
                col_b = clean_row[1].strip() if len(clean_row) > 1 else ""

                # 1. Block Detection (SPGO Specific)
                # Col A (0) = code_site (C-...), Col B (1) = client_name
                # Note: If Col A is non-empty, it starts a new block.
                # If Col B is non-empty BUT Col C/D are empty, it's a block header.
                if col_a:
                    ctx_site_code_raw = col_a
                    ctx_site_code = normalize_site_code(col_a)
                    # Block header row: A=site, B=client name, rest=empty
                    if col_b and (len(clean_row) < 3 or not clean_row[2].strip()):
                        ctx_client_name = col_b
                        metrics["site_blocks_detected"] += 1
                        continue
                    # Else it might be a site code on the same line as an event (valid)
                
                if not ctx_site_code:
                    record_skip("NO_SITE_CONTEXT", row_idx, clean_row)
                    continue

                # 2. Extract Data using Fixed Indices (A=0, B=1, C=2, D=3, E=4, F=5)
                # Col 1 (B) = Jour
                col_b_jour = col_b
                # Col 2 (C) = Datetime complet ou Heure seule
                raw_dt = clean_row[2].strip() if len(clean_row) > 2 else ""
                # Col 3 (D) = Action métier ou Message
                col_d_action_msg = clean_row[3].strip() if len(clean_row) > 3 else ""
                # Col 4 (E) = Code alarme
                col_e_code = clean_row[4].strip() if len(clean_row) > 4 else ""
                # Col 5 (F) = Détails
                col_f_details = clean_row[5].strip() if len(clean_row) > 5 else ""

                if not raw_dt:
                    metrics["missing_time_count"] += 1
                    record_skip("MISSING_TIME", row_idx, clean_row)
                    continue

                # 3. Detect Operator Note vs Security Event
                # Rule: Col B (1) vide AND Col C (2) = heure seule (HH:MM:SS)
                is_operator_note = False
                if not col_b_jour and len(raw_dt) <= 10 and ':' in raw_dt and '/' not in raw_dt:
                    is_operator_note = True

                # Parse DateTime
                dt = None
                raw_dt_clean = raw_dt
                
                # Strip weekday prefix for security events if present
                if not is_operator_note and raw_dt_clean and raw_dt_clean[3:4] == ' ' and raw_dt_clean[:3].isalpha():
                    raw_dt_clean = raw_dt_clean[4:]
                    metrics["weekday_prefix_stripped_count"] += 1

                if is_operator_note:
                    # Reconstruct time using ctx_date
                    if ctx_date:
                        try:
                            t_part = datetime.strptime(raw_dt_clean, "%H:%M:%S").time()
                            dt = datetime.combine(ctx_date, t_part)
                        except: pass
                    
                    if not dt:
                        record_skip("OPERATOR_NOTE_MISSING_DATE_CONTEXT", row_idx, raw_dt_clean)
                        continue
                else:
                    # Security Event: Try to parse full datetime
                    for fmt in ["%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%y %H:%M:%S", "%d/%m/%Y %H:%M"]:
                        try:
                            dt = datetime.strptime(raw_dt_clean, fmt)
                            ctx_date = dt.date() # Keep track for next operator notes
                            break
                        except: continue
                    
                    if not dt:
                        record_skip("DATE_PARSE_ERROR", row_idx, raw_dt)
                        continue

                # 4. Action & Details Mapping
                norm_type = "GENERIC"
                severity = "INFO"
                msg = ""
                code = col_e_code # Alarm code Col E "as-is"

                if is_operator_note:
                    norm_type = "OPERATOR_NOTE"
                    severity = "INFO"
                    # Details DOIT inclure Col D (obligatoire) (+ Col F si présent)
                    msg = col_d_action_msg
                    if col_f_details:
                        msg += " " + col_f_details
                else:
                    # Security Event
                    action = col_d_action_msg.upper()
                    if action in ["APPARITION", "DISPARITION", "RETARD", "ALERTE", "MISE EN SERVICE", "MISE HORS SERVICE", "TEST CYCLIQUE"]:
                        norm_type = action
                        if action == "APPARITION": severity = "CRITICAL"
                        else: severity = "INFO"
                    else:
                        # Fallback action deriving if Col D is not a standard keyword?
                        # User said: "Mapper Col D = action métier uniquement si datetime complet"
                        # This implies if Col D is not a keyword, maybe it's just part of message?
                        # "Sinon Col D va dans details"
                        norm_type = "INFO"
                        severity = "INFO"
                    
                    msg = col_f_details or ""
                    if norm_type == "INFO" and col_d_action_msg:
                        msg = col_d_action_msg + (" " + msg if msg else "")

                # 5. Smart Code fallback (Only if Col E was empty)
                if not code or code == "":
                    match_code_dollar = re.search(r'\$([^\s,\t;()[\]]+)', msg)
                    if match_code_dollar:
                        code = "$" + match_code_dollar.group(1)
                    else:
                        match_code_digits = re.search(r'\b(\d{4})\b', msg)
                        if match_code_digits:
                            code = match_code_digits.group(1)

                n_code = self._normalize_code(code)
                if n_code:
                    metrics["with_code_count"] += 1

                evt = NormalizedEvent(
                    timestamp=dt,
                    site_code=ctx_site_code,
                    site_code_raw=ctx_site_code_raw,
                    client_name=ctx_client_name,
                    event_type=norm_type,
                    normalized_type=norm_type,
                    raw_message=msg,
                    raw_code=code,
                    normalized_code=n_code,
                    status=severity,
                    source_file=file_path,
                    row_index=row_idx,
                    raw_data="\t".join(raw_row),
                    tenant_id="default"
                )
                events.append(evt)
                metrics["events_created"] += 1

        except Exception as e:
            logger.error(f"[TSV_FATAL_ERROR] {file_path}: {e}")
            raise e
            
        logger.info(f"[TSV_PARSE_DONE] events={len(events)} metrics={metrics}")
        self.last_metrics = metrics
        return events
