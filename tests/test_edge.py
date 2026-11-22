"""Edge node and the simulator's retry rules (Week 7, R11)."""
from simulator import edge
from simulator.run_simulator import _json_body, send_with_backoff


def test_edge_blanks_impossible_values_only():
    clean, blanked = edge.range_check({"heart_rate": 250, "spo2": 97})
    assert clean["heart_rate"] is None and clean["spo2"] == 97 and blanked == ["heart_rate"]


def test_edge_early_warning_works_without_network():
    assert edge.early_warning({"spo2": 85}) and not edge.early_warning({"spo2": 97, "heart_rate": 70})


def test_buffer_is_bounded_and_drops_oldest():
    b = edge.EdgeBuffer(max_items=3)
    for i in range(5):
        b.add({"i": i})
    assert len(b) == 3 and b.pop_oldest() == {"i": 2}


def test_backoff_retries_connection_failures_then_succeeds():
    calls = []
    def flaky(reading):
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("down")
        return 201, {"outcome": "created"}
    assert send_with_backoff({}, post=flaky, sleep=lambda s: None) == (201, {"outcome": "created"})
    assert len(calls) == 3


def test_backoff_never_retries_a_422():
    calls = []
    def bad(reading):
        calls.append(1)
        return 422, {"outcome": "invalid"}
    assert send_with_backoff({}, post=bad, sleep=lambda s: None)[0] == 422
    assert len(calls) == 1


def test_backoff_gives_up_after_the_limit():
    def down(reading):
        raise ConnectionError("down")
    code, _ = send_with_backoff({}, post=down, tries=3, sleep=lambda s: None)
    assert code is None


def test_an_error_page_that_is_not_json_does_not_crash_the_simulator():
    assert _json_body(b"<html>Internal Server Error</html>") == {"outcome": "not JSON"}
    assert _json_body(b"") == {} and _json_body(b'{"outcome": "created"}') == {"outcome": "created"}
