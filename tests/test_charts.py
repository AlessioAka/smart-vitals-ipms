"""T18 · Trend chart honesty (R8): the time window is real time, and missing readings show as gaps."""
import math
from datetime import datetime, timedelta

from dashboard.charts import with_gaps
from dashboard.views import in_window
from tests.helpers import PASSWORD, make_client, normal_reading, post

T0 = datetime(2026, 1, 1, 8, 0)


def test_a_silence_breaks_the_line_instead_of_bridging_it():
    times = [T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=30), T0 + timedelta(minutes=31)]
    xs, ys = with_gaps(times, [70, 71, 90, 91])
    assert len(xs) == 5 and math.isnan(ys[2])           # one break inserted in the 29-minute silence
    assert [y for y in ys if not math.isnan(y)] == [70, 71, 90, 91]


def test_a_missing_vital_is_a_gap_too():
    _, ys = with_gaps([T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=2)], [70, None, 72])
    assert math.isnan(ys[1]) and len(ys) == 3


def test_window_means_time_not_number_of_readings():
    rows = [{"ts": (T0 + timedelta(minutes=m)).isoformat()} for m in (0, 1, 2, 600, 601)]
    kept = in_window(rows, 60)                           # the computer was off for ~10 hours
    assert [r["ts"][-8:-3] for r in kept] == ["18:00", "18:01"] and in_window([], 60) == []


def test_chart_with_a_long_gap_still_renders():
    import re
    c = make_client()
    for m in (0, 1, 2, 300, 301):
        post(c, normal_reading(minute=m))
    html = c.get("/dashboard/login").get_data(as_text=True)
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)
    c.post("/dashboard/login", data={"csrf": csrf, "clinician_id": "C01", "password": PASSWORD})
    for window in (60, 180, 360):
        r = c.get(f"/dashboard/patients/P001/chart.png?window={window}")
        assert r.status_code == 200 and r.data[:4] == b"\x89PNG"
