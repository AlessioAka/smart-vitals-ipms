"""Alerts and per-patient thresholds (R4, R10) plus alarm-fatigue control.

`make_alert` builds what the brief requires in every alert: the patient ID,
the vitals recorded and a timestamp - plus the assigned clinician and the
reasons (which vitals drove it).
"""
from datetime import datetime, timedelta

from src import config

_ORDER = ["Normal", "Warning", "Critical"]


def apply_thresholds(status: str, vitals: dict, thresholds: dict):
    """R10: a clinician's own limits can only RAISE the status by one level, never lower it.

    thresholds look like {"heart_rate_high": 100, "spo2_low": 94}.
    Returns (new_status, list of breach sentences).
    """
    breaches = []
    for key, limit in thresholds.items():
        vital, side = key.rsplit("_", 1)   # "heart_rate_high" -> ("heart_rate", "high")
        value = vitals.get(vital)
        if value is None:
            continue
        if (side == "low" and value < limit) or (side == "high" and value > limit):
            breaches.append(f"{vital} = {value} breaks this patient's {side} limit of {limit}")
    if breaches:
        # One level up, capped at Critical. Never down: a clinician's limit must not be able to
        # silence what the model flagged (safety first).
        status = _ORDER[min(_ORDER.index(status) + 1, 2)]
    return status, breaches


def make_alert(patient, reading_id: str, timestamp: str, status: str, vitals: dict, reasons: list) -> dict:
    """The alert the assigned clinician receives."""
    return {
        "patient_id": patient["patient_id"],
        "clinician_id": patient["clinician_id"],
        "reading_id": reading_id,
        "timestamp": timestamp,
        "status": status,
        "vitals": {k: v for k, v in vitals.items() if v is not None},
        "reasons": reasons,
    }


def is_late(ts: str, newest_ts) -> bool:
    """A reading measured more than STALE_MINUTES before the newest stored one is late."""
    if newest_ts is None:
        return False
    return datetime.fromisoformat(ts) < datetime.fromisoformat(newest_ts) - timedelta(minutes=config.STALE_MINUTES)


def within_cooldown(ts: str, last_alert_ts: str) -> bool:
    """Alarm-fatigue control: one alert per episode (until acknowledged or the cooldown ends)."""
    gap = datetime.fromisoformat(ts) - datetime.fromisoformat(last_alert_ts)
    return gap <= timedelta(minutes=config.ALERT_COOLDOWN_MINUTES)


def is_escalated(alert: dict, newest_ts) -> bool:
    """An unacknowledged alert becomes 'escalated' after ESCALATE_AFTER_MINUTES.

    `newest_ts` is the simulated "now": the newest reading from ANY patient
    (db.newest_ts). Using only this patient's readings would mean an alert never
    escalates if the patient's sensor goes silent straight after it - the worst case.
    """
    if alert["acknowledged"] or newest_ts is None:
        return False
    waited = datetime.fromisoformat(newest_ts) - datetime.fromisoformat(alert["ts"])
    return waited >= timedelta(minutes=config.ESCALATE_AFTER_MINUTES)
