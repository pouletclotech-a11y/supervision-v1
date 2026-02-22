import asyncio
import logging
from app.db.session import AsyncSessionLocal
from app.db.models import Setting
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_settings():
    logger.info("Initializing Settings...")
    defaults = {
        'imap_host': 'ssl0.ovh.net',
        'imap_port': '993',
        'imap_user': 'user@domain.com',
        'imap_password': '',
        'whitelist_senders': '[]',
        'attachment_types': '["pdf", "xlsx", "xls"]',
        'cleanup_mode': 'MOVE',
        'imap_folder': 'Processed',
        'smtp_host': 'ssl0.ovh.net',
        'smtp_port': '465'
    }

    async with AsyncSessionLocal() as db:
        for key, val in defaults.items():
            stmt = select(Setting).where(Setting.key == key)
            result = await db.execute(stmt)
            obj = result.scalar_one_or_none()
            
            if not obj:
                logger.info(f"Creating default setting: {key}")
                db.add(Setting(key=key, value=val, description="Default"))
            else:
                logger.info(f"Setting {key} exists. Skipping.")
        
        await db.commit()
    logger.info("Settings initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_settings())
