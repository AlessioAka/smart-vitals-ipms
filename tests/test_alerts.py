"""R4 alerts, R10 thresholds, alarm-fatigue control."""
import json

from tests.helpers import auth, critical_reading, make_client, normal_reading, post


def test_critical_reading_raises_alert_with_id_vitals_timestamp():  # R4
    c = make_client()
    r = post(c, critical_reading(minute=5)).get_json()
    assert r["status"] == "Critical" and r["alert"] is True
    alerts = c.get("/alerts", headers=auth(c, "C01")).get_json()
    a = alerts[0]
    assert a["patient_id"] == "P001" and a["clinician_id"] == "C01"
    assert a["ts"] == "2026-01-01T08:05:00" and json.loads(a["vitals"])["spo2"] == 88.0


def test_alert_goes_to_the_assigned_clinician_only():
    c = make_client()
    post(c, critical_reading("P001", 5))
    assert len(c.get("/alerts", headers=auth(c, "C01")).get_json()) == 1
    assert c.get("/alerts", headers=auth(c, "C02")).get_json() == []


def test_alert_explains_which_vitals_drove_it():
    c = make_client()
    r = post(c, critical_reading(minute=5)).get_json()
    assert any(s.startswith("spo2 = 88") for s in r["reasons"])


def test_normal_reading_raises_no_alert():
    c = make_client()
    post(c, normal_reading(minute=1))
    assert c.get("/alerts", headers=auth(c)).get_json() == []


def test_one_alert_per_episode_then_repeat_count():
    c = make_client()
    first = post(c, critical_reading(minute=5)).get_json()
    second = post(c, critical_reading(minute=6)).get_json()
    assert first["alert"] is True and second["alert"] is False and second["suppressed"] is True
    alerts = c.get("/alerts", headers=auth(c)).get_json()
    assert len(alerts) == 1 and alerts[0]["repeat_count"] == 2


def test_after_acknowledging_a_new_critical_alerts_again():
    c = make_client()
    a1 = post(c, critical_reading(minute=5)).get_json()["alert_id"]
    assert c.post(f"/alerts/{a1}/acknowledge", headers=auth(c)).status_code == 200
    assert post(c, critical_reading(minute=6)).get_json()["alert"] is True


def test_cooldown_ends_so_a_long_episode_alerts_again():
    c = make_client()
    post(c, critical_reading(minute=5))
    assert post(c, critical_reading(minute=20)).get_json()["alert"] is True  # 15 min later


def test_unacknowledged_alert_is_escalated_after_15_minutes():
    c = make_client()
    post(c, critical_reading(minute=5))
    post(c, normal_reading(minute=25))
    assert c.get("/alerts", headers=auth(c)).get_json()[0]["escalated"] is True


# ----- R10: thresholds
def test_clinician_can_set_and_read_thresholds():
    c = make_client()
    r = c.put("/patients/P001/thresholds", json={"heart_rate_high": 95}, headers=auth(c))
    assert r.status_code == 200 and r.get_json() == {"heart_rate_high": 95}
    assert c.get("/patients/P001/thresholds", headers=auth(c)).get_json() == {"heart_rate_high": 95}


def test_threshold_breach_raises_status_one_level():
    c = make_client()
    base = post(c, normal_reading(minute=1, heart_rate=100)).get_json()["status"]
    c.put("/patients/P001/thresholds", json={"heart_rate_high": 90}, headers=auth(c))
    raised = post(c, normal_reading(minute=2, heart_rate=100)).get_json()
    assert base == "Normal" and raised["status"] == "Warning"
    assert any("breaks this patient's high limit" in s for s in raised["reasons"])


def test_threshold_cannot_lower_a_status():
    c = make_client()
    c.put("/patients/P001/thresholds", json={"heart_rate_high": 200}, headers=auth(c))
    assert post(c, critical_reading(minute=5)).get_json()["status"] == "Critical"


def test_bad_threshold_is_422():
    c = make_client()
    assert c.put("/patients/P001/thresholds", json={"heart_rate_high": 9999}, headers=auth(c)).status_code == 422
    assert c.put("/patients/P001/thresholds", json={"banana": 1}, headers=auth(c)).status_code == 422


def test_blank_threshold_clears_it():
    c = make_client()
    c.put("/patients/P001/thresholds", json={"heart_rate_high": 95}, headers=auth(c))
    r = c.put("/patients/P001/thresholds", json={"heart_rate_high": None}, headers=auth(c))
    assert r.get_json() == {}


def test_alert_still_escalates_when_the_patient_goes_silent():
    """P001 turns Critical, then its sensor drops out. Time moves on (P002 keeps reporting)."""
    c = make_client()
    post(c, critical_reading("P001", 5))
    assert c.get("/alerts", headers=auth(c)).get_json()[0]["escalated"] is False
    post(c, normal_reading("P002", 25, glucose=None))
    assert c.get("/alerts", headers=auth(c)).get_json()[0]["escalated"] is True
