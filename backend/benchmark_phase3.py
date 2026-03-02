import asyncio
import logging
import json
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def benchmark():
    async with AsyncSessionLocal() as session:
        # User requirement: Provide proof EXPLAIN ANALYZE for /alerts
        query = """
        EXPLAIN ANALYZE
        SELECT 
            erh.id as hit_id,
            erh.rule_id,
            erh.rule_name,
            erh.score,
            erh.created_at,
            e.site_code,
            e.client_name,
            p.label as provider_name,
            e.id as event_id,
            e.import_id
        FROM event_rule_hits erh
        JOIN events e ON erh.event_id = e.id
        LEFT OUTER JOIN imports i ON e.import_id = i.id
        LEFT OUTER JOIN monitoring_providers p ON i.provider_id = p.id
        ORDER BY erh.created_at DESC
        LIMIT 50;
        """
        
        result = await session.execute(text(query))
        plan = "\n".join([row[0] for row in result.all()])
        print("--- EXPLAIN ANALYZE PLAN ---")
        print(plan)
        print("----------------------------")

if __name__ == "__main__":
    asyncio.run(benchmark())
