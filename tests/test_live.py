"""T17 · Live mode of the simulator (used by the always-on service in deploy/)."""
from datetime import datetime, timezone

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


def test_run_live_sends_readings_stamped_with_the_current_minute(monkeypatch):
    sent = []
    monkeypatch.setattr(run_simulator, "send_with_backoff", lambda r: (sent.append(r), (201, {}))[1])
    monkeypatch.setattr(run_simulator.time, "sleep", lambda s: (_ for _ in ()).throw(_Stop()))
    with pytest.raises(_Stop):  # stop the endless loop after its first pass
        run_simulator.run_live(faults=False)
    assert len(sent) == 20  # one reading for each of the 20 patients, right now
    stamps = {r["timestamp"] for r in sent}
    age = datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(stamps.pop())
    assert not stamps and 0 <= age.total_seconds() < 120  # all stamped with the current minute (UTC)
