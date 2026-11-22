"""IoT-style sensor simulator (R2) with on-purpose problems (R9).

Uses only numpy and the standard library, so the simulator container stays small.

What it makes
-------------
* make_patients(): a register of patients in Low / Medium / High risk groups (R1).
* simulate(): one reading a minute per patient, with
    - deterioration episodes (a vital drifts, then recovers),
    - dropouts (readings never arrive),
    - missing single vitals,
    - impossible values (glitches),
    - a stuck sensor (the same value repeated),
    - late readings (arrive 20-45 minutes after they were measured),
    - resent copies (the same reading_id sent again).
It returns the messages in the order they would ARRIVE, plus the truth.
"""
from datetime import datetime, timedelta

import numpy as np

from src import config, rules

CONDITIONS = ["hypertension", "diabetes", "arrhythmia"]
EPISODE_RATE_PER_HOUR = {"Low": 0.20, "Medium": 0.45, "High": 0.80}
CLINICIANS = ["C01", "C02", "C03", "C04"]


# ---------------------------------------------------------------- patients
def make_patients(n: int = 20, seed: int = 7, prefix: str = "P") -> list:
    """A synthetic patient register. No real people: every record is invented."""
    rng = np.random.default_rng(seed)
    patients = []
    for i in range(n):
        n_cond = int(rng.choice([0, 1, 2, 3], p=[0.25, 0.35, 0.28, 0.12]))
        conditions = sorted(rng.choice(CONDITIONS, size=n_cond, replace=False).tolist())
        age = int(rng.integers(35, 89))
        patients.append(
            {
                "patient_id": f"{prefix}{i + 1:03d}",
                "age": age,
                "conditions": conditions,
                "risk_group": rules.risk_group(conditions, age),
                "has_diabetes": "diabetes" in conditions,
                "clinician_id": CLINICIANS[i % len(CLINICIANS)],
            }
        )
    return patients


# ------------------------------------------------------------ true vitals
def _baselines(patient: dict) -> dict:
    cond = patient["conditions"]
    older = 1.0 if patient["age"] >= 65 else 0.0
    return {
        "heart_rate": 68 + (6 if "arrhythmia" in cond else 0),
        "spo2": 97.6 - 0.8 * older,
        "systolic": 118 + (22 if "hypertension" in cond else 0) + 6 * older,
        "diastolic": 76 + (10 if "hypertension" in cond else 0),
        "temperature": 36.7,
        "glucose": 138 if "diabetes" in cond else None,
    }


def _noise_sd(patient: dict) -> dict:
    wobble = 1.6 if "arrhythmia" in patient["conditions"] else 1.0
    return {"heart_rate": 3.0 * wobble, "spo2": 0.6, "systolic": 5.0, "diastolic": 3.5,
            "temperature": 0.12, "glucose": 11.0}


def _episode_effect(kind: str, s: float, has_diabetes: bool) -> dict:
    """How far each vital moves at severity s (0 to ~1.1)."""
    if kind == "infection":
        return {"heart_rate": 48 * s, "temperature": 2.3 * s, "systolic": -34 * s, "spo2": -4.5 * s}
    if kind == "hypoxia":
        return {"spo2": -10 * s, "heart_rate": 40 * s, "systolic": -8 * s}
    if kind == "hypertensive":
        return {"systolic": 85 * s, "diastolic": 38 * s, "heart_rate": 20 * s}
    if kind == "glycaemic" and has_diabetes:
        return {"glucose": 230 * s, "heart_rate": 18 * s}
    return {"heart_rate": 45 * s, "spo2": -3 * s}


def _true_vitals(patient: dict, minutes: int, rng) -> list:
    """The real vital signs, minute by minute, before any sensor problems."""
    base, sd = _baselines(patient), _noise_sd(patient)
    state = {v: 0.0 for v in base}  # AR(1) wobble around the baseline
    rate = EPISODE_RATE_PER_HOUR[patient["risk_group"]] / 60
    kinds = ["infection", "hypoxia", "hypertensive"] + (["glycaemic"] if patient["has_diabetes"] else [])
    episode = None  # (kind, start, duration, peak)
    rows = []
    for m in range(minutes):
        if episode is None and rng.random() < rate:
            episode = (str(rng.choice(kinds)), m, int(rng.integers(20, 45)), float(rng.uniform(0.8, 1.6)))
        effect = {}
        if episode is not None:
            kind, start, dur, peak = episode
            pos = (m - start) / dur
            if pos >= 1:
                episode = None
            else:
                s = peak * (1 - abs(2 * pos - 1))  # up, then down (triangle)
                effect = _episode_effect(kind, s, patient["has_diabetes"])
        row = {}
        for v, b in base.items():
            if b is None:
                row[v] = None
                continue
            state[v] = 0.9 * state[v] + rng.normal(0, sd[v] * 0.45)
            value = b + state[v] + effect.get(v, 0.0)
            row[v] = value
        row["spo2"] = min(row["spo2"], 100.0)
        rows.append(row)
    return rows


