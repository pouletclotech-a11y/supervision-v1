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


async def _get_db_setting(session: AsyncSession, key: str, default: Any) -> Any:
    """Lire un setting depuis la table DB (override par rapport au YAML)."""
    try:
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            return json.loads(setting.value)
    except Exception:
        pass
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
        exclude = await _get_db_setting(self.session, 'monitoring.rules.exclude_dup_count', exclude)
        return bool(exclude) and (event.dup_count or 0) > 0

    async def _raw_code_mode(self) -> str:
        cfg = await self._rules_config()
        default_mode = cfg.get('raw_code_mode', 'IN').upper()
        return await _get_db_setting(self.session, 'monitoring.rules.raw_code_mode', default_mode)

    async def evaluate_batch(self, events: List[Event]):
        """Évalue toutes les règles pour un lot d'événements persistés."""
        # Charger les règles actives une seule fois pour tout le batch
        active_rules = await self._load_active_rules()
        raw_code_mode = await self._raw_code_mode()

        for event in events:
            # Filtre dup_count
            if await self._should_exclude_dup(event):
                logger.debug(f"[RULE_DUP_EXCLUDED] event_id={event.id} dup_count={event.dup_count}")
                continue

            # Moteur V1 hérité (règles hardcodées ENGINE_V1)
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
        """Trouve l'ID de la règle système ENGINE_V1 ou fallback à 1."""
        stmt = select(AlertRule.id).where(AlertRule.name == 'ENGINE_V1').limit(1)
        result = await self.session.execute(stmt)
        rid = result.scalar()
        if rid:
            return rid
        # Fallback: première règle active
        stmt2 = select(AlertRule.id).where(AlertRule.is_active == True).order_by(AlertRule.id).limit(1)
        result2 = await self.session.execute(stmt2)
        rid2 = result2.scalar()
        return rid2 or 1


# ─── REPLAY ENGINE ────────────────────────────────────────────────────────────

async def replay_all_rules(session: AsyncSession, batch_size: int = 500) -> Dict[str, int]:
    """
    Rejoue toutes les règles sur l'ensemble des événements.
    1. Vide event_rule_hits
    2. Réévalue par batch
    3. Retourne les stats
    """
    from sqlalchemy import func as sql_func

    # Compter avant
    count_before_result = await session.execute(select(sql_func.count()).select_from(EventRuleHit))
    count_before = count_before_result.scalar() or 0

    # Vider hits (pas les règles elles-mêmes)
    await session.execute(delete(EventRuleHit))
    await session.commit()
    logger.info(f"[REPLAY_ALL] Cleared {count_before} event_rule_hits. Starting re-evaluation.")

    engine = BusinessRuleEngine(session)
    active_rules = await engine._load_active_rules()
    raw_code_mode = await engine._raw_code_mode()

    # Paginer sur les events
    offset = 0
    total_processed = 0
    total_hits = 0

    while True:
        result = await session.execute(
            select(Event).order_by(Event.id).offset(offset).limit(batch_size)
        )
        events = list(result.scalars().all())
        if not events:
            break

        for event in events:
            if await engine._should_exclude_dup(event):
                logger.debug(f"[REPLAY_DUP_EXCLUDED] event_id={event.id}")
                continue
            await engine.evaluate_legacy_rules(event)
            await engine.evaluate_db_rules(event, active_rules, raw_code_mode)

        await session.commit()
        total_processed += len(events)
        offset += batch_size
        logger.info(f"[REPLAY_ALL] Processed {total_processed} events so far...")

    # Compter après
    count_after_result = await session.execute(select(sql_func.count()).select_from(EventRuleHit))
    count_after = count_after_result.scalar() or 0
    total_hits = count_after

    logger.info(
        f"[REPLAY_ALL] Done. events_processed={total_processed} "
        f"hits_before={count_before} hits_after={count_after}"
    )

    return {
        "events_processed": total_processed,
        "hits_before": count_before,
        "hits_after": count_after,
        "delta": count_after - count_before,
    }
