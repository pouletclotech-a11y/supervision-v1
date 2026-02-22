import requests
import sys

BASE_URL = "http://localhost:8000/api/v1"

def login(email, password):
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login/access-token",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"Login failed for {email}: {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def test_admin_access(token):
    print("\n--- TEST 1: Admin Access to /users ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/users", headers=headers)
    if response.status_code == 200:
        print("✅ SUCCESS: Admin accessed /users")
        users = response.json()
        print(f"Users found: {len(users)}")
        return users
    else:
        print(f"❌ FAILED: Admin cannot access /users. Status: {response.status_code}")
        print(response.text)
        return None

def create_viewer(token):
    print("\n--- Setup: Creating Viewer User ---")
    headers = {"Authorization": f"Bearer {token}"}
    viewer_email = "viewer_test@supervision.local"
    viewer_pass = "ViewerPass123"
    
    # Check if exists (by trying login or listing) - simpler just to try create and ignore 400
    user_data = {
        "email": viewer_email,
        "password": viewer_pass,
        "role": "VIEWER",
        "full_name": "Test Viewer"
    }
    
    response = requests.post(f"{BASE_URL}/users", json=user_data, headers=headers)
    if response.status_code in [200, 201]:
        print("✅ SUCCESS: Viewer user created")
    elif response.status_code == 400 and "already exists" in response.text:
        print("⚠️ Viewer user already exists (skipping creation)")
    else:
        print(f"❌ FAILED to create viewer: {response.status_code} {response.text}")
    
    return viewer_email, viewer_pass

def test_viewer_access(token):
    print("\n--- TEST 2: Viewer Access to /users ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/users", headers=headers)
    if response.status_code == 403:
        print("✅ SUCCESS: Viewer blocked from /users (403 Forbidden)")
    else:
        print(f"❌ FAILED: Viewer should get 403, got {response.status_code}")
        print(response.text)

def test_me(token, role_name):
    print(f"\n--- BONUS: Testing /users/me for {role_name} ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/users/me", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS: /me returned {data['email']} with role {data['role']}")
        if data['role'] != role_name:
             print(f"⚠️ WARNING: Role mismatch? Expected {role_name}, got {data['role']}")
    else:
        print(f"❌ FAILED: {response.status_code} {response.text}")

def main():
    # 1. Login Admin
    admin_token = login("admin@supervision.local", "SuperSecurePassword123")
    if not admin_token:
        sys.exit(1)
        
    # 2. Test Admin Access
    test_admin_access(admin_token)
    test_me(admin_token, "ADMIN")
    
    # 3. Create Viewer
    v_email, v_pass = create_viewer(admin_token)
    
    # 4. Login Viewer
    viewer_token = login(v_email, v_pass)
    if not viewer_token:
        print("Skipping viewer test (login failed)")
        sys.exit(1)
        
    # 5. Test Viewer Access
    test_viewer_access(viewer_token)
    test_me(viewer_token, "VIEWER")

if __name__ == "__main__":
    main()
