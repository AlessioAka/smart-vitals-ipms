"""The simulator client: plays an IoT feed into the API.

    python -m simulator.run_simulator

Settings (environment variables, so the same code runs in Docker):
    API_URL     http://localhost:8000
    DEVICE_KEY  dev-device-key
    MINUTES     150      simulated minutes per patient
    FAULTS      on|off   dropouts, glitches, late readings, resent copies
    EDGE        on|off   on: the phone blanks impossible values before sending
    SPEED       0        0 = as fast as possible; 60 = real time
    SEED        11
Week 7: retry with exponential backoff and jitter on connection failures and
5xx; never retry a 4xx (the request itself is wrong).
"""
import json
import os
import random
import time
import urllib.error
import urllib.request
from collections import Counter

from simulator import edge
from simulator.generator import simulate
from src import config  # importing it also reads .env, so API_URL / DEVICE_KEY below match the API

API_URL = os.environ.get("API_URL", "http://localhost:8000")
DEVICE_KEY = os.environ.get("DEVICE_KEY", "dev-device-key")


def post_reading(reading: dict, api_url: str = API_URL, key: str = DEVICE_KEY) -> tuple:
    """One POST. Returns (status_code, body). Raises ConnectionError if the server cannot be reached."""
    req = urllib.request.Request(
        f"{api_url}/readings", data=json.dumps(reading).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Device-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, _json_body(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, _json_body(err.read())
    except (urllib.error.URLError, TimeoutError) as err:
        raise ConnectionError(str(err)) from err


def _json_body(raw: bytes) -> dict:
    """The reply as a dict. An error page that is not JSON (e.g. an HTML 500) must not crash the simulator."""
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return {"outcome": "not JSON"}
    return body if isinstance(body, dict) else {"outcome": "not JSON"}


def send_with_backoff(reading: dict, post=post_reading, tries: int = 6, base: float = 0.5,
                      sleep=time.sleep) -> tuple:
    """Retry connection failures and 5xx with backoff + jitter; return at once on any 4xx."""
    for attempt in range(tries):
        try:
            code, body = post(reading)
            if code < 500:
                return code, body
        except ConnectionError:
            pass
        # Exponential backoff with jitter: wait 0.5 s, 1 s, 2 s, 4 s ... times a random 0.5-1.0, so
        # thousands of devices coming back after an outage do not all hit the API at the same moment.
        sleep(base * (2 ** attempt) * random.uniform(0.5, 1.0))
    return None, {"outcome": "gave up"}  # the edge buffer keeps the reading


def run(minutes=None, faults=None, use_edge=None) -> Counter:
    minutes = minutes or int(os.environ.get("MINUTES", 150))
    faults = faults if faults is not None else os.environ.get("FAULTS", "on") == "on"
    use_edge = use_edge if use_edge is not None else os.environ.get("EDGE", "on") == "on"
    speed = float(os.environ.get("SPEED", 0))

    patients = json.loads(config.PATIENTS_PATH.read_text())
    events, _ = simulate(patients, minutes=minutes, seed=int(os.environ.get("SEED", 11)), faults=faults)
    print(f"Simulating {len(patients)} patients x {minutes} min -> {len(events)} messages "
          f"(faults={'on' if faults else 'off'}, edge={'on' if use_edge else 'off'})")

    buffer, counts, blanked_total, warnings = edge.EdgeBuffer(), Counter(), 0, 0
    clock = events[0]["send_at"] if events else 0
    for ev in events:
        if speed and ev["send_at"] > clock:
            time.sleep((ev["send_at"] - clock) * 60 / speed)
        clock = ev["send_at"]
        reading = ev["reading"]
        if use_edge:
            reading, blanked = edge.range_check(reading)
            blanked_total += len(blanked)
            if edge.early_warning(reading):
                warnings += 1
        # Edge buffer: every reading joins the queue; the queue is sent oldest first. If the API cannot
        # be reached even after retries, the reading stays queued and is tried again with the next one.
        buffer.add(reading)
        while len(buffer):
            item = buffer.pop_oldest()
            code, body = send_with_backoff(item)
            if code is None:           # network still down: put it back and move on
                buffer.queue.appendleft(item)
                counts["buffered"] += 1
                if counts["buffered"] == 1:
                    print(f"Cannot reach the API at {API_URL}. Is it running?  (python -m app.main)  "
                          "Readings wait in the edge buffer and are retried.")
                break
            counts[f"{code} {body.get('outcome', '')}".strip()] += 1
            if body.get("alert"):
                counts["new alerts"] += 1
            if code == 401 and counts["401 unauthorised"] == 1:
                print("The API refused the device key (401). The API and the simulator must use the "
                      "same DEVICE_KEY: check .env, then restart both.")
    if len(buffer):
        print(f"{len(buffer)} readings were never delivered (still in the edge buffer).")
    print("Edge: impossible values blanked before sending:", blanked_total, "| local early warnings:", warnings)
    print("Results from the API:")
    for k, v in sorted(counts.items()):
        print(f"  {k:28s} {v}")
    return counts


if __name__ == "__main__":
    run()
