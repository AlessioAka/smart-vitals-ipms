"""Validation and status codes (Week 8: the API is a contract).

These two small functions are the heart of requirement 9 at the API door:
`problems_in` says what is wrong with a request; `status_code` turns the
outcome into an honest HTTP code.
"""
from datetime import datetime, timezone

from src import config

# Allowed range for a clinician-set threshold (R10): wider than normal, inside what is physical.
THRESHOLD_FIELDS = {
    "heart_rate_low": "heart_rate", "heart_rate_high": "heart_rate",
    "spo2_low": "spo2",
    "systolic_low": "systolic", "systolic_high": "systolic",
    "temperature_low": "temperature", "temperature_high": "temperature",
    "glucose_low": "glucose", "glucose_high": "glucose",
}


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def clean_timestamp(value):
    """Return the timestamp in ONE standard form (2026-01-01T08:00:00), or None if it is not valid.

    The database sorts timestamps as text and the alert rules compare them, so every
    stored timestamp must look the same. A timestamp with a time zone (for example
    ...+01:00 or ...Z) is converted to UTC; a date with no time is refused.
    """
    if not isinstance(value, str) or "T" not in value.upper() and " " not in value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat(timespec="seconds")


def problems_in(payload) -> list:
    """Return every problem with a POST /readings body. An empty list means valid."""
    if not isinstance(payload, dict):
        return ["body must be a JSON object"]
    problems = []
    for field in ("reading_id", "patient_id"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{field} is required (a non-empty string)")
    if clean_timestamp(payload.get("timestamp")) is None:
        problems.append("timestamp is required (ISO 8601, e.g. 2026-01-01T08:00:00)")

    present = 0
    for vital, (low, high) in config.RANGES.items():
        value = payload.get(vital)
        if value is None:
            continue  # a missing vital is allowed: the pipeline fills it (R9)
        if not _is_number(value):
            problems.append(f"{vital} must be a number")
        elif not low <= value <= high:
            problems.append(f"{vital} = {value} is outside {low} to {high}")
        else:
            present += 1
    if present == 0 and not any("is outside" in p or "must be a number" in p for p in problems):
        problems.append("at least one vital sign is required")
    return problems


def threshold_problems(body) -> list:
    """Problems with a PUT /patients/<id>/thresholds body."""
    if not isinstance(body, dict) or not body:
        return ["body must be a JSON object with at least one threshold"]
    problems = []
    for key, value in body.items():
        if key not in THRESHOLD_FIELDS:
            problems.append(f"{key} is not a known threshold")
            continue
        if value is None:
            continue  # None clears a threshold
        low, high = config.RANGES[THRESHOLD_FIELDS[key]]
        if not _is_number(value):
            problems.append(f"{key} must be a number")
        elif not low <= value <= high:
            problems.append(f"{key} = {value} is outside {low} to {high}")
    return problems


def status_code(outcome: str) -> int:
    """2xx fine, 4xx the caller's fault, 5xx ours (Week 8)."""
    return {
        "created": 201,
        "duplicate": 200,          # the copy is a success; nothing new was made
        "invalid": 422,
        "unknown patient": 404,
        "unauthorised": 401,
        "forbidden": 403,
    }.get(outcome, 500)
