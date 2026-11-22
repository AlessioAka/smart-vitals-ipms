"""R1 and the label rule."""
from src import rules


def test_normal_reading_is_normal():
    assert rules.label({"heart_rate": 70, "spo2": 98, "systolic": 120, "diastolic": 78, "temperature": 36.8}) == "Normal"


def test_single_bad_vital_is_warning():
    assert rules.label({"heart_rate": 70, "spo2": 90, "systolic": 120, "temperature": 36.8}) == "Warning"


def test_several_bad_vitals_are_critical():
    r = {"heart_rate": 135, "spo2": 88, "systolic": 92, "temperature": 39.4}
    assert rules.score(r) >= 6 and rules.label(r) == "Critical"


def test_missing_vitals_score_zero_not_crash():
    assert rules.label({"heart_rate": None, "spo2": float("nan")}) == "Normal"


def test_explain_names_the_vitals_that_scored():
    assert "spo2 = 88 (+3)" in rules.explain({"spo2": 88, "heart_rate": 70})


def test_risk_groups_follow_conditions_and_age():  # R1
    assert rules.risk_group([], 40) == "Low"
    assert rules.risk_group(["hypertension", "diabetes"], 50) == "Medium"
    assert rules.risk_group(["arrhythmia", "diabetes"], 70) == "High"
