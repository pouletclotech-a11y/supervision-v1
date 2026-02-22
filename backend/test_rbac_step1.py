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
            return e.code, e.reason
    except Exception as e:
        return 0, str(e)

def test_step1():
    print("--- Phase 4 Step 1: RBAC CRUD Providers Test ---")
    
    tokens = {
        "VIEWER": login("viewer_test@test.com", "password123"),
        "OPERATOR": login("operator_test@test.com", "password123"),
        "ADMIN": login("admin_test@test.com", "password123")
    }

    # 1. TEST VIEWER: Can Read, Cannot Create
    print("\n[VIEWER TEST]")
    status, body = api_call(tokens["VIEWER"], "/connections/providers")
    print(f"GET /providers: Status {status}")
    
    status, body = api_call(tokens["VIEWER"], "/connections/providers", method='POST', data={"code": "FAIL", "label": "Viewer Should Fail"})
    print(f"POST /providers (Unauthorized): Status {status} (Expected 403)")
    if status != 403: print("❌ FAIL: Viewer should not be able to create provider")

    # 2. TEST OPERATOR: Can Create and Update
    print("\n[OPERATOR TEST]")
    status, body = api_call(tokens["OPERATOR"], "/connections/providers", method='POST', data={"code": "ABC", "label": "ABC Security"})
    print(f"POST /providers (ABC): Status {status}")
    if status == 200:
        abc_id = body["id"]
        print(f"✅ SUCCESS: Created ABC provider with ID {abc_id}")
        
        status, body = api_call(tokens["OPERATOR"], f"/connections/providers/{abc_id}", method='PATCH', data={"label": "ABC Security Updated"})
        print(f"PATCH /providers/ABC: Status {status}")
        if status == 200: print("✅ SUCCESS: Updated label as Operator")
        
        # 3. TEST DELETE RBAC
        print("\n[DELETE RBAC TEST]")
        status, body = api_call(tokens["OPERATOR"], f"/connections/providers/{abc_id}", method='DELETE')
        print(f"DELETE /providers/ABC as Operator: Status {status} (Expected 403)")
        
        status, body = api_call(tokens["VIEWER"], f"/connections/providers/{abc_id}", method='DELETE')
        print(f"DELETE /providers/ABC as Viewer: Status {status} (Expected 403)")

        status, body = api_call(tokens["ADMIN"], f"/connections/providers/{abc_id}", method='DELETE')
        print(f"DELETE /providers/ABC as Admin: Status {status} (Expected 200)")
        if status == 200: print("✅ SUCCESS: Admin deleted provider")
    else:
        print(f"❌ FAIL: Operator could not create provider. {body}")

if __name__ == "__main__":
    test_step1()
