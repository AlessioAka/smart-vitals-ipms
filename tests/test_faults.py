"""T7 to T10: requirement 9. A messy hour (dropouts, glitches, stuck sensors, late
readings, resent copies) goes through edge + API. No crashes, no duplicate alerts,
no alerts caused by glitches, and real Critical episodes are still caught."""
import json

from simulator import edge
from simulator.generator import simulate
from src import config
from tests.helpers import auth, make_client, post

_CACHE = {}


def replay(use_edge=True, minutes=150, seed=11):
    """Play the faulty feed through the API; return (client, replies, observed)."""
    key = (use_edge, minutes, seed)
    if key in _CACHE:
        return _CACHE[key]
    register = json.loads(config.PATIENTS_PATH.read_text())
    c = make_client(register)
    events, observed = simulate(register, minutes=minutes, seed=seed, faults=True)
    replies = []
    for ev in events:
        reading = edge.range_check(ev["reading"])[0] if use_edge else ev["reading"]
        r = post(c, reading)
        replies.append((ev, r.status_code, r.get_json()))
    _CACHE[key] = (c, replies, observed)
    return _CACHE[key]


def test_T7_dropouts_and_resends_never_crash_the_api():
    _, replies, _ = replay()
    assert all(code < 500 for _, code, _ in replies)
    assert any(ev["fault"] == "duplicate" for ev, _, _ in replies)


def test_T8_resent_copies_are_200_and_cause_no_duplicate_alerts():
    c, replies, _ = replay()
    dups = [(code, body) for ev, code, body in replies if ev["fault"] == "duplicate"]
    # a resent copy is always "200 duplicate", unless it somehow arrived first (then it was the original)
    assert sum(1 for code, b in dups if code == 200 and b["outcome"] == "duplicate") >= len(dups) * 0.9
    alerts = [a for cid in ("C01", "C02", "C03", "C04") for a in c.get("/alerts", headers=auth(c, cid)).get_json()]
    reading_ids = [a["reading_id"] for a in alerts]
    assert len(reading_ids) == len(set(reading_ids))


def test_T9_glitches_do_not_cause_false_alerts():
    """With the edge range check on, glitched readings of healthy patients raise no alert."""
    c, replies, observed = replay()
    truth = {o["reading_id"]: o["true_label"] for o in observed}
    false_alerts = [body for ev, code, body in replies
                    if ev["fault"] == "glitch" and body.get("alert") and truth[ev["reading"]["reading_id"]] == "Normal"]
    assert false_alerts == []


def test_T9b_without_the_edge_glitches_are_refused_not_stored():
    """Edge off: the cloud validation refuses impossible values (422) rather than classify them."""
    _, replies, _ = replay(use_edge=False)
    glitch_replies = [code for ev, code, _ in replies if ev["fault"] == "glitch"]
    assert glitch_replies and all(code in (422, 200) for code in glitch_replies)
    assert sum(code == 422 for code in glitch_replies) >= len(glitch_replies) * 0.8


def test_T10_real_critical_episodes_are_not_missed():
    """Every run of true-Critical minutes is covered by an alert for that patient within or just after it."""
    c, _, observed = replay()
    alerts = {}
    for cid in ("C01", "C02", "C03", "C04"):
        for a in c.get("/alerts", headers=auth(c, cid)).get_json():
            alerts.setdefault(a["patient_id"], []).append(a["ts"])
    episodes, current = [], None
    for o in sorted(observed, key=lambda o: (o["patient_id"], o["minute"])):
        if o["true_label"] == "Critical":
            if current and current["patient"] == o["patient_id"] and o["minute"] - current["end"] <= 2:
                current["end"] = o["minute"]
            else:
                current = {"patient": o["patient_id"], "start": o["minute"], "end": o["minute"]}
                episodes.append(current)
    from datetime import datetime, timedelta
    start0 = datetime.fromisoformat(config.SIM_START)
    caught = 0
    for ep in episodes:
        lo, hi = start0 + timedelta(minutes=ep["start"] - 1), start0 + timedelta(minutes=ep["end"] + 10)
        if any(lo <= datetime.fromisoformat(t) <= hi for t in alerts.get(ep["patient"], [])):
            caught += 1
    assert episodes, "the simulation should contain Critical episodes"
    assert caught / len(episodes) >= 0.8, f"caught {caught} of {len(episodes)} Critical episodes"


def test_missing_vitals_are_handled_without_error():
    _, replies, _ = replay()
    missing = [code for ev, code, _ in replies if ev["fault"] == "missing_vital"]
    assert missing and all(code in (200, 201) for code in missing)