def _rounded(v: str, value):
    if value is None:
        return None
    if v in ("heart_rate", "systolic", "diastolic", "glucose"):
        return int(round(value))
    return round(float(value), 1)


# ------------------------------------------------------------- simulation
def _stamp(minute: int) -> str:
    return (datetime.fromisoformat(config.SIM_START) + timedelta(minutes=minute)).isoformat()


def simulate(patients: list, minutes: int = 60, seed: int = 11, faults: bool = True):
    """Return (events, observed).

    events   - dicts {"send_at", "reading", "fault"} in ARRIVAL order (late and
               resent copies are where they would really arrive).
    observed - one dict per reading that was sent (first copy), with the truth
               label, for training and for fault tests.
    """
    events, observed = [], []
    for idx, patient in enumerate(patients):
        rng = np.random.default_rng(seed * 1000 + idx)
        truth = _true_vitals(patient, minutes, rng)
        dropout_until = -1
        stuck = {}  # vital -> (value, until_minute)
        for m in range(minutes):
            # The label is made from the TRUE vitals, before any sensor fault: the "ground truth"
            # the system should recover even when the message itself is damaged.
            true_row = {v: _rounded(v, x) for v, x in truth[m].items()}
            true_label = rules.label(true_row)
            sent = dict(true_row)
            tags = []

            # ---- R9: problems created ON PURPOSE, so the system can be tested against them.
            if faults:
                # Dropout: the sensor goes silent for 2-8 minutes (nothing is sent at all).
                if m > dropout_until and rng.random() < 0.012:
                    dropout_until = m + int(rng.integers(2, 9))
                if m <= dropout_until:
                    continue  # nothing arrives: sensor dropout (R9)
                # Stuck sensor: the same value repeated for 8-12 minutes.
                for v in config.STUCK_COLUMNS:
                    if v in stuck and m < stuck[v][1]:
                        sent[v] = stuck[v][0]
                        tags.append("stuck")
                    elif rng.random() < 0.0012:
                        stuck[v] = (sent[v], m + int(rng.integers(8, 13)))
                # One vital missing from the message.
                if rng.random() < 0.02:
                    v = str(rng.choice([k for k in sent if sent[k] is not None]))
                    sent[v] = None
                    tags.append("missing_vital")
                # Glitch: a physically impossible value.
                if rng.random() < 0.012:
                    v = str(rng.choice([k for k in sent if sent[k] is not None]))
                    sent[v] = {"heart_rate": 250, "spo2": 0, "systolic": 0, "diastolic": 400,
                               "temperature": 85.0, "glucose": 9999}[v]
                    tags.append("glitch")

            reading = {
                "reading_id": f"{patient['patient_id']}-{m:04d}",
                "patient_id": patient["patient_id"],
                "timestamp": _stamp(m),
                **sent,
            }
            # Late delivery (network delay: arrives 20-45 minutes after it was measured)
            # and resent copies (the phone retries and the same reading_id arrives twice).
            late = faults and rng.random() < 0.03
            send_at = m + (int(rng.integers(20, 46)) if late else 0)
            if late:
                tags.append("late")
            first_tag = tags[0] if tags else ""
            events.append({"send_at": send_at, "reading": reading, "fault": first_tag})
            if faults and rng.random() < 0.04:  # a resent copy
                events.append({"send_at": send_at + int(rng.integers(0, 4)),
                               "reading": dict(reading), "fault": "duplicate"})
            observed.append({**reading, "minute": m, "fault": first_tag, "true_label": true_label,
                             "risk_group": patient["risk_group"],
                             "has_diabetes": patient["has_diabetes"]})
    events.sort(key=lambda e: e["send_at"])  # stable: keeps order within a minute
    return events, observed
