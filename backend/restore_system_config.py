import asyncio
import os
import logging
import sys
from datetime import datetime
from sqlalchemy import select, func, text
from app.db.session import AsyncSessionLocal
from app.db.models import Setting, MonitoringProvider, SmtpProviderRule, User, Site, Event

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("restorer")

async def get_counts():
    async with AsyncSessionLocal() as session:
        site_count = await session.scalar(select(func.count()).select_from(Site))
        user_count = await session.scalar(select(func.count()).select_from(User))
        event_count = await session.scalar(select(func.count()).select_from(Event))
        return site_count, user_count, event_count

async def restore():
    logger.info("--- DEBUT DE LA RESTAURATION DE CONFIGURATION ---")
    
    # 1. Verification de sécurité pre-flight
    imap_password = os.getenv("IMAP_PASSWORD")
    logger.info(f"IMAP_PASSWORD présent: {'OUI' if imap_password else 'NON'}")
    
    if not imap_password:
        logger.error("ERREUR: La variable d'environnement IMAP_PASSWORD est manquante.")
        sys.exit(1)
        
    site_pre, user_pre, event_pre = await get_counts()
    logger.info(f"Compteurs PRE-EXECUTION: Sites={site_pre}, Users={user_pre}, Events={event_pre}")

    async with AsyncSessionLocal() as session:
        # 2. Restauration des SETTINGS (IMAP)
        settings_to_upsert = {
            "imap_host": "ssl0.ovh.net",
            "imap_user": "tls@ypsilon-manager.fr",
            "imap_password": imap_password,
            "imap_port": "993",
            "imap_folder": "inbox",
            "cleanup_mode": "MOVE"
        }
        
        for key, value in settings_to_upsert.items():
            result = await session.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                session.add(Setting(key=key, value=value))
        
        # 3. Restauration des PROVIDERS (CORS, SPGO, UNCLASSIFIED)
        # On définit les fréquences : 4 par 24H -> interval de 360 min (1440/4)
        providers_data = [
            {
                "code": "PROVIDER_UNCLASSIFIED",
                "label": "Unclassified",
                "is_active": True,
                "expected_emails_per_day": 0,
                "expected_interval_minutes": 0
            },
            {
                "code": "CORS",
                "label": "CORS Monitoring",
                "recovery_email": "noreply@cors-online.fr",
                "expected_emails_per_day": 4,
                "expected_interval_minutes": 360,
                "accepted_attachment_types": ["pdf", "xlsx"],
                "email_match_keyword": "YPSILON_HISTO"
            },
            {
                "code": "SPGO",
                "label": "SPGO Monitoring",
                "recovery_email": "cortis@spgo.fr",
                "expected_emails_per_day": 4,
                "expected_interval_minutes": 360,
                "accepted_attachment_types": ["pdf", "xls"],
                "email_match_keyword": "YPSILON"
            }
        ]
        
        for p_data in providers_data:
            result = await session.execute(select(MonitoringProvider).where(MonitoringProvider.code == p_data["code"]))
            provider = result.scalar_one_or_none()
            
            if provider:
                for k, v in p_data.items():
                    setattr(provider, k, v)
                provider.is_active = True
            else:
                provider = MonitoringProvider(**p_data)
                session.add(provider)
            
            await session.flush() # Pour avoir l'ID
            
            # 4. Règles SMTP rattachées
            rule_match = p_data.get("recovery_email")
            if rule_match:
                rule_res = await session.execute(
                    select(SmtpProviderRule).where(
                        SmtpProviderRule.provider_id == provider.id,
                        SmtpProviderRule.match_value == rule_match
                    )
                )
                rule = rule_res.scalar_one_or_none()
                if not rule:
                    session.add(SmtpProviderRule(
                        provider_id=provider.id,
                        match_type="EMAIL",
                        match_value=rule_match,
                        priority=10,
                        is_active=True
                    ))
            else:
                logger.info(f"Skipping SMTP rule for {p_data['code']} (no recovery_email)")

        await session.commit()

    # 5. Vérification post-flight
    site_post, user_post, event_post = await get_counts()
    logger.info(f"Compteurs POST-EXECUTION: Sites={site_post}, Users={user_post}, Events={event_post}")
    
    if (site_pre, user_pre, event_pre) == (site_post, user_post, event_post):
        logger.info("VERIFICATION REUSSIE: Aucune donnée utilisateur n'a été altérée (Sites/Users/Events).")
    else:
        logger.error("ALERTE: Les compteurs de données ont changé ! Restauration suspecte.")

    logger.info("--- FIN DE LA RESTAURATION ---")

if __name__ == "__main__":
    asyncio.run(restore())
