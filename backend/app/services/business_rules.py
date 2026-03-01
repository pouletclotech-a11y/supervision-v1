"""
Phase 2A — Business Rule Engine V2
Moteur d'évaluation des règles métier avec :
  - exclude_dup_count configurable (config.yml + DB settings)
  - matching raw_code EXACT | IN
  - Évaluation des AlertRule actives en DB
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from app.db.models import Event, EventRuleHit, AlertRule, Setting

logger = logging.getLogger("business-rules")


def _get_rules_config() -> Dict[str, Any]:
    """Charge la config monitoring.rules depuis config_loader avec fallbacks."""
    try:
        from app.core.config_loader import app_config
        return app_config.get('monitoring', {}).get('rules', {})
    except Exception:
        return {}


async def _get_db_setting(
    session: AsyncSession,
    key: str,
    default: Any,
    expected_type: Optional[type] = None,
    allowed_values: Optional[List[Any]] = None
) -> Any:
    """
    Lire un setting depuis la table DB (override par rapport au YAML).
    Robustesse : log WARNING si JSON invalide ou type incorrect.
    """
    try:
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            try:
                val = json.loads(setting.value)
            except json.JSONDecodeError:
                logger.warning(f"[SETTINGS_OVERRIDE_INVALID_JSON] key={key} value={setting.value}")
                return default

            # Validation de type
            if expected_type and not isinstance(val, expected_type):
                logger.warning(f"[SETTINGS_OVERRIDE_TYPE_MISMATCH] key={key} expected={expected_type.__name__} got={type(val).__name__}")
                return default

            # Validation d'enum
            if allowed_values and val not in allowed_values:
                logger.warning(f"[SETTINGS_OVERRIDE_INVALID_ENUM] key={key} value={val} allowed={allowed_values}")
                return default

            return val
    except Exception as e:
        logger.error(f"[SETTINGS_OVERRIDE_ERROR] key={key} error={str(e)}")

    return default


def rule_raw_code_match(event_raw_code: Optional[str], rule_config: Dict[str, Any], mode: str = "IN") -> bool:
    """
    Match event.raw_code contre la config de la règle.

    Args:
        event_raw_code: Code brut de l'événement (peut être None).
        rule_config: Dict contenant soit:
            - {'raw_code': '570'}              → EXACT
            - {'raw_codes': ['570', '571']}    → IN
        mode: "EXACT" ou "IN" (global, peut être overridé par la config).

    Returns:
        True si le code correspond selon le mode.
    """
    if event_raw_code is None:
        return False

    event_code = str(event_raw_code).strip()

    # Mode override depuis la règle elle-même
    rule_mode = rule_config.get('raw_code_mode', mode).upper()

    if rule_mode == "EXACT":
        target = str(rule_config.get('raw_code', '')).strip()
        matched = event_code == target
        return matched

    elif rule_mode == "IN":
        targets = rule_config.get('raw_codes', rule_config.get('raw_code_list', []))
        if isinstance(targets, str):
            # JSON string → parse
            try:
                targets = json.loads(targets)
            except Exception:
                targets = [targets]
        targets_str = [str(t).strip() for t in targets]
        return event_code in targets_str

    return False


class BusinessRuleEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        # Config statique YAML (chargée une fois par instance)
        self._rules_cfg: Optional[Dict[str, Any]] = None

    async def _rules_config(self) -> Dict[str, Any]:
        if self._rules_cfg is None:
            self._rules_cfg = _get_rules_config()
        return self._rules_cfg

    async def _should_exclude_dup(self, event: Event) -> bool:
        """
        Retourne True si l'événement doit être ignoré à cause de dup_count.
        Priorité : DB setting > config.yml > False.
        """
        cfg = await self._rules_config()
        exclude = cfg.get('exclude_dup_count', False)
        # Override possible depuis la table settings
        exclude = await _get_db_setting(self.session, 'monitoring.rules.exclude_dup_count', exclude, expected_type=bool)
        return bool(exclude) and (event.dup_count or 0) > 0

    async def _raw_code_mode(self) -> str:
        cfg = await self._rules_config()
        default_mode = cfg.get('raw_code_mode', 'IN').upper()
        return await _get_db_setting(
            self.session,
            'monitoring.rules.raw_code_mode',
            default_mode,
            expected_type=str,
            allowed_values=['EXACT', 'IN']
        )

    async def evaluate_batch(self, events: List[Event]):
        """Évalue toutes les règles pour un lot d'événements persistés."""
        # Charger les règles actives une seule fois pour tout le batch
        active_rules = await self._load_active_rules()
        raw_code_mode = await self._raw_code_mode()

        cfg = await self._rules_config()
        v1_enabled = cfg.get('engine_v1_enabled', True)
        v1_enabled = await _get_db_setting(self.session, 'monitoring.rules.engine_v1_enabled', v1_enabled, expected_type=bool)

        logger.debug(f"[ENGINE_V1] enabled={v1_enabled}")

        for event in events:
            # Filtre dup_count
            if await self._should_exclude_dup(event):
                logger.debug(f"[RULE_DUP_EXCLUDED] event_id={event.id} dup_count={event.dup_count}")
                continue

            # Moteur V1 hérité (règles hardcodées ENGINE_V1)
            if v1_enabled:
                await self.evaluate_legacy_rules(event)

            # Moteur V2 : règles DB dynamiques
            await self.evaluate_db_rules(event, active_rules, raw_code_mode)

    async def _load_active_rules(self) -> List[AlertRule]:
        """Charge toutes les AlertRule actives de la DB."""
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.is_active == True)
        )
        return list(result.scalars().all())

    # ─── MOTEUR V1 (backward compat) ──────────────────────────────────────────

    async def evaluate_legacy_rules(self, event: Event):
        """Évaluation des règles V1 hardcodées (ENGINE_V1)."""
        cfg = _get_rules_config()
        await self._rule_intrusion_maintenance(event, cfg)
        await self._rule_absence_test(event, cfg)
        await self._rule_technical_faults(event, cfg)
        await self._rule_ejection_48h(event, cfg)
        await self._rule_inhibition(event, cfg)

    async def _rule_intrusion_maintenance(self, event: Event, cfg: dict):
        keywords = cfg.get("intrusion", {}).get("keywords", [])
        msg = (event.normalized_message or "").lower()
        if any(k in msg for k in keywords):
            if event.in_maintenance:
                return
            await self._record_hit(event, "INTRUSION_NO_MAINTENANCE", "Intrusion sans maintenance active")

    async def _rule_absence_test(self, event: Event, cfg: dict):
        triggers = cfg.get("absence_test", {}).get("trigger_keywords", [])
        msg = (event.normalized_message or "").lower()
        if any(t in msg for t in triggers):
            await self._record_hit(event, "ABSENCE_TEST", "Manque de test cyclique détecté")

    async def _rule_technical_faults(self, event: Event, cfg: dict):
        codes = cfg.get("faults", {}).get("apparition_codes", [])
        if event.raw_code in codes:
            await self._record_hit(event, "TECHNICAL_FAULT", f"Défaut technique: {event.raw_code}")

    async def _rule_ejection_48h(self, event: Event, cfg: dict):
        ejection_code = cfg.get("ejection", {}).get("code", "570")
        if event.raw_code == ejection_code:
            await self._record_hit(event, "EJECTION_48H", "Éjection détectée (surveillance 48h)")

    async def _rule_inhibition(self, event: Event, cfg: dict):
        inhibition_keyword = cfg.get("inhibition", {}).get("keyword", "***")
        msg = (event.normalized_message or "")
        if inhibition_keyword in msg:
            await self._record_hit(event, "ZONE_INHIBITION", f"Zone inhibée: {msg[:80]}")

    # ─── MOTEUR V2 (règles DB dynamiques) ────────────────────────────────────

    async def evaluate_db_rules(
        self,
        event: Event,
        active_rules: List[AlertRule],
        raw_code_mode: str
    ):
        """Évalue les AlertRule actives avec matching raw_code."""
        for rule in active_rules:
            matched = self._evaluate_single_db_rule(event, rule, raw_code_mode)
            if matched:
                await self._record_hit(
                    event,
                    rule.name,
                    f"[V2] raw_code match (mode={raw_code_mode})",
                    rule_id_override=rule.id
                )

    def _evaluate_single_db_rule(
        self,
        event: Event,
        rule: AlertRule,
        global_raw_code_mode: str
    ) -> bool:
        """
        Évalue une AlertRule sur un Event.
        Supporte :
          - condition_type == "RAW_CODE" : matching via logic_tree ou value
          - logic_tree avec clé raw_code / raw_codes
        """
        if not rule.is_active:
            return False

        # Scope site_code
        if rule.scope_site_code and rule.scope_site_code != event.site_code:
            return False

        # Matching RAW_CODE
        if rule.condition_type == "RAW_CODE":
            rule_cfg: Dict[str, Any] = {}

            if rule.logic_enabled and rule.logic_tree:
                # logic_tree stocke la config de matching
                rule_cfg = rule.logic_tree if isinstance(rule.logic_tree, dict) else {}
            else:
                # Fallback : value = code EXACT ou JSON liste
                raw_val = rule.value or ""
                try:
                    parsed = json.loads(raw_val)
                    if isinstance(parsed, list):
                        rule_cfg = {'raw_codes': parsed}
                    else:
                        rule_cfg = {'raw_code': str(parsed)}
                except (json.JSONDecodeError, TypeError):
                    rule_cfg = {'raw_code': raw_val}

            matched = rule_raw_code_match(event.raw_code, rule_cfg, global_raw_code_mode)
            if matched:
                logger.info(
                    f"[RULE_RAW_CODE_MATCH] rule_id={rule.id} rule_name={rule.name} "
                    f"event_id={event.id} raw_code={event.raw_code} mode={global_raw_code_mode}"
                )
            return matched

        # Autres condition_types non gérés ici (KEYWORD géré par V1)
        return False

    # ─── HELPERS ──────────────────────────────────────────────────────────────

    async def _record_hit(
        self,
        event: Event,
        rule_code: str,
        explanation: str,
        rule_id_override: Optional[int] = None
    ):
        """Enregistre un hit, en évitant les doublons (unique index event_id+rule_id)."""
        rule_id = rule_id_override or await self._resolve_system_rule_id()

        # Check doublon avant insertion (unique index peut lever une erreur)
        existing = await self.session.execute(
            select(EventRuleHit.id).where(
                EventRuleHit.event_id == event.id,
                EventRuleHit.rule_id == rule_id
            )
        )
        if existing.scalar():
            return  # déjà enregistré

        hit = EventRuleHit(
            event_id=event.id,
            rule_id=rule_id,
            rule_name=rule_code,
            hit_metadata={"explanation": explanation}
        )
        self.session.add(hit)
        logger.info(f"[RULE_HIT] {rule_code} (rule_id={rule_id}) event={event.id}")

    async def _resolve_system_rule_id(self) -> int:
        """Trouve l'ID de la règle système ENGINE_V1. Strict mode."""
        stmt = select(AlertRule.id).where(AlertRule.name == 'ENGINE_V1').limit(1)
        result = await self.session.execute(stmt)
        rid = result.scalar()
        if rid:
            return rid

        logger.critical("[ENGINE_V1] System rule ENGINE_V1 missing from alert_rules table!")
        raise RuntimeError("ENGINE_V1 system rule missing. Cannot record legacy hits.")


