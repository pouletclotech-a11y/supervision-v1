import asyncio
from app.db.session import AsyncSessionLocal
from app.ingestion.profile_manager import ProfileManager

async def main():
    async with AsyncSessionLocal() as db:
        pm = ProfileManager()
        await pm.load_profiles(db)
        profiles = pm.list_profiles()
        for p in sorted(profiles, key=lambda x: x.priority, reverse=True):
            print(f"Profile: {p.profile_id} | format_kind={p.format_kind} | provider={p.provider_code}")
            print(f"  extensions={p.detection.extensions}")
            print(f"  filename_pattern={p.detection.filename_pattern}")
            print(f"  filename_regex={p.filename_regex}")
            print()

asyncio.run(main())
