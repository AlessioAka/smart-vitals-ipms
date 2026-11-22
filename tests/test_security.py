"""R5 access control, R7 data protection basics (Week 8: BOLA, OWASP API1)."""
import json
import sqlite3

from app.main import create_app
from src import config
from tests.helpers import PASSWORD, auth, make_client, normal_reading, post, small_model, token


def _own_and_other(c):
    mine = [p["patient_id"] for p in c.get("/patients", headers=auth(c, "C01")).get_json()]
    other = [p["patient_id"] for p in c.get("/patients", headers=auth(c, "C02")).get_json()]
    return mine, other


def test_clinician_sees_only_own_patients():
    c = make_client()
    mine, other = _own_and_other(c)
    assert mine and other and not set(mine) & set(other)


def test_cannot_read_another_clinicians_patient_403():
    c = make_client()
    mine, other = _own_and_other(c)
    for path in ("readings", "alerts", "thresholds"):
        assert c.get(f"/patients/{other[0]}/{path}", headers=auth(c, "C01")).status_code == 403


def test_cannot_change_another_clinicians_thresholds():
    c = make_client()
    _, other = _own_and_other(c)
    r = c.put(f"/patients/{other[0]}/thresholds", json={"heart_rate_high": 90}, headers=auth(c, "C01"))
    assert r.status_code == 403


def test_cannot_ask_for_someone_elses_alerts():
    c = make_client()
    assert c.get("/alerts?clinician=C02", headers=auth(c, "C01")).status_code == 403


def test_cannot_acknowledge_someone_elses_alert():
    c = make_client()
    other_patient = [p["patient_id"] for p in c.get("/patients", headers=auth(c, "C02")).get_json()][0]
    from tests.helpers import critical_reading
    alert_id = post(c, critical_reading(other_patient, 5)).get_json()["alert_id"]
    assert c.post(f"/alerts/{alert_id}/acknowledge", headers=auth(c, "C01")).status_code == 403


def test_no_token_is_401():
    c = make_client()
    assert c.get("/patients").status_code == 401
    assert c.get("/alerts").status_code == 401


def test_forged_token_is_401():
    c = make_client()
    assert c.get("/patients", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_wrong_password_and_unknown_id_look_the_same():
    c = make_client()
    a = c.post("/login", json={"clinician_id": "C01", "password": "wrong"})
    b = c.post("/login", json={"clinician_id": "NOBODY", "password": "wrong"})
    assert a.status_code == b.status_code == 401 and a.get_json() == b.get_json()


def test_wrong_device_key_cannot_post_readings():
    assert post(make_client(), normal_reading(), key="wrong").status_code == 401


def test_passwords_are_stored_hashed_not_plain():
    c = make_client()
    path = c.application.config["DB_PATH"]
    conn = sqlite3.connect(path)
    stored = conn.execute("SELECT password_hash FROM clinicians").fetchall()
    conn.close()
    assert stored and all(PASSWORD not in row[0] and row[0].startswith("pbkdf2:") for row in stored)


def test_no_real_patient_data_only_invented_ids():  # R7
    register = json.loads(config.PATIENTS_PATH.read_text())
    assert all(p["patient_id"].startswith("P") and "name" not in p for p in register)


def _login_page(c):
    html = c.get("/dashboard/login").get_data(as_text=True)
    import re
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


def test_dashboard_requires_login_and_hides_other_patients():
    c = make_client()
    assert c.get("/dashboard").status_code == 302
    csrf = _login_page(c)
    r = c.post("/dashboard/login", data={"csrf": csrf, "clinician_id": "C01", "password": PASSWORD})
    assert r.status_code == 302
    assert c.get("/dashboard").status_code == 200
    _, other = _own_and_other(c)
    assert c.get(f"/dashboard/patients/{other[0]}").status_code == 403
    assert c.get(f"/dashboard/patients/{other[0]}/chart.png").status_code == 403


def test_dashboard_form_without_csrf_token_is_refused():
    c = make_client()
    csrf = _login_page(c)
    c.post("/dashboard/login", data={"csrf": csrf, "clinician_id": "C01", "password": PASSWORD})
    r = c.post("/dashboard/patients/P001/thresholds", data={"heart_rate_high": "90"})
    assert r.status_code == 400


def test_dashboard_chart_renders_a_png():  # R8
    c = make_client()
    for m in range(5):
        post(c, normal_reading(minute=m))
    csrf = _login_page(c)
    c.post("/dashboard/login", data={"csrf": csrf, "clinician_id": "C01", "password": PASSWORD})
    r = c.get("/dashboard/patients/P001/chart.png")
    assert r.status_code == 200 and r.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_changing_the_demo_password_takes_effect_on_an_existing_database():
    c = make_client()
    settings = {k: c.application.config[k] for k in ("DB_PATH", "PATIENTS_PATH", "DEVICE_KEY", "SECRET_KEY")}
    c2 = create_app({**settings, "MODEL": small_model(), "DEMO_PASSWORD": "a-new-password"}).test_client()
    assert token(c2, password="a-new-password") is not None
    assert token(c2, password=PASSWORD) is None  # the old password stops working


def test_login_with_a_body_that_is_not_an_object_is_401_not_500():
    c = make_client()
    assert c.post("/login", json=["C01", PASSWORD]).status_code == 401


def _logged_in(c, clinician_id="C01"):
    csrf = _login_page(c)
    c.post("/dashboard/login", data={"csrf": csrf, "clinician_id": clinician_id, "password": PASSWORD})
    return csrf


def test_acknowledge_cannot_redirect_to_another_website():
    """An attacker-supplied "next" address is ignored (open-redirect protection)."""
    from tests.helpers import critical_reading
    c = make_client()
    alert_id = post(c, critical_reading("P001", 5)).get_json()["alert_id"]
    csrf = _logged_in(c)
    r = c.post(f"/dashboard/alerts/{alert_id}/acknowledge", data={"csrf": csrf, "next": "https://evil.example"})
    assert r.status_code == 302 and r.headers["Location"] == "/dashboard"


def test_dashboard_errors_are_pages_and_api_errors_stay_json():
    c = make_client()
    _logged_in(c)
    _, other = _own_and_other(c)
    page = c.get(f"/dashboard/patients/{other[0]}")
    assert page.status_code == 403 and "not assigned to you" in page.get_data(as_text=True)
    api = c.get("/no-such-route")
    assert api.status_code == 404 and api.is_json


def test_overview_lists_only_my_patients_most_urgent_first():
    from tests.helpers import critical_reading
    c = make_client()
    post(c, critical_reading("P005", 5, glucose=None))  # P005: C01's patient, no diabetes
    post(c, normal_reading("P001", 5))
    _logged_in(c)
    html = c.get("/dashboard").get_data(as_text=True)
    mine, other = _own_and_other(c)
    assert all(f">{p}<" in html for p in mine) and not any(f">{p}<" in html for p in other)
    assert html.index(">P005<") < html.index(">P001<")  # the Critical patient is listed first
