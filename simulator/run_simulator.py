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
    LIVE        off|on   on: never stop; stream readings stamped with the real clock (run_live)
Week 7: retry with exponential backoff and jitter on connection failures and
5xx; never retry a 4xx (the request itself is wrong).
"""
import heapq
import itertools
import json
import os
import random
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

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
        buffer.add(reading)
        _drain(buffer, counts)
    if len(buffer):
        print(f"{len(buffer)} readings were never delivered (still in the edge buffer).")
    print("Edge: impossible values blanked before sending:", blanked_total, "| local early warnings:", warnings)
    print("Results from the API:")
    for k, v in sorted(counts.items()):
        print(f"  {k:28s} {v}")
    return counts


def _drain(buffer: edge.EdgeBuffer, counts: Counter) -> None:
    """Edge buffer: every reading joins the queue; the queue is sent oldest first. If the API cannot
    be reached even after retries, the reading stays queued and is tried again with the next one."""
    while len(buffer):
        item = buffer.pop_oldest()
        code, body = send_with_backoff(item)
        if code is None:           # network still down: put it back and move on
            buffer.queue.appendleft(item)
            counts["buffered"] += 1
            if counts["buffered"] == 1:
                print(f"Cannot reach the API at {API_URL}. Is it running?  (python -m app.main)  "
                      "Readings wait in the edge buffer and are retried.", flush=True)
            return
        counts[f"{code} {body.get('outcome', '')}".strip()] += 1
        if body.get("alert"):
            counts["new alerts"] += 1
        if code == 401 and counts["401 unauthorised"] == 1:
            print("The API refused the device key (401). The API and the simulator must use the "
                  "same DEVICE_KEY: check .env, then restart both.", flush=True)


STALE_MINUTES = 5  # live mode: a message this overdue (the computer was asleep) is dropped


def run_live(chunk_minutes: int = 60, faults=None, use_edge=None, clock=None) -> None:
    """LIVE=on: a feed that never ends, in real time, for the always-on service (deploy/).

    run() replays one fixed 150-minute session as fast as it can and stops. This instead
    simulates one hour at a time starting from the real clock (UTC), sends every message at
    the moment it would really arrive, and starts the next hour when this one runs out.
    The same faults, edge checks, buffer and retries are used, so the dashboard shows
    exactly what the R9 tests cover - just live.
    `clock` (the time now, UTC) is only replaced by the tests.
    """
    clock = clock or (lambda: datetime.now(timezone.utc))
    faults = faults if faults is not None else os.environ.get("FAULTS", "on") == "on"
    use_edge = use_edge if use_edge is not None else os.environ.get("EDGE", "on") == "on"
    patients = json.loads(config.PATIENTS_PATH.read_text())
    buffer, counts = edge.EdgeBuffer(), Counter()
    queue, order = [], itertools.count()  # heap of (arrival time, tie-breaker, reading)
    hour_end = None
    print(f"Live feed: {len(patients)} patients, one reading a minute each -> {API_URL}", flush=True)
    while True:
        now = clock()
        if hour_end is None or now >= hour_end:
            # Continue straight on from the last hour. On a (re)start, or after a long sleep, begin at the
            # NEXT whole minute: the previous run may already have sent this minute's readings.
            start = hour_end if hour_end and now - hour_end < timedelta(minutes=STALE_MINUTES) \
                else now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            events, _ = simulate(patients, minutes=chunk_minutes, seed=int(start.timestamp() // 60) % 2**31,
                                 faults=faults, start=start.replace(tzinfo=None).isoformat(),
                                 id_tag=start.strftime("%Y%m%d%H%M-"))
            # Late messages of this hour may arrive during the next one: the heap keeps them in order.
            for ev in events:
                heapq.heappush(queue, (start + timedelta(minutes=ev["send_at"]), next(order), ev["reading"]))
            hour_end = start + timedelta(minutes=chunk_minutes)
            if counts:
                print(f"{now:%Y-%m-%d %H:%M} UTC  so far: " +
                      ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), flush=True)

        while queue and queue[0][0] <= now:
            due, _, reading = heapq.heappop(queue)
            if now - due > timedelta(minutes=STALE_MINUTES):
                counts["dropped (computer was asleep)"] += 1
                continue
            if use_edge:
                reading, _ = edge.range_check(reading)
            buffer.add(reading)
            _drain(buffer, counts)
        if len(buffer):
            _drain(buffer, counts)  # the API was down: keep trying what is waiting

        next_due = min(queue[0][0] if queue else hour_end, hour_end)
        time.sleep(max(0.5, min(30.0, (next_due - clock()).total_seconds())))


if __name__ == "__main__":
    run_live() if os.environ.get("LIVE") == "on" else run()
