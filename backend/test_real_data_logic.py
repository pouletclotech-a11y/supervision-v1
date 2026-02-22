import asyncio
import os
import sys
import pytz
from datetime import datetime

# Add backend to path
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
from app.services.tagging_service import TaggingService
from app.services.alerting import AlertingService
from app.utils.text import normalize_text, clean_excel_value
from app.ingestion.models import NormalizedEvent

async def test_real_data_logic():
    async with AsyncSessionLocal() as session:
        tagger = TaggingService(session)
        alert_service = AlertingService()
        repo = EventRepository(session)
        
        # 1. Test Normalization
        print("--- Testing Normalization ---")
        t1 = '="ALARME INTRUSION zon 04 : IR ENTR CLIENT"'
        norm = normalize_text(t1)
        print(f"Original: {t1} -> Normalized: {norm}")
        assert "alarme intrusion" in norm
        assert "entr" in norm # sans accent
        
        # 2. Test Tagging (Keyword based)
        print("\n--- Testing Tagging (Keyword ALARME INTRUSION) ---")
        e_intrusion = NormalizedEvent(
            timestamp=datetime.now(),
            site_code="TEST_REAL",
            event_type="APPARITION",
            raw_message='="ALARME INTRUSION zone 04 : IR ENTRÉE CLIENT"',
            normalized_message=normalize_text('="ALARME INTRUSION zone 04 : IR ENTRÉE CLIENT"'),
            source_file="test.xls"
        )
        tagged = await tagger.tag_event(e_intrusion)
        print(f"Intrusion Category: {tagged.category}, Status: {tagged.status}")
        assert tagged.category == "security"
        assert tagged.status == "CRITICAL"
        
        # 3. Test Tagging (CAM pattern)
        print("\n--- Testing Tagging (CAM Pattern) ---")
        e_cam = NormalizedEvent(
            timestamp=datetime.now(),
            site_code="TEST_REAL",
            event_type="APPARITION",
            raw_message='="CAM4-1 : Connexion, Résultat succès"',
            normalized_message=normalize_text('="CAM4-1 : Connexion, Résultat succès"'),
            source_file="test.xls"
        )
        tagged_cam = await tagger.tag_event(e_cam)
        print(f"CAM Category: {tagged_cam.category}, Alertable: {tagged_cam.alertable_default}")
        assert tagged_cam.category == "camera"
        assert tagged_cam.alertable_default is False
        
        # 4. Test Alerting (Keyword in Rule)
        print("\n--- Testing Alerting (Keyword Match) ---")
        from app.db.models import AlertRule
        rule_intrusion = AlertRule(
            name="ALERT_INTRUSION",
            match_keyword="Intrusion", # Mixed casing
            is_active=True,
            logic_enabled=False
        )
        # Even if rule is simple V3, evaluate_rule now uses normalized_message
        res = await alert_service.evaluate_rule(tagged, rule_intrusion, repo=repo)
        print(f"Alert Triggered (Intrusion): {res['triggered']}")
        assert res["triggered"] is True
        
        print("\n--- Testing Alerting (No Match) ---")
        rule_other = AlertRule(
            name="ALERT_FIRE",
            match_keyword="FEU",
            is_active=True
        )
        res_fire = await alert_service.evaluate_rule(tagged, rule_other, repo=repo)
        print(f"Alert Triggered (Fire on Intrusion): {res_fire['triggered']}")
        assert res_fire["triggered"] is False

        print("\n✅ ALL REAL DATA TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_real_data_logic())
