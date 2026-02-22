import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:8000"
EMAIL = "admin@supervision.local"
PASSWORD = "SuperSecurePassword123"

def make_request(url, method='GET', data=None, headers=None):
    if headers is None:
        headers = {}
    
    if data:
        data = urllib.parse.urlencode(data).encode('utf-8')
        # urllib defaults to POST if data is present
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 0, str(e)

def test_backend():
    print("1. Checking Health...")
    status, _ = make_request(f"{BASE_URL}/health")
    print(f"   Status: {status}")
    if status != 200:
        print("   ERROR: Backend not healthy")
        sys.exit(1)

    print("\n2. Testing Login (Get Token)...")
    status, body = make_request(f"{BASE_URL}/api/v1/auth/login/access-token", 
                                method='POST', 
                                data={"username": EMAIL, "password": PASSWORD})
    print(f"   Status: {status}")
    if status != 200:
        print(f"   ERROR: Login failed. {body}")
        sys.exit(1)
    
    token = body["access_token"]
    print(f"   Token received (len={len(token)})")

    print("\n3. Testing Protected Route (Imports)...")
    headers = {"Authorization": f"Bearer {token}"}
    status, body = make_request(f"{BASE_URL}/api/v1/imports?limit=1", headers=headers)
    print(f"   Status: {status}")
    if status == 200:
        print(f"   Success! Retrieved {len(body) if isinstance(body, list) else 'data'}.")
    else:
        print(f"   ERROR: Failed to access protected route. {body}")
        sys.exit(1)

    print("\n✅ DIAGNOSTIC SUCCESS: Backend Auth is working perfectly.")

if __name__ == "__main__":
    test_backend()
