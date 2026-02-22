"""
Provider Resolver: Résolution du télésurveilleur depuis l'email expéditeur SMTP.
Ordre de priorité: EXACT > DOMAIN > REGEX, puis par priority DESC.
"""
import re
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import SmtpProviderRule, MonitoringProvider

logger = logging.getLogger("provider-resolver")


class ProviderResolver:
    """Résout le provider_id depuis une adresse email source."""
    
    async def resolve_provider(
        self, 
        from_email: str, 
        db: AsyncSession
    ) -> Optional[int]:
        """
        Résout le provider_id depuis l'email expéditeur.
        
        Args:
            from_email: Adresse email complète (ex: alerts@spgo.fr)
            db: Session DB async
            
        Returns:
            provider_id si trouvé, None sinon
        """
        if not from_email:
            return None
            
        from_email_lower = from_email.lower().strip()
        
        # Extraire le domaine
        domain = None
        if '@' in from_email_lower:
            domain = from_email_lower.split('@')[1]
        
        # Récupérer toutes les règles actives, triées par priorité DESC
        stmt = (
            select(SmtpProviderRule)
            .where(SmtpProviderRule.is_active == True)
            .order_by(SmtpProviderRule.priority.desc())
        )
        result = await db.execute(stmt)
        rules = result.scalars().all()
        
        # Séparer par type pour respecter l'ordre EXACT > DOMAIN > REGEX
        exact_rules = [r for r in rules if r.match_type == 'EXACT']
        domain_rules = [r for r in rules if r.match_type == 'DOMAIN']
        regex_rules = [r for r in rules if r.match_type == 'REGEX']
        
        # 1. EXACT match
        for rule in exact_rules:
            if from_email_lower == rule.match_value.lower():
                logger.debug(f"EXACT match: {from_email} -> provider_id={rule.provider_id}")
                return rule.provider_id
        
        # 2. DOMAIN match
        if domain:
            for rule in domain_rules:
                # match_value stocke le domaine sans @ (ex: spgo.fr)
                if domain == rule.match_value.lower():
                    logger.debug(f"DOMAIN match: {from_email} -> provider_id={rule.provider_id}")
                    return rule.provider_id
        
        # 3. REGEX match
        for rule in regex_rules:
            try:
                if re.search(rule.match_value, from_email_lower, re.IGNORECASE):
                    logger.debug(f"REGEX match: {from_email} -> provider_id={rule.provider_id}")
                    return rule.provider_id
            except re.error as e:
                logger.warning(f"Invalid regex in rule {rule.id}: {e}")
                continue
        
        logger.debug(f"No provider match for: {from_email}")
        return None
    
    async def get_provider_by_id(
        self, 
        provider_id: int, 
        db: AsyncSession
    ) -> Optional[MonitoringProvider]:
        """Récupère un provider par son ID."""
        stmt = select(MonitoringProvider).where(MonitoringProvider.id == provider_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_providers(
        self, 
        db: AsyncSession, 
        active_only: bool = True
    ) -> list:
        """Récupère tous les providers."""
        stmt = select(MonitoringProvider)
        if active_only:
            stmt = stmt.where(MonitoringProvider.is_active == True)
        stmt = stmt.order_by(MonitoringProvider.code)
        result = await db.execute(stmt)
        return result.scalars().all()
