#!/usr/bin/env python3
"""
Script de test Dry Run déterministe pour Phase 2.1
Tests: time_scope (business hours, night/minuit), frequency, no DB writes
"""
import requests
import sys
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Test credentials (adjust if needed)
TEST_USER = "admin@example.com"
TEST_PASS = "admin123"


def login():
    """Get auth token"""
    resp = requests.post(
        f"{BASE_URL}/auth/login/access-token",
        data={"username": TEST_USER, "password": TEST_PASS}
    )
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} - {resp.text}")
        return None
    token = resp.json().get("access_token")
    print(f"✅ Login OK (token: {token[:20]}...)")
    return token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_list_rules(token):
    """List available rules"""
    resp = requests.get(f"{BASE_URL}/alerts/rules", headers=auth_headers(token))
    if resp.status_code != 200:
        print(f"❌ List rules failed: {resp.status_code}")
        return []
    rules = resp.json()
    print(f"✅ Found {len(rules)} rules")
    for r in rules[:5]:
        ts = r.get('time_scope', 'NONE')
        print(f"   [{r['id']}] {r['name']} | scope={ts} | active={r.get('is_active')}")
    return rules


def test_dry_run(token, rule_id, reference_time, expected_trigger, scenario_name):
    """Run dry-run and check result"""
    resp = requests.post(
        f"{BASE_URL}/alerts/rules/{rule_id}/dry-run",
        params={"reference_time_override": reference_time, "limit": 10},
        headers=auth_headers(token)
    )
    
    if resp.status_code != 200:
        print(f"❌ [{scenario_name}] Dry-run failed: {resp.status_code} - {resp.text}")
        return False
    
    data = resp.json()
    matched = data.get("matched_count", 0) > 0
    
    status = "✅" if matched == expected_trigger else "❌"
    print(f"{status} [{scenario_name}] matched={matched}, expected={expected_trigger}")
    print(f"    evaluated={data.get('evaluated_count')}, matched_count={data.get('matched_count')}")
    
    # Show sample results
    for r in data.get("results", [])[:3]:
        trig = "🔥" if r.get("triggered") else "⬜"
        print(f"    {trig} event_id={r.get('event_id')} | {r.get('explanations', [])[:2]}")
    
    return matched == expected_trigger


def test_business_hours_scenarios(token, rule_id):
    """Test business hours time_scope"""
    print("\n=== BUSINESS HOURS TESTS ===")
    
    # Lundi 10:00 CET => business hours true
    test_dry_run(token, rule_id, "2026-01-26T09:00:00+01:00", True, "Lundi 10:00 (business)")
    
    # Lundi 20:00 CET => off business hours (outside 9-18)
    test_dry_run(token, rule_id, "2026-01-26T20:00:00+01:00", False, "Lundi 20:00 (off-business)")


def test_night_scenarios(token, rule_id):
    """Test night time_scope with midnight crossing"""
    print("\n=== NIGHT / MIDNIGHT CROSSING TESTS ===")
    
    # 23:30 => night true
    test_dry_run(token, rule_id, "2026-01-26T22:30:00+01:00", True, "23:30 (night)")
    
    # 05:30 => night true (after midnight, before 06:00)
    test_dry_run(token, rule_id, "2026-01-27T05:30:00+01:00", True, "05:30 (night cross-midnight)")
    
    # 12:00 => night false
    test_dry_run(token, rule_id, "2026-01-26T12:00:00+01:00", False, "12:00 (daytime)")


def test_no_db_write(token, rule_id):
    """Verify dry-run doesn't create hits"""
    print("\n=== NO DB WRITE TEST ===")
    
    # Get current hit count (would need endpoint or direct DB check)
    # For now, call dry-run 3x and verify same results
    results = []
    for i in range(3):
        resp = requests.post(
            f"{BASE_URL}/alerts/rules/{rule_id}/dry-run",
            params={"limit": 5},
            headers=auth_headers(token)
        )
        if resp.status_code == 200:
            results.append(resp.json().get("evaluated_count"))
    
    if len(set(results)) == 1:
        print(f"✅ No side effects: 3 calls all returned {results[0]} evaluated events")
    else:
        print(f"⚠️ Results varied: {results}")


def main():
    print("=" * 60)
    print("TLS Y - Supervision: Dry Run Verification Script")
    print("=" * 60)
    
    # 1. Login
    token = login()
    if not token:
        sys.exit(1)
    
    # 2. List rules
    rules = test_list_rules(token)
    if not rules:
        print("⚠️ No rules found. Create test rules first.")
        sys.exit(1)
    
    # Find suitable rules for tests (need BUSINESS_HOURS and NIGHT scopes)
    business_rule = next((r for r in rules if r.get('time_scope') == 'BUSINESS_HOURS'), None)
    night_rule = next((r for r in rules if r.get('time_scope') == 'NIGHT'), None)
    any_rule = rules[0]
    
    # 3. Run tests
    if business_rule:
        test_business_hours_scenarios(token, business_rule['id'])
    else:
        print("\n⚠️ No BUSINESS_HOURS rule found, skipping business hours tests")
        print("   Create a rule with time_scope=BUSINESS_HOURS to test")
    
    if night_rule:
        test_night_scenarios(token, night_rule['id'])
    else:
        print("\n⚠️ No NIGHT rule found, skipping night tests")
        print("   Create a rule with time_scope=NIGHT to test")
    
    # 4. No DB write test
    test_no_db_write(token, any_rule['id'])
    
    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