# ─── REPLAY ENGINE ────────────────────────────────────────────────────────────

async def replay_all_rules(
    session: AsyncSession,
    batch_size: int = 500,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    mode: str = "REPLACE",
    force_full: bool = False
) -> Dict[str, Any]:
    """
    Rejoue les règles sur un scope d'événements (basé sur Event.created_at).
    Mode REPLACE (par défaut) : atomic par tranche (delete hits tranche -> re-eval -> commit).
    Mode FULL : Global delete (nécessite settings.replay_allow_full_clear=True AND force_full=True).
    """
    from sqlalchemy import func as sql_func

    # 1. Vérification des permissions pour FULL
    if mode.upper() == "FULL":
        allow_full = await _get_db_setting(session, 'monitoring.rules.replay_allow_full_clear', False, expected_type=bool)
        if not (allow_full and force_full):
            logger.error("[REPLAY] FULL mode requested but forbidden by settings or missing force flag.")
            raise ValueError("FULL mode is forbidden. Use REPLACE or enable replay_allow_full_clear and use force=true.")

    # 2. Construction du scope (Events)
    stmt_base = select(Event)
    if date_from:
        stmt_base = stmt_base.where(Event.created_at >= date_from)
    if date_to:
        stmt_base = stmt_base.where(Event.created_at <= date_to)

    # Compter avant
    count_before_res = await session.execute(select(sql_func.count()).select_from(EventRuleHit))
    count_before = count_before_res.scalar() or 0

    # Si mode FULL, on vide tout d'un coup (destructive)
    if mode.upper() == "FULL":
        await session.execute(delete(EventRuleHit))
        await session.commit()
        logger.info(f"[REPLAY] FULL CLEAR of event_rule_hits completed ({count_before} rows deleted).")

    engine = BusinessRuleEngine(session)
    active_rules = await engine._load_active_rules()
    raw_code_mode = await engine._raw_code_mode()

    offset = 0
    total_processed = 0
    total_cleared = 0

    logger.info(f"[REPLAY] Starting {mode} scope={date_from or 'ALL'} to {date_to or 'ALL'} batch={batch_size}")

    while True:
        # Fetch batch d'events
        stmt = stmt_base.order_by(Event.id).offset(offset).limit(batch_size)
        result = await session.execute(stmt)
        events = list(result.scalars().all())
        if not events:
            break

        event_ids = [e.id for e in events]
        min_id, max_id = min(event_ids), max(event_ids)

        # REPLACE : Supprimer hits uniquement pour ces events (atomic batch)
        if mode.upper() == "REPLACE":
            res_del = await session.execute(
                delete(EventRuleHit).where(EventRuleHit.event_id.in_(event_ids))
            )
            total_cleared += res_del.rowcount
            logger.debug(f"[REPLAY_REPLACE] Cleared {res_del.rowcount} hits for events [{min_id}..{max_id}]")

        # Réévaluer
        for event in events:
            if await engine._should_exclude_dup(event):
                continue
            await engine.evaluate_legacy_rules(event)
            await engine.evaluate_db_rules(event, active_rules, raw_code_mode)

        # Commit de la tranche
        await session.commit()
        total_processed += len(events)
        offset += batch_size
        logger.info(f"[REPLAY_PROGRESS] Processed {total_processed} events...")

    # Compter après
    count_after_res = await session.execute(select(sql_func.count()).select_from(EventRuleHit))
    count_after = count_after_res.scalar() or 0

    logger.info(
        f"[REPLAY_DONE] mode={mode} processed={total_processed} "
        f"hits_before={count_before} hits_after={count_after}"
    )

    return {
        "status": "SUCCESS",
        "mode": mode,
        "events_processed": total_processed,
        "hits_before": count_before,
        "hits_after": count_after,
        "delta": count_after - (0 if mode == "FULL" else count_before) # Approximate delta for REPLACE
    }
