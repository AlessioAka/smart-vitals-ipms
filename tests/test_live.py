"""T17 · Live mode of the simulator (used by the always-on service in deploy/)."""
from datetime import datetime, timedelta, timezone

import pytest

from simulator import run_simulator
from simulator.generator import make_patients, simulate


def test_default_ids_and_times_are_unchanged():
    events, _ = simulate(make_patients(2), minutes=3, faults=False)
    first = events[0]["reading"]
    assert first["reading_id"] == "P001-0000" and first["timestamp"] == "2026-01-01T08:00:00"


def test_live_hour_starts_at_the_given_time_with_unique_ids():
    events, _ = simulate(make_patients(2), minutes=3, faults=False,
                         start="2026-11-22T10:00:00", id_tag="202611221000-")
    first = events[0]["reading"]
    assert first["timestamp"] == "2026-11-22T10:00:00" and first["reading_id"] == "P001-202611221000-0000"


class _Stop(Exception):
    pass


def test_run_live_starts_at_the_next_minute_and_stamps_readings_with_it(monkeypatch):
    """A (re)started feed waits for the next whole minute, so it never repeats a minute
    that a previous run may already have sent; then each patient gets one reading."""
    sent, now, sleeps = [], [datetime(2026, 11, 22, 10, 0, 30, tzinfo=timezone.utc)], []

    def fake_sleep(seconds):  # advance the fake clock instead of waiting; stop on the second pass
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise _Stop()
        now[0] += timedelta(seconds=seconds)

    monkeypatch.setattr(run_simulator, "send_with_backoff", lambda r: (sent.append(r), (201, {}))[1])
    monkeypatch.setattr(run_simulator.time, "sleep", fake_sleep)
    with pytest.raises(_Stop):
        run_simulator.run_live(faults=False, clock=lambda: now[0])
    assert sleeps[0] == 30                                 # 10:00:30 -> wait for 10:01:00
    assert len(sent) == 20                                 # one reading for each of the 20 patients
    assert {r["timestamp"] for r in sent} == {"2026-11-22T10:01:00"}
