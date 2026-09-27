import requests
import uuid

BASE_URL = "http://127.0.0.1:8000"

def test_flow():
    # 1. Test public hospitals
    res = requests.get(f"{BASE_URL}/hospitals/public?limit=5")
    print(f"GET /hospitals/public status: {res.status_code}")
    assert res.status_code == 200, res.text
    hospitals = res.json()["hospitals"]
    print(f"Public hospitals count: {len(hospitals)}, first: {hospitals[0]}")

    # 2. Test staff register with explicit hospital
    test_email = f"staff_{uuid.uuid4().hex[:6]}@test.com"
    chosen_hosp = hospitals[0]["hospital_id"]
    reg_res = requests.post(f"{BASE_URL}/auth/register", json={
        "email": test_email,
        "name": "Dr. Test Staff",
        "password": "Password123!",
        "role": "hospital_staff",
        "hospital_ids": [chosen_hosp]
    })
    print(f"Register staff status: {reg_res.status_code}")
    assert reg_res.status_code == 201, reg_res.text
    staff_token = reg_res.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # 3. Test staff /hospitals endpoint
    hosp_res = requests.get(f"{BASE_URL}/hospitals", headers=staff_headers)
    print(f"Staff /hospitals: {hosp_res.status_code}, data: {hosp_res.json()}")
    assert hosp_res.status_code == 200
    assert chosen_hosp in hosp_res.json()["hospitals"]

    # 4. Test staff access to unauthorized hospital
    unauth_hosp = hospitals[1]["hospital_id"]
    bad_res = requests.get(f"{BASE_URL}/forecast/latest?hospitals={unauth_hosp}", headers=staff_headers)
    print(f"Staff accessing unauthorized hospital status: {bad_res.status_code}")
    assert bad_res.status_code == 403

    # 5. Test staff accessing authorized hospital
    ok_res = requests.get(f"{BASE_URL}/forecast/latest?hospitals={chosen_hosp}", headers=staff_headers)
    print(f"Staff accessing authorized hospital status: {ok_res.status_code}")
    assert ok_res.status_code == 200

    # 6. Test Admin login
    admin_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test_admin_v2@healthflow.ai",
        "password": "AdminPass123!"
    })
    print(f"Admin login status: {admin_res.status_code}")
    assert admin_res.status_code == 200
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 7. Test Admin /hospitals (should return all)
    admin_hosp = requests.get(f"{BASE_URL}/hospitals", headers=admin_headers)
    print(f"Admin /hospitals count: {admin_hosp.json()['count']}")
    assert admin_hosp.json()["count"] > 100

    # 8. Test Admin creating new hospital
    new_hosp_id = f"TEST_{uuid.uuid4().hex[:5].upper()}"
    create_res = requests.post(f"{BASE_URL}/admin/hospitals", headers=admin_headers, json={
        "hospital_id": new_hosp_id,
        "name": "Mount Sinai Innovation Clinic",
        "region": "NY",
        "capacity": 320,
        "icu_capacity": 45
    })
    print(f"Admin create hospital status: {create_res.status_code}, res: {create_res.json()}")
    assert create_res.status_code == 201

    # 9. Verify staff cannot create hospital
    staff_create_res = requests.post(f"{BASE_URL}/admin/hospitals", headers=staff_headers, json={
        "hospital_id": "ILLEGAL_1"
    })
    print(f"Staff create hospital status: {staff_create_res.status_code} (expected 403)")
    assert staff_create_res.status_code == 403

    print("\nALL BACKEND RBAC & HOSPITAL MANAGEMENT TESTS PASSED!")

if __name__ == "__main__":
    test_flow()
