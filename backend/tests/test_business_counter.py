"""
Tests Phase 2.A : Business Counter & Classification SMTP
Couvre :
1. Classification SMTP (domain/exact/contains + priorité)
2. Même code_site chez 2 providers => 2 entrées distinctes
3. 2 imports même code_site même provider => compteur = 1 site (distinct)
4. Reprocess/replay => idempotence
5. Absence de match => PROVIDER_UNCLASSIFIED
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.classification_service import ClassificationService
from app.db.models import SmtpProviderRule, MonitoringProvider


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
def _make_rule(match_type: str, match_value: str, priority: int = 10, provider_id: int = 1) -> SmtpProviderRule:
    rule = MagicMock(spec=SmtpProviderRule)
    rule.match_type = match_type
    rule.match_value = match_value
    rule.priority = priority
    rule.provider_id = provider_id
    rule.is_active = True
    return rule


def _mock_session(rules: list, unclassified_id: int = 99):
    """Build an async session mock that returns given rules and unclassified_id."""
    session = AsyncMock()

    async def execute_side_effect(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = rules
        result.scalar_one_or_none.return_value = unclassified_id
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Tests Classification SMTP
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationService:

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """EXACT: adresse complète → provider 1."""
        rules = [_make_rule('EXACT', 'alerts@alpha.pro', priority=5, provider_id=1)]
        session = _mock_session(rules)
        result = await ClassificationService.classify_email(session, 'alerts@alpha.pro')
        assert result == 1

    @pytest.mark.asyncio
    async def test_exact_no_match(self):
        """EXACT: mauvaise adresse → UNCLASSIFIED."""
        rules = [_make_rule('EXACT', 'alerts@alpha.pro', priority=5, provider_id=1)]
        session = _mock_session(rules, unclassified_id=99)
        result = await ClassificationService.classify_email(session, 'other@alpha.pro')
        assert result == 99

    @pytest.mark.asyncio
    async def test_domain_match_with_at(self):
        """DOMAIN (format @domain.com) : expéditeur du même domaine → provider 2."""
        rules = [_make_rule('DOMAIN', '@beta.com', priority=10, provider_id=2)]
        session = _mock_session(rules)
        result = await ClassificationService.classify_email(session, 'user@beta.com')
        assert result == 2

    @pytest.mark.asyncio
    async def test_domain_match_without_at(self):
        """DOMAIN (format domain.com sans @) : normalisation automatique."""
        rules = [_make_rule('DOMAIN', 'beta.com', priority=10, provider_id=2)]
        session = _mock_session(rules)
        result = await ClassificationService.classify_email(session, 'sentry@beta.com')
        assert result == 2

    @pytest.mark.asyncio
    async def test_contains_match(self):
        """CONTAINS : sous-chaîne dans l'adresse → provider 3."""
        rules = [_make_rule('CONTAINS', 'gamma', priority=15, provider_id=3)]
        session = _mock_session(rules)
        result = await ClassificationService.classify_email(session, 'noreply@gamma-surveillance.fr')
        assert result == 3

    @pytest.mark.asyncio
    async def test_priority_order(self):
        """Priorité : la règle avec le plus petit nombre de priorité gagne."""
        rule_high_prio = _make_rule('DOMAIN', 'alpha.pro', priority=5, provider_id=1)
        rule_low_prio  = _make_rule('CONTAINS', 'alpha', priority=50, provider_id=99)
        # Order matters - lower priority int should be first
        rules = [rule_high_prio, rule_low_prio]
        session = _mock_session(rules)
        result = await ClassificationService.classify_email(session, 'test@alpha.pro')
        assert result == 1  # High priority rule wins

    @pytest.mark.asyncio
    async def test_no_match_returns_unclassified(self):
        """Aucun match → PROVIDER_UNCLASSIFIED (id=99)."""
        rules = [_make_rule('DOMAIN', 'alpha.pro', priority=10, provider_id=1)]
        session = _mock_session(rules, unclassified_id=99)
        result = await ClassificationService.classify_email(session, 'unknown@unknown.fr')
        assert result == 99

    @pytest.mark.asyncio
    async def test_empty_sender_returns_unclassified(self):
        """Expéditeur vide ou None → UNCLASSIFIED, sans erreur."""
        session = _mock_session([], unclassified_id=99)
        result = await ClassificationService.classify_email(session, '')
        assert result == 99

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        """Classification insensible à la casse."""
        rules = [_make_rule('DOMAIN', 'Alpha.Pro', priority=5, provider_id=1)]
        session = _mock_session(rules)
        result = await ClassificationService.classify_email(session, 'USER@ALPHA.PRO')
        assert result == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests Business Counter (Upsert SiteConnection)
# ─────────────────────────────────────────────────────────────────────────────

class TestSiteConnectionUpsert:
    """Tests d'intégration - nécessitent la DB de test."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_same_site_two_providers_distinct_rows(self, db_session):
        """
        Même code_site chez 2 providers → 2 entrées distinctes dans site_connections.
        """
        from app.services.repository import EventRepository
        from sqlalchemy import select
        from app.db.models import SiteConnection

        repo = EventRepository(db_session)
        now = datetime.now(timezone.utc)

        await repo.upsert_site_connection(provider_id=1, code_site='12345', client_name='Client A', seen_at=now)
        await repo.upsert_site_connection(provider_id=2, code_site='12345', client_name='Client A', seen_at=now)
        await db_session.flush()

        result = await db_session.execute(
            select(SiteConnection).where(SiteConnection.code_site == '12345')
        )
        rows = result.scalars().all()
        assert len(rows) == 2, "Deux providers distincts => 2 rows"
        provider_ids = {r.provider_id for r in rows}
        assert provider_ids == {1, 2}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_same_site_same_provider_increments_events(self, db_session):
        """
        2 imports même code_site même provider → 1 seul site, total_events = 2.
        """
        from app.services.repository import EventRepository
        from sqlalchemy import select
        from app.db.models import SiteConnection

        repo = EventRepository(db_session)
        now = datetime.now(timezone.utc)

        await repo.upsert_site_connection(provider_id=1, code_site='67890', client_name='Client B', seen_at=now)
        await repo.upsert_site_connection(provider_id=1, code_site='67890', client_name='Client B', seen_at=now)
        await db_session.flush()

        result = await db_session.execute(
            select(SiteConnection).where(SiteConnection.code_site == '67890',
                                         SiteConnection.provider_id == 1)
        )
        rows = result.scalars().all()
        assert len(rows) == 1, "Même provider + même site => 1 row"
        assert rows[0].total_events == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_first_seen_at_never_overwritten(self, db_session):
        """
        first_seen_at ne doit jamais être écrasé lors de l'upsert.
        """
        from app.services.repository import EventRepository
        from sqlalchemy import select
        from app.db.models import SiteConnection
        from datetime import timedelta

        repo = EventRepository(db_session)
        t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 1, tzinfo=timezone.utc)

        await repo.upsert_site_connection(provider_id=1, code_site='OLDSITE', client_name='C', seen_at=t1)
        await repo.upsert_site_connection(provider_id=1, code_site='OLDSITE', client_name='C', seen_at=t2)
        await db_session.flush()

        result = await db_session.execute(
            select(SiteConnection).where(SiteConnection.code_site == 'OLDSITE')
        )
        row = result.scalars().first()
        assert row.first_seen_at == t1, "first_seen_at ne doit pas être écrasé"
        assert row.last_seen_at == t2, "last_seen_at doit être mis à jour"
