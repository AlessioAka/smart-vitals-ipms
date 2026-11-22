"""Week 8: the API contract's two rule functions."""
from app import validation as V
from tests.helpers import normal_reading


def test_valid_reading_has_no_problems():
    assert V.problems_in(normal_reading()) == []


def test_impossible_heart_rate_is_named():
    assert V.problems_in(normal_reading(heart_rate=250)) == ["heart_rate = 250 is outside 30 to 220"]


def test_missing_spo2_is_allowed():
    assert V.problems_in(normal_reading(spo2=None)) == []


def test_missing_ids_and_bad_timestamp_are_all_reported():
    problems = V.problems_in({"heart_rate": 70, "timestamp": "yesterday"})
    assert len(problems) == 3


def test_text_and_booleans_are_not_numbers():
    assert V.problems_in(normal_reading(heart_rate="fast"))
    assert V.problems_in(normal_reading(heart_rate=True))


def test_a_reading_with_no_vitals_is_refused():
    body = {"reading_id": "x", "patient_id": "P001", "timestamp": "2026-01-01T08:00:00"}
    assert V.problems_in(body) == ["at least one vital sign is required"]


def test_body_must_be_an_object():
    assert V.problems_in([1, 2, 3]) == ["body must be a JSON object"]


def test_status_codes():
    assert [V.status_code(o) for o in ("created", "duplicate", "invalid", "unknown patient")] == [201, 200, 422, 404]


def test_timestamps_are_put_into_one_standard_form():
    assert V.clean_timestamp("2026-01-01T08:00:00") == "2026-01-01T08:00:00"
    assert V.clean_timestamp("2026-01-01 08:00") == "2026-01-01T08:00:00"
    assert V.clean_timestamp("2026-01-01T09:00:00+01:00") == "2026-01-01T08:00:00"
    assert V.clean_timestamp("2026-01-01") is None and V.clean_timestamp(1767254400) is None
