"""The points rule that makes the labels (Normal / Warning / Critical).

It is in the spirit of NEWS2 (Royal College of Physicians, 2017), which scores
pulse, oxygen saturation, systolic blood pressure and temperature. It is NOT
NEWS2: the bands are simplified, and the diastolic and glucose bands are my own
additions because the brief monitors them. State this in your report.

IMPORTANT LIMITATION: a model trained on labels made by this rule largely
re-learns the rule. Discuss it as a limitation (see docs/assumptions.md).
"""
import math

# Each table: (upper_limit_inclusive, points). Values above the last limit get the last points.
_BANDS = {
    "heart_rate": [(40, 3), (50, 1), (90, 0), (110, 1), (130, 2), (math.inf, 3)],
    "systolic": [(90, 3), (100, 2), (110, 1), (219, 0), (math.inf, 3)],
    "temperature": [(35.0, 3), (36.0, 1), (38.0, 0), (39.0, 1), (math.inf, 2)],
    "diastolic": [(50, 1), (119, 0), (math.inf, 2)],
    "glucose": [(53, 3), (69, 2), (180, 0), (250, 1), (350, 2), (math.inf, 3)],
}
# SpO2 is the other way round: LOW is bad.
_SPO2_BANDS = [(91, 3), (93, 2), (95, 1), (math.inf, 0)]


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _points(value, bands) -> int:
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def points_for(reading: dict) -> dict:
    """Points per vital for one reading. Missing vitals score 0 (nothing to judge)."""
    out = {}
    for vital, bands in _BANDS.items():
        value = reading.get(vital)
        if not _is_missing(value):
            out[vital] = _points(value, bands)
    spo2 = reading.get("spo2")
    if not _is_missing(spo2):
        out["spo2"] = _points(spo2, _SPO2_BANDS)
    return out


def score(reading: dict) -> int:
    """Total points."""
    return sum(points_for(reading).values())


def label(reading: dict) -> str:
    """Critical: 6+ points. Warning: 3-5 points, or any single vital worth 3. Else Normal."""
    pts = points_for(reading)
    total = sum(pts.values())
    if total >= 6:
        return "Critical"
    if total >= 3 or any(p == 3 for p in pts.values()):
        return "Warning"
    return "Normal"


def explain(reading: dict) -> list:
    """Which vitals earned points, as plain sentences for the clinician."""
    pts = points_for(reading)
    return [
        f"{vital} = {reading[vital]} (+{p})"
        for vital, p in sorted(pts.items(), key=lambda kv: -kv[1])
        if p > 0
    ]


def risk_group(conditions: list, age: int) -> str:
    """R1: Low / Medium / High from chronic conditions and age (history)."""
    weight = {"arrhythmia": 2, "diabetes": 1, "hypertension": 1}
    total = sum(weight.get(c, 0) for c in conditions)
    if age >= 75:
        total += 2
    elif age >= 65:
        total += 1
    if total >= 4:
        return "High"
    if total >= 2:
        return "Medium"
    return "Low"
