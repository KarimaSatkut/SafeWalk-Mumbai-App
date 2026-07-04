"""SafeWalk Mumbai — full backend API test suite."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://womens-safety-sos-3.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def unique_phone():
    # Unique phone per test-run so create_user doesn't collide.
    return f"+9199{uuid.uuid4().int % 10**8:08d}"


# ---------- Health ----------
class TestHealth:
    def test_root(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("service") == "safewalk-mumbai"
        assert data.get("status") == "ok"


# ---------- Auth (mock OTP) ----------
class TestAuth:
    def test_send_otp(self, api_client, unique_phone):
        r = api_client.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": unique_phone})
        assert r.status_code == 200
        data = r.json()
        assert data.get("sent") is True
        assert "123456" in data.get("hint", "")

    def test_verify_otp_success(self, api_client, unique_phone):
        r = api_client.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": unique_phone, "otp": "123456"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert "user_id" in data
        assert data.get("is_new") is True

    def test_verify_otp_wrong(self, api_client, unique_phone):
        r = api_client.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": unique_phone, "otp": "000000"})
        assert r.status_code == 401

    def test_verify_otp_bad_format(self, api_client, unique_phone):
        r = api_client.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": unique_phone, "otp": "12ab56"})
        assert r.status_code == 400


# ---------- Users ----------
class TestUsers:
    user_id = None
    phone = None

    def test_create_user(self, api_client, unique_phone):
        TestUsers.phone = unique_phone
        payload = {
            "phone": unique_phone,
            "name": "TEST_Aditi",
            "language": "en",
            "emergency_contacts": [
                {"name": "Amma", "phone": "+919111111111"},
                {"name": "Papa", "phone": "+919222222222"},
                {"name": "Rohan", "phone": "+919333333333"},
            ],
            "is_volunteer": False,
        }
        r = api_client.post(f"{BASE_URL}/api/users", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "TEST_Aditi"
        assert len(data["emergency_contacts"]) == 3
        assert "_id" not in data
        assert "id" in data
        TestUsers.user_id = data["id"]

    def test_get_user_persisted(self, api_client):
        assert TestUsers.user_id, "create must run first"
        r = api_client.get(f"{BASE_URL}/api/users/{TestUsers.user_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == TestUsers.user_id
        assert "_id" not in data
        assert len(data["emergency_contacts"]) == 3

    def test_patch_user_language_and_volunteer(self, api_client):
        r = api_client.patch(
            f"{BASE_URL}/api/users/{TestUsers.user_id}",
            json={"language": "hi", "is_volunteer": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "hi"
        assert data["is_volunteer"] is True

        # verify via GET
        r2 = api_client.get(f"{BASE_URL}/api/users/{TestUsers.user_id}")
        assert r2.json()["language"] == "hi"
        assert r2.json()["is_volunteer"] is True

    def test_get_user_not_found(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/users/{uuid.uuid4()}")
        assert r.status_code == 404


# ---------- SOS ----------
class TestSOS:
    incident_id = None
    volunteer_id = None

    def test_create_sos(self, api_client):
        assert TestUsers.user_id, "user must exist"
        r = api_client.post(
            f"{BASE_URL}/api/sos",
            json={"user_id": TestUsers.user_id, "lat": 18.9438, "lng": 72.8231},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "active"
        assert len(data["volunteers"]) == 4
        v = data["volunteers"][0]
        for key in ["id", "name", "phone", "avatar", "distance_m", "eta_min", "responding"]:
            assert key in v
        assert v["responding"] is False
        assert len(data["emergency_contacts_notified"]) == 3
        assert "_id" not in data
        TestSOS.incident_id = data["id"]
        TestSOS.volunteer_id = data["volunteers"][0]["id"]

    def test_sos_no_user(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/sos",
            json={"user_id": str(uuid.uuid4()), "lat": 18.9, "lng": 72.8},
        )
        assert r.status_code == 404

    def test_simulate_response(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/sos/{TestSOS.incident_id}/simulate-response")
        assert r.status_code == 200
        data = r.json()
        assert data.get("updated", 0) >= 1

        # Verify via GET
        g = api_client.get(f"{BASE_URL}/api/sos/{TestSOS.incident_id}")
        assert g.status_code == 200
        vols = g.json()["volunteers"]
        assert any(v["responding"] for v in vols)

    def test_respond_specific_volunteer(self, api_client):
        # Create fresh incident to isolate.
        r = api_client.post(
            f"{BASE_URL}/api/sos",
            json={"user_id": TestUsers.user_id, "lat": 18.9438, "lng": 72.8231},
        )
        assert r.status_code == 200
        inc = r.json()
        vol_id = inc["volunteers"][2]["id"]
        r2 = api_client.post(
            f"{BASE_URL}/api/sos/{inc['id']}/respond",
            json={"volunteer_id": vol_id},
        )
        assert r2.status_code == 200
        updated = r2.json()
        found = [v for v in updated["volunteers"] if v["id"] == vol_id]
        assert found and found[0]["responding"] is True

    def test_respond_bad_volunteer(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/sos/{TestSOS.incident_id}/respond",
            json={"volunteer_id": str(uuid.uuid4())},
        )
        assert r.status_code == 404

    def test_cancel_sos(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/sos/{TestSOS.incident_id}/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


# ---------- Ratings & pins ----------
class TestRatings:
    def test_post_rating_and_pin_aggregation(self, api_client):
        assert TestUsers.user_id
        payload = {
            "user_id": TestUsers.user_id,
            "lat": 18.9440,
            "lng": 72.8235,
            "stars": 4,
            "tags": ["well_lit", "police_nearby"],
            "note": "TEST",
        }
        r = api_client.post(f"{BASE_URL}/api/ratings", json=payload)
        assert r.status_code == 200
        assert r.json()["stars"] == 4

        # add second rating same bucket to test aggregation
        payload["stars"] = 5
        api_client.post(f"{BASE_URL}/api/ratings", json=payload)

        r2 = api_client.get(f"{BASE_URL}/api/community/pins")
        assert r2.status_code == 200
        pins = r2.json().get("pins", [])
        assert isinstance(pins, list) and len(pins) >= 1
        p = pins[0]
        for key in ["lat", "lng", "stars", "count", "tags"]:
            assert key in p


# ---------- Helplines ----------
class TestHelplines:
    def test_helplines(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/helplines")
        assert r.status_code == 200
        h = r.json().get("helplines", [])
        assert len(h) == 5
        numbers = {x["number"] for x in h}
        assert "1091" in numbers  # Nirbhaya
        assert "100" in numbers   # Mumbai Police
        assert "108" in numbers   # Ambulance
