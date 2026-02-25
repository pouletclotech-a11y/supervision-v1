import logging
import re
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import SmtpProviderRule, MonitoringProvider

logger = logging.getLogger("classification-service")

class ClassificationService:
    @staticmethod
    async def classify_email(session: AsyncSession, sender_email: str) -> int:
        """
        Classify an email based on its sender address.
        Uses smtp_provider_rules in DB with priorities (lower priority = checked first).
        Returns provider_id or the ID for PROVIDER_UNCLASSIFIED if no match.
        """
        if not sender_email:
            return await ClassificationService.get_unclassified_id(session)

        # 1. Fetch active rules ordered by priority (lower first)
        stmt = (
            select(SmtpProviderRule)
            .where(SmtpProviderRule.is_active == True)
            .order_by(SmtpProviderRule.priority.asc())
        )
        result = await session.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            match = False
            match_type = rule.match_type.upper()
            pattern = rule.match_value.lower()
            sender_lower = sender_email.lower()

            if match_type in ['EXACT', 'EMAIL']:
                if sender_lower == pattern:
                    match = True
            elif match_type == 'DOMAIN':
                # Handles both "@domain.com" and "domain.com"
                domain_pattern = pattern if pattern.startswith('@') else f"@{pattern}"
                if sender_lower.endswith(domain_pattern):
                    match = True
            elif match_type == 'CONTAINS':
                if pattern in sender_lower:
                    match = True
            elif match_type == 'REGEX':
                try:
                    if re.search(pattern, sender_lower):
                        match = True
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern}' for rule {rule.id}: {e}")

            if match:
                logger.info(f"Email {sender_email} matched rule {rule.id} (Type: {match_type}) -> Provider {rule.provider_id}")
                return rule.provider_id

        # 2. No match found -> Return UNCLASSIFIED
        return await ClassificationService.get_unclassified_id(session)

    @staticmethod
    async def get_unclassified_id(session: AsyncSession) -> int:
        stmt = select(MonitoringProvider.id).where(MonitoringProvider.code == 'PROVIDER_UNCLASSIFIED')
        result = await session.execute(stmt)
        provider_id = result.scalar_one_or_none()
        
        if not provider_id:
            logger.error("PROVIDER_UNCLASSIFIED not found in monitoring_providers. Seed might be missing.")
            # Fallback to a safe check (or let it fail if critical)
            return None
            
        return provider_id
