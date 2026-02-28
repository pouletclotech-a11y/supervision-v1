import logging
import pytz
from app.ingestion.models import NormalizedEvent
from app.services.calendar_service import CalendarService
from app.utils.text import normalize_text
from app.db.models import EventRuleHit
from app.core.config import settings
from datetime import datetime, time, timedelta

logger = logging.getLogger("alerting-engine")

class AlertingService:
    async def check_and_trigger_alerts(self, event: NormalizedEvent, rules: list, repo=None):
        """
        Main entry point for live/replay alerting.
        """
        for rule in rules:
            if not getattr(rule, 'is_active', True):
                continue
                
            res = await self.evaluate_rule(event, rule, repo)
            if res["triggered"]:
                await self._trigger_alert(event, rule, repo)

    async def evaluate_rule(self, event: NormalizedEvent, rule, repo=None, reference_time_override=None) -> dict:
        """
        Detailed evaluation of a rule against an event.
        Used by both real triggering and Dry Run.
        """
        # 1. SETUP
        # The base event time is ALWAYS UTC (enforced at ingestion)
        evt_dt_utc = getattr(event, 'timestamp', None)
        
        # Override time for deterministic tests
        if reference_time_override:
            if isinstance(reference_time_override, str):
                from datetime import datetime
                evt_dt = datetime.fromisoformat(reference_time_override.replace('Z', '+00:00'))
            else:
                evt_dt = reference_time_override
        else:
            evt_dt = evt_dt_utc

        if evt_dt.tzinfo is None:
            evt_dt = pytz.UTC.localize(evt_dt)
        else:
            evt_dt = evt_dt.astimezone(pytz.UTC)

        # Local conversion ONLY for schedule-matching (e.g. "Night", "Business Hours")
        display_tz = pytz.timezone(settings.DEFAULT_DISPLAY_TIMEZONE)
        evt_dt_local = evt_dt.astimezone(display_tz)
            
        evt_date_local = evt_dt_local.date()
        evt_time_local = evt_dt_local.time()
        
        is_weekend = CalendarService.is_weekend(evt_date_local)
        is_holiday = CalendarService.is_holiday(evt_date_local)
        
        report = {
            "rule_id": getattr(rule, 'id', None),
            "triggered": False,
            "condition_ok": False,
            "time_scope_ok": True,
            "frequency_ok": True,
            "logic_tree_eval": None,
            "details": []
        }

        # 2. SITE SCOPE CHECK
        r_scope = getattr(rule, 'scope_site_code', None)
        if r_scope and r_scope != getattr(event, 'site_code', None):
            report["time_scope_ok"] = False 
            report["details"].append(f"Site mismatch: expected {r_scope}")
            return report 
            
        # 3. TIME SCOPE CHECK
        r_time_scope = getattr(rule, 'time_scope', 'NONE')
        r_start = getattr(rule, 'schedule_start', None)
        r_end = getattr(rule, 'schedule_end', None)
        
        in_schedule = True
        if r_start and r_end:
            try:
                s_h, s_m = map(int, r_start.split(':'))
                e_h, e_m = map(int, r_end.split(':'))
                start_t = time(s_h, s_m)
                end_t = time(e_h, e_m)
                
                if start_t <= end_t:
                    in_schedule = (start_t <= evt_time_local <= end_t)
                else:
                    # Cross-midnight (ex: 18:00 -> 08:00)
                    in_schedule = (evt_time_local >= start_t or evt_time_local <= end_t)
            except Exception as e:
                logger.error(f"Schedule error rule {getattr(rule, 'id', '?')}: {e}")
        
        if r_time_scope == 'WEEKEND' and not is_weekend:
            report["time_scope_ok"] = False
            report["details"].append("Not a weekend")
        elif r_time_scope == 'HOLIDAYS' and not is_holiday:
            report["time_scope_ok"] = False
            report["details"].append("Not a holiday")
        elif r_time_scope == 'NIGHT':
             # Default 22:00-06-00 if no start/end
             if not (r_start and r_end):
                 in_schedule = (evt_dt_local.hour >= 22 or evt_dt_local.hour < 6)
             if not in_schedule: 
                 report["time_scope_ok"] = False
                 report["details"].append("Outside night hours (schedule)")
        elif r_time_scope == 'BUSINESS_HOURS':
            if is_weekend or is_holiday or not in_schedule:
                report["time_scope_ok"] = False
                report["details"].append("Outside business hours")
        elif r_time_scope == 'OFF_BUSINESS_HOURS':
            is_business = (not is_weekend and not is_holiday and in_schedule)
            if is_business:
                report["time_scope_ok"] = False
                report["details"].append("Inside business hours")
        
        if report["time_scope_ok"]:
            report["details"].append(f"Time scope OK ({r_time_scope})")

        if not report["time_scope_ok"]:
            return report

        # 4. LOGIC TREE or LEGACY/V3 COEXISTENCE
        if getattr(rule, 'logic_enabled', False) and getattr(rule, 'logic_tree', None) and repo:
            # Step 7: Logic Tree AST
            tree = rule.logic_tree
            codes = self._extract_condition_codes(tree)
            cond_map = await repo.get_rule_conditions_by_codes(codes)
            
            # Evaluate recursively
            eval_tree = await self._evaluate_logic_node(tree, event, repo, cond_map, evt_dt)
            report["logic_tree_eval"] = eval_tree
            report["triggered"] = eval_tree.get("result", False)
            if report["triggered"]:
                report["details"].append("Logic Tree MATCHED ✅")
            else:
                report["details"].append("Logic Tree did NOT match.")
            return report

        # --- LEGACY / SINGLE CONDITION LOGIC ---
        # 4. CONDITION CHECK (V3 Category + Keyword + B1 legacy)
        r_type = getattr(rule, 'condition_type', None)
        r_value = getattr(rule, 'value', None)
        r_cat = getattr(rule, 'match_category', None)
        r_key = getattr(rule, 'match_keyword', None)
        
        # Ensure defaults for numeric fields
        r_freq = getattr(rule, 'frequency_count', 1) or 1
        r_win = getattr(rule, 'frequency_window', 0) or 0
        r_days = getattr(rule, 'sliding_window_days', 0) or 0
        r_open_only = getattr(rule, 'is_open_only', False) or False
        r_seq_enabled = getattr(rule, 'sequence_enabled', False) or False
        
        evt_msg = getattr(event, 'normalized_message', None) or normalize_text(getattr(event, 'raw_message', ''))
        evt_cat = getattr(event, 'category', None)
        evt_action = (getattr(event, 'normalized_type', None) or getattr(event, 'event_type', '')).upper()
        
        # Action Filter: Step 5 counts on APPARITION
        action_match = ("APPARITION" in evt_action)
        
        # Category Filter
        cat_match = True
        if r_cat:
            cat_match = (evt_cat == r_cat)
            if not cat_match:
                report["details"].append(f"Category mismatch: {evt_cat} != {r_cat}")
            else:
                report["details"].append(f"Category matched: {r_cat}")

        # Keyword Filter
        key_match = True
        if r_key:
            norm_key = normalize_text(r_key)
            key_match = (norm_key in evt_msg)
            if not key_match:
                report["details"].append(f"Keyword '{norm_key}' not found in normalized message")
            else:
                report["details"].append(f"Keyword '{norm_key}' matched")

        # Legacy B1 Logic
        legacy_match = True
        if r_type == 'SEVERITY':
            evt_status = (getattr(event, 'status', None) or '').upper()
            legacy_match = (evt_status == r_value.upper())
            if not legacy_match: report["details"].append(f"Severity mismatch: {evt_status} != {r_value}")
        elif r_type == 'KEYWORD' and not r_key: # Only if V3 keyword not set
            legacy_match = (r_value.lower() in evt_msg.lower())
            if not legacy_match: report["details"].append(f"Condition Keyword '{r_value}' not found")
        elif r_type == 'REGEX':
            import re
            try:
                legacy_match = bool(re.search(r_value, evt_msg, re.IGNORECASE))
                if not legacy_match: report["details"].append(f"Regex '{r_value}' did not match")
            except Exception as e:
                legacy_match = False
                report["details"].append(f"Invalid Regex: {e}")

        # Overall Condition Trigger
        report["condition_ok"] = (action_match and cat_match and key_match and legacy_match)
        if report["condition_ok"]:
            report["details"].append("General conditions matched (Action+Cat+Key+Legacy)")

        # 5. FREQUENCY / SLIDING WINDOW CHECK
        if report["condition_ok"] and report["time_scope_ok"]:
            # Check if event is historical (has ID)
            is_hist = (getattr(event, 'id', None) is not None)
            
            # 5. SEQUENCE or FREQUENCY CHECK
            if r_seq_enabled and repo:
                # V3 SEQUENCE LOGIC: A -> B in Δt
                # Note: We use the repository to find a matching pair in the lookback
                match = await repo.find_sequence_match(
                    site_code=getattr(event, 'site_code', ''),
                    a_cat=getattr(rule, 'seq_a_category', None),
                    a_key=getattr(rule, 'seq_a_keyword', None),
                    b_cat=getattr(rule, 'seq_b_category', None),
                    b_key=getattr(rule, 'seq_b_keyword', None),
                    max_delay_seconds=getattr(rule, 'seq_max_delay_seconds', 0),
                    lookback_days=getattr(rule, 'seq_lookback_days', 2),
                    reference_time=evt_dt
                )
                
                if match:
                    report["triggered"] = True
                    report["details"].append(f"SEQUENCE MATCHED: A(id:{match['a_id']}, time:{match['a_time']}) followed by B(id:{match['b_id']}, time:{match['b_time']})")
                    report["details"].append(f"Delay: {(match['b_time'] - match['a_time']).total_seconds()}s (max allowed: {getattr(rule, 'seq_max_delay_seconds', 0)}s)")
                else:
                    report["frequency_ok"] = False
                    report["details"].append("No valid sequence (A->B) found in lookback window.")

            elif r_days > 0 and repo:
                # V3 FREQUENCY LOGIC
                count = await repo.count_v3_matches(
                    site_code=getattr(event, 'site_code', ''),
                    category=r_cat,
                    keyword=r_key,
                    days=r_days,
                    open_only=r_open_only,
                    reference_time=evt_dt
                )
                # If historical, count should already include current event if matching
                actual_count = count if is_hist else (count + 1)
                
                if actual_count < r_freq:
                    report["frequency_ok"] = False
                    report["details"].append(f"V3 Frequency not met: {actual_count}/{r_freq} matches in last {r_days} days (OpenOnly={r_open_only}, is_hist={is_hist})")
                else:
                    report["details"].append(f"V3 Frequency met: {actual_count}/{r_freq} matches found")
            
            elif r_freq > 1 and r_win > 0 and repo:
                # B1 LOGIC: frequency_window in seconds
                count = await repo.count_recent_matches(
                    getattr(event, 'site_code', ''), r_type, r_value, r_win, reference_time=evt_dt
                )
                if (count + 1) < r_freq:
                    report["frequency_ok"] = False
                    report["details"].append(f"B1 Frequency not met: {count+1}/{r_freq} matches in {r_win}s")
            
            # Final trigger decision
            if report["frequency_ok"]:
                report["triggered"] = True
                report["details"].append("Rule TRIGGERED ✅")
                
        return report

    # --- Step 7 Logic Engine ---
    
    def _extract_condition_codes(self, node: dict) -> list:
        codes = []
        if "ref" in node:
            ref = node["ref"]
            if ref.startswith("cond:"):
                codes.append(ref.split(":")[1])
        if "children" in node:
            for child in node["children"]:
                codes.extend(self._extract_condition_codes(child))
        return list(set(codes))

    async def _evaluate_logic_node(self, node: dict, event, repo, cond_map, evt_dt) -> dict:
        """Recursive AST evaluator."""
        eval_res = {"node": node, "result": False, "details": []}
        
        # 1. Leaf: Reference to a named condition
        if "ref" in node:
            code = node["ref"].split(":")[1]
            cond = cond_map.get(code)
            if not cond:
                eval_res["details"].append(f"Condition '{code}' not found or inactive")
                return eval_res
            
            res = await self._evaluate_condition(cond, event, repo, evt_dt)
            eval_res["result"] = res["triggered"]
            eval_res["details"] = res["details"]
            return eval_res
            
        # 2. Operator: AND / OR
        op = node.get("op", "AND").upper()
        children = node.get("children", [])
        
        if not children:
            eval_res["details"].append("Empty operator node")
            return eval_res
            
        child_results = []
        final_res = (op == "AND") # True if AND (start positive), False if OR (start negative)
        
        short_circuited = False
        for child in children:
            if short_circuited:
                child_results.append({"node": child, "skipped": True})
                continue
                
            c_res = await self._evaluate_logic_node(child, event, repo, cond_map, evt_dt)
            child_results.append(c_res)
            
            if op == "AND":
                final_res = final_res and c_res["result"]
                if not final_res: short_circuited = True
            else: # OR
                final_res = final_res or c_res["result"]
                if final_res: short_circuited = True
                
        eval_res["result"] = final_res
        eval_res["children"] = child_results
        return eval_res

    async def _evaluate_condition(self, cond, event, repo, evt_dt) -> dict:
        """Evaluates a single RuleCondition payload."""
        payload = cond.payload
        c_type = cond.type # SIMPLE_V3, SEQUENCE
        
        # Mocking a rule object from the payload for reuse
        mock_rule = type('obj', (object,), {**payload, 'id': f"cond:{cond.code}", 'name': cond.label})
        
        # Action Filter (mandatory in Step 7 context)
        evt_action = (getattr(event, 'normalized_type', None) or getattr(event, 'event_type', '')).upper()
        if "APPARITION" not in evt_action:
            return {"triggered": False, "details": ["Condition only applies to APPARITION"]}

        # Prepare report
        report = {"triggered": False, "details": []}
        
        # Filters (Category, Keyword)
        cat_match = True
        r_cat = payload.get("match_category")
        if r_cat:
            evt_cat = getattr(event, 'category', None)
            cat_match = (evt_cat == r_cat)
            if not cat_match: report["details"].append(f"Cat mismatch: {evt_cat}")
            
        key_match = True
        r_key = payload.get("match_keyword")
        if r_key:
            evt_msg = getattr(event, 'normalized_message', None) or normalize_text(getattr(event, 'raw_message', ''))
            norm_key = normalize_text(r_key)
            key_match = (norm_key in evt_msg)
            if not key_match: report["details"].append(f"Keyword '{norm_key}' not found in normalized message")
            
        if not (cat_match and key_match):
            return report

        # Frequency/Sequence logic
        is_hist = (getattr(event, 'id', None) is not None)
        
        if c_type == 'SEQUENCE':
            match = await repo.find_sequence_match(
                site_code=getattr(event, 'site_code', ''),
                a_cat=payload.get("seq_a_category"),
                a_key=payload.get("seq_a_keyword"),
                b_cat=payload.get("seq_b_category"),
                b_key=payload.get("seq_b_keyword"),
                max_delay_seconds=payload.get("seq_max_delay_seconds", 0),
                lookback_days=payload.get("seq_lookback_days", 2),
                reference_time=evt_dt
            )
            if match:
                report["triggered"] = True
                report["details"].append(f"Seq match A:{match['a_id']} -> B:{match['b_id']}")
        else: # SIMPLE_V3
            r_freq = payload.get("frequency_count", 1)
            r_days = payload.get("sliding_window_days", 0)
            count = await repo.count_v3_matches(
                site_code=getattr(event, 'site_code', ''),
                category=r_cat,
                keyword=r_key,
                days=r_days,
                open_only=payload.get("is_open_only", False),
                reference_time=evt_dt
            )
            actual_count = count if is_hist else (count + 1)
            if actual_count >= r_freq:
                report["triggered"] = True
                report["details"].append(f"Freq met: {actual_count}/{r_freq}")
            else:
                report["details"].append(f"Freq not met: {actual_count}/{r_freq}")
                
        return report

    async def _trigger_alert(self, event, rule, repo=None):
        r_name = getattr(rule, 'name', '?')
        logger.warning(f"🚨 ALERT TRIGGERED: Rule '{r_name}' Matched | Site: {getattr(event, 'site_code', '?')} | Msg: {getattr(event, 'raw_message', '?')}")
        
        # Update event status to CRITICAL so it appears red in UI
        event.status = 'CRITICAL'
        
        # 4. RECORD HIT (Phase 1 Auditability)
        if repo:
            event_id = getattr(event, 'id', None) or getattr(event, '_db_id', None)
            if event_id:
                # Build metadata for scope grouping
                hit_metadata = {}
                zone_label = getattr(event, 'zone_label', None)
                if zone_label:
                    hit_metadata['zone_label'] = zone_label
                
                # Try to extract zone_id from metadata or zone_label
                evt_metadata = getattr(event, 'metadata', {}) or {}
                zone_id = evt_metadata.get('zone_id')
                if zone_id:
                    hit_metadata['zone_id'] = zone_id

                try:
                    await repo.record_rule_hit(
                        event_id=event_id,
                        rule_id=rule.id,
                        rule_name=rule.name,
                        hit_metadata=hit_metadata
                    )
                except Exception as e:
                    logger.error(f"Failed to record rule hit: {e}")
