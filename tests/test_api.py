"""Week 8 contract: the same replies as the lecture examples (R2, R6, R9)."""
from tests.helpers import auth, critical_reading, make_client, normal_reading, post


def test_health_ok_when_model_loaded():
    c = make_client()
    assert c.get("/health").status_code == 200


def test_normal_reading_is_created():
    r = post(make_client(), normal_reading())
    assert r.status_code == 201 and r.get_json()["status"] == "Normal" and r.get_json()["alert"] is False


def test_same_reading_again_is_200_duplicate_not_201():
    c = make_client()
    post(c, normal_reading())
    r = post(c, normal_reading())
    assert r.status_code == 200 and r.get_json()["outcome"] == "duplicate"


def test_impossible_heart_rate_is_422_with_reason():
    r = post(make_client(), normal_reading(heart_rate=250))
    assert r.status_code == 422
    assert r.get_json()["problems"] == ["heart_rate = 250 is outside 30 to 220"]


def test_missing_spo2_is_still_201():
    assert post(make_client(), normal_reading(spo2=None)).status_code == 201


def test_unknown_patient_is_404():
    assert post(make_client(), normal_reading("P999")).status_code == 404


def test_not_json_is_422_not_500():
    c = make_client()
    r = c.post("/readings", data="hello", headers={"X-Device-Key": "test-device-key"})
    assert r.status_code == 422


def test_duplicate_is_stored_once_history_r6():
    c = make_client()
    for _ in range(3):
        post(c, normal_reading())
    post(c, normal_reading(minute=1))
    hist = c.get("/patients/P001/readings", headers=auth(c)).get_json()
    assert [h["reading_id"] for h in hist] == ["P001-0000", "P001-0001"]


def test_late_reading_is_stored_in_time_order_and_marked_late():
    c = make_client()
    for m in (30, 31, 32):
        post(c, normal_reading(minute=m))
    r = post(c, normal_reading(minute=2))  # measured 30 minutes before the newest one
    assert r.status_code == 201 and r.get_json()["late"] is True
    hist = c.get("/patients/P001/readings", headers=auth(c)).get_json()
    assert [h["ts"][14:16] for h in hist] == ["02", "30", "31", "32"]


def test_late_critical_is_stored_but_does_not_page_the_clinician():
    c = make_client()
    for m in (30, 31):
        post(c, normal_reading(minute=m))
    r = post(c, critical_reading(minute=3)).get_json()
    assert r["status"] == "Critical" and r["alert"] is False and r["late"] is True


def test_history_is_kept_between_requests_stateless():
    """Two app copies sharing one database see the same history (Week 7)."""
    c = make_client()
    post(c, normal_reading(minute=0))
    assert len(c.get("/patients/P001/readings", headers=auth(c)).get_json()) == 1


def test_timestamp_with_a_time_zone_is_stored_in_the_standard_form():
    """08:10 at +01:00 is 07:10 UTC. It used to crash the next comparison with a 500."""
    c = make_client()
    post(c, normal_reading(minute=5))
    r = post(c, normal_reading(reading_id="tz", timestamp="2026-01-01T09:10:00+01:00"))
    assert r.status_code == 201
    assert post(c, normal_reading(reading_id="z", timestamp="2026-01-01T08:11:00Z")).status_code == 201
    assert post(c, normal_reading(reading_id="space", timestamp="2026-01-01 08:12:00")).status_code == 201
    hist = c.get("/patients/P001/readings", headers=auth(c)).get_json()
    assert [h["ts"] for h in hist] == ["2026-01-01T08:05:00", "2026-01-01T08:10:00",
                                       "2026-01-01T08:11:00", "2026-01-01T08:12:00"]


def test_timestamp_that_is_not_a_date_and_time_is_422_not_500():
    c = make_client()
    for bad in ("2026-01-01", 20260101, None, "yesterday", ""):
        assert post(c, normal_reading(timestamp=bad)).status_code == 422, bad


def test_history_limit_cannot_be_switched_off_with_a_negative_number():
    c = make_client()
    for m in range(3):
        post(c, normal_reading(minute=m))
    assert len(c.get("/patients/P001/readings?limit=-1", headers=auth(c)).get_json()) == 1
    assert len(c.get("/patients/P001/readings?limit=2", headers=auth(c)).get_json()) == 2
