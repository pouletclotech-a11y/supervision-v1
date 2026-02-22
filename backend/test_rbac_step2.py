import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://backend:8000"

def login(email, password):
    data = urllib.parse.urlencode({"username": email, "password": password}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login/access-token", data=data, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)["access_token"]
    except Exception as e:
        print(f"Login failed for {email}: {e}")
        return None

def api_call(token, path, method='GET', data=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(f"{BASE_URL}/api/v1{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except:
            return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 0, str(e)

def test_step2():
    print("--- Phase 4 Step 2: RBAC CRUD SMTP Rules Test ---")
    
    tokens = {
        "OPERATOR": login("operator_test@test.com", "password123"),
        "ADMIN": login("admin_test@test.com", "password123")
    }

    # 1. Setup Provider
    status, body = api_call(tokens["OPERATOR"], "/connections/providers", method='POST', data={"code": "RT", "label": "Rule Test"})
    if status != 200 and status != 400: # 400 if already exists
        print(f"❌ Setup failed: could not create provider. Status {status}")
        return
    
    # Get ID (might be first or second call)
    status, bodyList = api_call(tokens["OPERATOR"], "/connections/providers")
    provider_id = [p["id"] for p in bodyList if p["code"] == "RT"][0]
    print(f"✅ Provider RT (ID: {provider_id}) ready.")

    # 2. TEST OPERATOR: Create Rule
    print("\n[OPERATOR: CREATE RULE]")
    status, rule = api_call(tokens["OPERATOR"], f"/connections/providers/{provider_id}/rules", method='POST', 
                            data={"match_type": "DOMAIN", "match_value": "test.com", "priority": 50})
    print(f"POST /rules: Status {status}")
    if status == 200:
        rule_id = rule["id"]
        print(f"✅ Created Rule ID {rule_id}")
        
        # 3. TEST OPERATOR: Update Rule
        print("\n[OPERATOR: UPDATE RULE]")
        status, updated = api_call(tokens["OPERATOR"], f"/connections/providers/{provider_id}/rules/{rule_id}", method='PATCH', 
                                   data={"match_value": "test.org", "priority": 100})
        print(f"PATCH /rules: Status {status}")
        if status == 200 and updated["match_value"] == "test.org":
            print("✅ SUCCESS: Updated rule as Operator")
        else:
            print(f"❌ FAIL: Update failed. Status {status}")

        # 4. TEST INVALID MATCH_TYPE
        print("\n[VALIDATION: INVALID TYPE]")
        status, err = api_call(tokens["OPERATOR"], f"/connections/providers/{provider_id}/rules", method='POST', 
                               data={"match_type": "INVALID", "match_value": "foo"})
        print(f"POST /rules (INVALID): Status {status} (Expected 400)")

        # 5. TEST DELETE RBAC
        print("\n[DELETE RBAC TEST]")
        status, body = api_call(tokens["OPERATOR"], f"/connections/providers/{provider_id}/rules/{rule_id}", method='DELETE')
        print(f"DELETE rule as Operator: Status {status} (Expected 403)")
        
        status, body = api_call(tokens["ADMIN"], f"/connections/providers/{provider_id}/rules/{rule_id}", method='DELETE')
        print(f"DELETE rule as Admin: Status {status} (Expected 200)")
        if status == 200: print("✅ SUCCESS: Admin deleted rule")
        
        # Cleanup Provider
        api_call(tokens["ADMIN"], f"/connections/providers/{provider_id}", method='DELETE')
        print("✅ Cleaned up provider.")
    else:
        print(f"❌ FAIL: Operator could not create rule. {rule}")

if __name__ == "__main__":
    test_step2()
