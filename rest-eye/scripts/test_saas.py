import sys
from pathlib import Path
import httpx
import json

base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_saas_api():
    print("==================================================")
    print(" [TEST] REST-EYE Multi-Tenant Cloud SaaS API")
    print("==================================================")
    
    from fastapi.testclient import TestClient
    from web.api import app
    
    client = TestClient(app)
    
    # 1. Test Tenant Registration
    test_email = f"owner_{int(sys.platform == 'win')}@testfranchise.com"
    reg_payload = {
        "restaurant_name": "سلسلة برجر إكسبريس (Burger Express)",
        "email": test_email,
        "password": "Password123!",
        "full_name": "مالك السلسلة"
    }
    res = client.post("/api/v2/auth/register", json=reg_payload)
    print(f"1. Register Tenant: status={res.status_code}")
    
    # 2. Test Login
    login_res = client.post("/api/v2/auth/login", json={"email": test_email, "password": "Password123!"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    token = token_data["access_token"]
    print(f"2. Login JWT Token: {token[:25]}... (Org: {token_data['organization']['name']})")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Test Profile (/api/v2/auth/me)
    me_res = client.get("/api/v2/auth/me", headers=headers)
    assert me_res.status_code == 200
    print(f"3. Profile Me: {me_res.json()['user']['email']} | Plan: {me_res.json()['organization']['plan']}")
    
    # 4. Test List Branches
    branches_res = client.get("/api/v2/branches", headers=headers)
    assert branches_res.status_code == 200
    branches = branches_res.json()["branches"]
    print(f"4. Branches Count: {len(branches)} (First: {branches[0]['name'] if branches else 'None'})")
    
    # 5. Test Add New Branch
    new_b_res = client.post("/api/v2/branches", json={"name": "فرع الإسكندرية (Alexandria)", "city": "الإسكندرية"}, headers=headers)
    assert new_b_res.status_code == 200
    new_b_id = new_b_res.json()["branch"]["id"]
    print(f"5. Add Branch: ID={new_b_id} ({new_b_res.json()['branch']['name']})")
    
    # 6. Test Add Camera to Branch
    new_cam_res = client.post("/api/v2/cameras", json={
        "branch_id": new_b_id,
        "name": "كاميرا خط الشواية (Grill Station 01)",
        "stream_source": "sample",
        "camera_type": "KITCHEN"
    }, headers=headers)
    assert new_cam_res.status_code == 200
    print(f"6. Add Camera: ID={new_cam_res.json()['camera']['id']}")
    
    # 7. Test Incidents Feed
    inc_res = client.get("/api/v2/incidents", headers=headers)
    assert inc_res.status_code == 200
    print(f"7. Incidents List: status={inc_res.status_code} total={inc_res.json()['total']}")
    
    # 8. Test Settings Endpoint
    settings_res = client.get("/api/v2/settings", headers=headers)
    assert settings_res.status_code == 200
    print(f"8. Settings: {settings_res.json()['settings']}")

    print("==================================================")
    print(" [PASSED] All Multi-Tenant SaaS APIs Tested 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_saas_api()
