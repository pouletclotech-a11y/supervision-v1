import re
import csv
import json
import pytz
from datetime import datetime
from typing import List, Optional
from app.parsers.base import BaseParser
from app.ingestion.models import NormalizedEvent
from app.utils.text import normalize_text, clean_excel_value
from app.ingestion.normalizer import normalize_site_code, normalize_site_code_full

class ExcelParser(BaseParser):
    """
    Parses 'Pseudo-Excel' files (YPSILON.xls) which are actually Tab-Separated Values (TSV)
    wrapped in Excel formulas (e.g. ="Value").
    
    V2 Implementation: Cell-aware context propagation.
    - Col A: site_code (inherits down)
    - Col B: day (inherits down)
    - Col C: date/time (inherits date part down)
    - Col D: action/type
    - Col F: details
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
        return ['.xlsx']

    def parse(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        import pandas as pd
        import logging
        logger = logging.getLogger("excel-parser")
        logger.info(f" [XLSX_PARSE_START] {file_path}")
        events = []
        
        # Quality report metrics
        metrics = {
            "rows_detected": 0,
            "events_created": 0,
            "events_skipped_count": 0,
            "missing_time_count": 0,
            "missing_action_count": 0,
            "with_code_count": 0,
            "site_blocks_detected": 0,
            "skipped_reasons": {},
            "skipped_samples": []
        }

        def record_skip(reason, row_idx, sample=None):
            metrics["events_skipped_count"] += 1
            metrics["skipped_reasons"][reason] = metrics["skipped_reasons"].get(reason, 0) + 1
            if len(metrics["skipped_samples"]) < 20:
                # Convert row sample to strings for JSON serializability
                sample_str = [str(s) for s in sample] if sample is not None else None
                metrics["skipped_samples"].append({"row": row_idx, "reason": reason, "data": sample_str})
            logger.info(f"[ROW_SKIPPED][{reason}] row={row_idx}")

        mapping_raw = parser_config.get("mapping", []) if parser_config else []
        action_config = parser_config.get("action_config", {}) if parser_config else {}
        is_histo = (parser_config or {}).get("format") == "HISTO"
        provider_code = (parser_config or {}).get("provider_code")
        
        # Zero-hardcoding strategies
        site_strategy = (parser_config or {}).get("site_propagation_strategy", "DEFAULT")
        client_strategy = (parser_config or {}).get("client_propagation_strategy", "DEFAULT")
        time_strategy = (parser_config or {}).get("timestamp_strategy", "DEFAULT")
        is_efi = (parser_config or {}).get("is_efi", False) or provider_code == "EFI"
        
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
        
        logger.info(f"Final mapping dict: {mapping}")
        
        try:
            # Explicitly use openpyxl for .xlsx
            df = pd.read_excel(file_path, header=None, engine='openpyxl')
            metrics["rows_detected"] = len(df)
            
            # Diagnostic Log: Raw sample content
            if not df.empty:
                logger.debug(f" [XLSX_DF_SHAPE] rows={len(df)} cols={len(df.columns)}")
            else:
                logger.warning(f" [XLSX_RAW_ROWS_CONTENT_SAMPLE] EMPTY DATAFRAME")
            
            # Context trackers (Inheritance)
            ctx_site_code = None
            ctx_site_code_raw = None
            ctx_client_name = None
            ctx_day = None
            ctx_date = None
            last_ts = None # For HISTO operator actions

            for idx, row_series in df.iterrows():
                row = []
                for val in row_series.tolist():
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        row.append("")
                    else:
                        row.append(val)

                row_idx = idx + 1
                
                # Ignore Row 1 (Header/MetaData)
                if row_idx == 1:
                    continue
                if mapping:
                    # Helper to get by index or letter
                    def get_val(key):
                        idx_val = mapping.get(key)
                        if idx_val is None: return None
                        try:
                            if isinstance(idx_val, str) and len(idx_val) == 1 and idx_val.isalpha():
                                idx = ord(idx_val.upper()) - ord('A')
                            else:
                                idx = int(idx_val)
                            return row[idx] if idx < len(row) else ""
                        except Exception as e: 
                            logger.error(f"get_val error for {key}: {e}")
                            return ""

                    # Site code logic (Propagation if empty)
                    current_site = str(get_val("site_code")).strip()
                    if current_site and current_site.lower() != 'nan' and current_site != "":
                        # site_propagation_strategy == "STRIP_LEADING_ZEROS" (CORS specific logic)
                        ctx_site_code_raw = current_site
                        # normalize_site_code_full handles digit extraction + leading zero strip
                        ctx_site_code, _ = normalize_site_code_full(current_site)
                        metrics["site_blocks_detected"] += 1
                    
                    if not ctx_site_code:
                        # Only skip if we really have no context and this isn't a header-only row
                        # Check all possible time keys
                        if get_val("timestamp") or get_val("date_time") or get_val("date"):
                            record_skip("NO_SITE_CONTEXT", row_idx, row)
                        continue

                    # Client name logic (Propagation if empty)
                    current_client = str(get_val("client_name") or "").strip()
                    if current_client and current_client.lower() != 'nan' and current_client != "":
                        ctx_client_name = current_client
                        # Also capture address if possible for context
                        # Col C = index 2
                        if len(row) > 2 and row[2] and str(row[2]).lower() != 'nan':
                            ctx_address = str(row[2]).strip()

                    # 2. Date/Time Parsing
                    raw_dt = get_val("timestamp") or get_val("date_time")
                    is_operator_action = False
                    
                    if not raw_dt or str(raw_dt).lower() == 'nan':
                        # Try Operator Action: Col J (index 9)
                        op_dt = row[9] if len(row) > 9 else None
                        if op_dt and str(op_dt).lower() != 'nan' and str(op_dt).strip() != "":
                            raw_dt = op_dt
                            is_operator_action = True
                    
                    if not raw_dt or str(raw_dt).lower() == 'nan':
                        metrics["missing_time_count"] += 1
                        record_skip("MISSING_DATE_TIME", row_idx, row)
                        continue
                    
                    # Parse Date (Robust)
                    dt = None
                    try:
                        if isinstance(raw_dt, datetime):
                            dt = raw_dt
                        else:
                            for fmt in ["%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"]:
                                try:
                                    dt = datetime.strptime(str(raw_dt).strip(), fmt)
                                    break
                                except: continue
                    except: pass

                    if not dt:
                        record_skip("DATE_PARSE_ERROR", row_idx, str(raw_dt))
                        continue

                    # Msg / Code / Action (Support raw_message/raw_code as priority)
                    msg = str(get_val("raw_message") or get_val("message") or "")
                    code = str(get_val("raw_code") or get_val("code") or "")
                    
                    # Robust Code Extraction from Message if empty (Strategy based)
                    if (not code or code.lower() == 'nan' or code == "") and msg:
                        # Pattern A: "1234  MESSAGE..." (Supervision Start)
                        match_code = re.match(r'^(\d{2,6})\s+', msg)
                        if match_code:
                            code = match_code.group(1)
                        else:
                            # Pattern B: "... $CODE" (Inside message)
                            match_code_dollar = re.search(r'\$([^\s,\t;()[\]]+)', msg)
                            if match_code_dollar:
                                code = "$" + match_code_dollar.group(1)
                            else:
                                # Pattern C: "MISE EN SERVICE 0003" (4 digits)
                                match_code_digits = re.search(r'\b(\d{4})\b', msg)
                                if match_code_digits:
                                    code = match_code_digits.group(1)
                    
                    # If Operator Action, use Col M (index 12) for detail text
                    if is_operator_action:
                        msg = row[12] if len(row) > 12 else msg
                        action = "OPERATOR_ACTION"
                    else:
                        action = get_val("action")

                    mode = action_config.get("mode", "NONE")
                    if mode == "COLUMN":
                        if not action:
                            action = "INFO" # Fallback if col mapped but empty
                    elif mode == "REGEX_DERIVE":
                        source = msg if action_config.get("source_field") == "message" else code
                        action = None
                        for reg in action_config.get("regex_app", []):
                            if re.search(reg, source, re.IGNORECASE):
                                action = "APPARITION"; break
                        if not action:
                            for reg in action_config.get("regex_dis", []):
                                if re.search(reg, source, re.IGNORECASE):
                                    action = "DISPARITION"; break
                    
                    if not action or str(action).lower() == 'nan' or action == "":
                        # Smart derivative if empty
                        action = "INFO"
                        m_upper = msg.upper()
                        if "APPARITION" in m_upper or "ALARM" in m_upper or "INTRUSION" in m_upper: action = "APPARITION"
                        elif "DISPARITION" in m_upper or "RETARD" in m_upper: action = "DISPARITION"
                        elif "MISE EN SERVICE" in m_upper: action = "MISE EN SERVICE"
                        elif "MISE HORS SERVICE" in m_upper: action = "MISE HORS SERVICE"
                        elif "TEST CYCLIQUE" in m_upper: action = "TEST CYCLIQUE"

                    # Smart code fallback if empty
                    if (not code or code.lower() == 'nan' or code == "") and msg:
                        # Pattern B: "... $CODE" (Inside message)
                        match_code_dollar = re.search(r'\$([^\s,\t;()[\]]+)', msg)
                        if match_code_dollar:
                            code = "$" + match_code_dollar.group(1)
                        else:
                            # Pattern C: "MISE EN SERVICE 0003" (4 digits)
                            match_code_digits = re.search(r'\b(\d{4})\b', msg)
                            if match_code_digits:
                                code = match_code_digits.group(1)

                    # Business Logic mapping
                    # Severity/Status: INFO, WARN, CRITICAL
                    # NormalizedType: APPARITION, DISPARITION, ...
                    
                    norm_type = "UNKNOWN"
                    if is_operator_action:
                        norm_type = "OPERATOR_ACTION"
                        severity = "INFO"
                    elif action in ["APPARITION", "DISPARITION", "ALARM", "MISE EN SERVICE", "MISE HORS SERVICE", "TEST CYCLIQUE", "RETARD", "ALERTE"]:
                        norm_type = action
                        if action == "ALARM": severity = "CRITICAL"
                        else: severity = "INFO"
                    else:
                        severity = action or "INFO"
                    
                    if norm_type == "GENERIC":
                        metrics["missing_action_count"] += 1

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
                        raw_data=json.dumps([str(x) for x in row]),
                        tenant_id="default"
                    )
                    events.append(evt)
                    metrics["events_created"] += 1
                else:
                    # Backward compatibility for existing logic if mapping empty (Phase transition)
                    try:
                        processed = self._process_row(row, row_idx, file_path, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date, is_histo, source_timezone, provider_code=provider_code, last_ts=last_ts, parser_config=parser_config)
                        if processed:
                            evt, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date = processed
                            if evt: 
                                events.append(evt)
                                metrics["events_created"] += 1
                                last_ts = evt.timestamp
                    except: 
                        record_skip("LEGACY_PARSE_ERROR", row_idx, row)
            
            logger.info(f" [XLSX_EVENTS_DONE] count={len(events)} metrics={metrics}")
            self.last_metrics = metrics
            
        except Exception as e:
            logger.error(f" [XLSX_FATAL_ERROR] file={file_path}: {e}")
            raise e
            
        return events

    def _process_row(self, clean_row, row_idx, file_path, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date, is_histo=False, source_timezone="UTC", is_efi=False, provider_code=None, last_ts=None, parser_config=None):
        if is_histo:
            return self._process_row_histo(clean_row, row_idx, file_path, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date, source_timezone, provider_code=provider_code, last_ts=last_ts, parser_config=parser_config)
        
        col_a, col_b, col_c, col_d, col_e, col_f, col_g = [clean_excel_value(c) for c in clean_row[:7]]

        # --- EFI DIAGNOSTIC: MAPPING ---
        if is_efi and row_idx == 1:
            import logging
            logging.getLogger("excel-parser").info(f" [EFI_COLUMN_MAP] site_code_col=A day_col=B date_col=C time_col=D code_col=F action_col=G")

        # --- 1. SITE_CODE PROPAGATION (Col A) ---
        if col_a:
            # Robust conversion: handle pandas floats (69000.0)
            col_a_clean = str(col_a).strip()
            if col_a_clean.endswith('.0'):
                col_a_clean = col_a_clean[:-2]
            
            # Match digits-only or C-digits, but keep original if it looks like a code
            site_match = re.match(r'^(C-)?(\d+)$', col_a_clean)
            if site_match:
                ctx_site_code, ctx_site_code_raw = normalize_site_code_full(col_a_clean)
                # Client name is usually in Col B of the header row
                if col_b:
                    col_b_str = str(col_b).strip().upper()
                    if col_b_str[:3] not in ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"] and col_b_str != "NAN":
                        ctx_client_name = str(col_b).strip()

        # --- 2. DAY PROPAGATION (Col B) ---
        days_map = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        if col_b:
            col_b_str = str(col_b).strip().upper()
            if col_b_str[:3] in days_map:
                ctx_day = col_b_str[:3]

        # --- 3. DATE/TIME PROPAGATION (Col C & D) ---
        ts = None
        if col_c or col_d:
            # Support already parsed datetime/Timestamp from Pandas
            if isinstance(col_c, datetime):
                ts = col_c
                ctx_date = ts.date()
            else:
                col_c_str = str(col_c).strip()
                # Case A: Full Date 27/01/2026 16:24:25 in Col C
                try:
                    ts = datetime.strptime(col_c_str, "%d/%m/%Y %H:%M:%S")
                    ctx_date = ts.date()
                except ValueError:
                    # Case B: Date in Col C (27/01/2026) and Time in Col D (16:24:25)
                    try:
                        temp_date = datetime.strptime(col_c_str, "%d/%m/%Y").date()
                        ctx_date = temp_date
                    except ValueError:
                        pass
                    
                    if col_d:
                        col_d_str = str(col_d).strip()
                        if re.match(r'^\d{2}:\d{2}:\d{2}$', col_d_str) and ctx_date:
                            try:
                                t_part = datetime.strptime(col_d_str, "%H:%M:%S").time()
                                ts = datetime.combine(ctx_date, t_part)
                            except ValueError:
                                pass
        
        # --- 4. ACTION & DETAILS (Col G & F) ---
        # In YPSILON TSV: Col E is empty/separator, Col F is raw_code, Col G is action/message
        action = str(col_g).strip()
        details = "" # Details might be merged in action for this format
        raw_code = str(col_f).strip() if col_f and str(col_f).lower() != 'nan' else None

        # --- 5. EVENT GENERATION ---
        if not ts or not action or not ctx_site_code or action.lower() == 'nan':
            if is_efi and row_idx <= 20:
                import logging
                reason = "MISSING_TS" if not ts else ("MISSING_ACTION" if not action else "MISSING_SITE")
                logging.getLogger("excel-parser").info(f" [EFI_ROW_SKIPPED] row_index={row_idx} reason={reason} raw_site={col_a} raw_date={col_c} raw_time={col_d} raw_action={col_g}")
            return None, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date
        
        # State mapping
        state = "UNKNOWN"
        if "APPARITION" in action.upper(): state = "APPARITION"
        elif "DISPARITION" in action.upper(): state = "DISPARITION"
        elif "EXPIRATION" in action.upper(): state = "EXPIRATION"
        elif "MISE EN SERVICE" in action.upper(): state = "MISE_EN_SERVICE"
        elif "MISE HORS SERVICE" in action.upper(): state = "MISE_HORS_SERVICE"

        event = NormalizedEvent(
            timestamp=self._normalize_timestamp(ts, source_timezone),
            site_code=ctx_site_code,
            site_code_raw=ctx_site_code_raw,
            client_name=ctx_client_name,
            weekday_label=ctx_day,
            event_type=action,
            raw_message=f"{action} | {details}" if details and details.lower() != 'nan' else action,
            normalized_message=normalize_text(f"{action} | {details}" if details and details.lower() != 'nan' else action),
            raw_code=raw_code,
            status="ALARM" if state == "APPARITION" else "INFO",
            source_file=file_path,
            row_index=row_idx,
            raw_data=json.dumps(clean_row if isinstance(clean_row, list) else []),
            tenant_id="default-tenant"
        )
        
        event.metadata = {
            "raw_action": action,
            "raw_details": details,
            "col_e": col_e,
            "state": state
        }
        
        return event, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date

    def _process_row_histo(self, clean_row, row_idx, file_path, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date, source_timezone="UTC", provider_code=None, last_ts=None, parser_config=None):
        if parser_config is None: parser_config = {}
        # Format YPSILON_HISTO:
        # Col 0 (A): Site code
        # Col 1 (B): Client name
        # Col 6 (G): Timestamp
        # Col 7 (H): Action
        # Col 8 (I): Message/Code
        
        col_site = str(clean_excel_value(clean_row[0])).strip()
        col_client = str(clean_excel_value(clean_row[1])).strip()
        
        # Strategy based mapping logic
        if time_strategy == "CORS_HISTO" or provider_code == "CORS":
            # A=0, G=6, H=7, I=8, J=9, N=13
            col_ts = clean_row[6]
            col_action = str(clean_excel_value(clean_row[7])).strip()
            col_code = str(clean_excel_value(clean_row[8])).strip() # alarm_code (I)
            col_msg = str(clean_excel_value(clean_row[9])).strip()  # details (J)
            
            # Action Opérateur (N = index 13)
            col_op_action = str(clean_excel_value(clean_row[13])).strip() if len(clean_row) > 13 else ""
            if col_op_action:
                col_action = "OPERATOR_ACTION"
                col_msg = col_op_action
        else:
            # Default mapping (SPGO, etc.)
            col_ts = clean_row[6]
            col_action = str(clean_excel_value(clean_row[7])).strip()
            col_msg = str(clean_excel_value(clean_row[8])).strip()
            col_code = None

        # 1. Propagation
        if col_site:
            col_site_clean = str(col_site).strip()
            match_site = re.match(r'^(C-)?(\d+)$', col_site_clean)
            if match_site:
                ctx_site_code, ctx_site_code_raw = normalize_site_code_full(col_site_clean)
                if col_client and col_client.lower() != 'nan':
                    ctx_client_name = col_client.strip()
        
        # 2. Timestamp
        ts = None
        if isinstance(col_ts, datetime):
            ts = col_ts
        elif col_ts:
            col_ts_str = str(clean_excel_value(col_ts)).strip()
            if col_ts_str:
                for fmt in ["%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                    try:
                        ts = datetime.strptime(col_ts_str, fmt)
                        break
                    except ValueError:
                        continue
        
        if not ts or not ctx_site_code:
            allow_ts_carry = parser_config.get("allow_timestamp_carry_over_for_actions", [])
            if col_action in allow_ts_carry and last_ts and ctx_site_code:
                ts = last_ts
            else:
                return None, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date
        
        # State mapping
        state = "UNKNOWN"
        action_upper = col_action.upper()
        if "APPARITION" in action_upper: state = "APPARITION"
        elif "DISPARITION" in action_upper: state = "DISPARITION"
        elif "EXPIRATION" in action_upper: state = "EXPIRATION"
        elif "MISE EN SERVICE" in action_upper: state = "MISE_EN_SERVICE"
        elif "MISE HORS SERVICE" in action_upper: state = "MISE_HORS_SERVICE"
        elif "OPERATOR_ACTION" in action_upper: state = "OPERATOR_ACTION"

        event = NormalizedEvent(
            timestamp=self._normalize_timestamp(ts, source_timezone),
            site_code=ctx_site_code,
            site_code_raw=ctx_site_code_raw,
            client_name=ctx_client_name,
            weekday_label=None,
            event_type=state if state != "UNKNOWN" else (col_action if col_action and col_action.lower() != 'nan' else "EVENT"),
            normalized_type=state if state != "UNKNOWN" else (col_action if col_action and col_action.lower() != 'nan' else "EVENT"),
            raw_message=f"{col_action} | {col_msg}" if col_action and col_action.lower() != 'nan' else col_msg,
            normalized_message=normalize_text(f"{col_action} | {col_msg}" if col_action and col_action.lower() != 'nan' else col_msg),
            raw_code=col_code,
            status="ALARM" if state == "APPARITION" else "INFO",
            source_file=file_path,
            row_index=row_idx,
            raw_data=json.dumps([str(x) for x in clean_row]),
            tenant_id="default-tenant"
        )

        # In non-CORS HISTO, the code might be inside the message after a '$'
        if not event.raw_code and '$' in col_msg:
            match_code = re.search(r'\$([\w-]+)', col_msg)
            if match_code:
                event.raw_code = match_code.group(1)
        
        # Normalization of code only if it exists
        if event.raw_code:
            event.normalized_code = self._normalize_code(event.raw_code)

        event.metadata = {
            "state": state,
            "raw_action": col_action,
            "raw_message": col_msg
        }

        # Weekday
        days_map_fr = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        event.weekday_label = days_map_fr[ts.weekday()]

        return event, ctx_site_code, ctx_site_code_raw, ctx_client_name, ctx_day, ctx_date

    def _normalize_timestamp(self, ts: datetime, source_timezone: str) -> datetime:
        """
        Converts a naive or local datetime to timezone-aware UTC.
        """
        if ts is None:
            return None
            
        # If already aware, convert to UTC
        if ts.tzinfo is not None:
            return ts.astimezone(pytz.UTC)
            
        # If naive, localize with source_timezone then convert to UTC
        try:
            tz = pytz.timezone(source_timezone)
            aware_ts = tz.localize(ts)
            return aware_ts.astimezone(pytz.UTC)
        except Exception:
            # Fallback to UTC if timezone is invalid
            aware_ts = pytz.UTC.localize(ts)
            return aware_ts
