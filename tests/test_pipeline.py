"""Week 4 and 5 cleaning functions."""
import numpy as np
import pandas as pd

from src import pipeline as P


def frame(hr, patient="A"):
    n = len(hr)
    return pd.DataFrame({"patient_id": patient, "reading_id": [f"{patient}{i}" for i in range(n)],
                         "timestamp": pd.date_range("2026-01-01 08:00", periods=n, freq="min"),
                         "heart_rate": hr, "spo2": 97.0, "systolic": 120.0, "diastolic": 75.0,
                         "temperature": 36.7, "glucose": np.nan})


def test_range_check_blanks_impossible_values():
    out = P.range_check(frame([70, 250, 72]))
    assert np.isnan(out.loc[1, "heart_rate"]) and out.loc[1, "n_glitches"] == 1
    assert out.loc[0, "heart_rate"] == 70


def test_short_gap_is_filled_but_long_gap_is_not():
    out = P.fill_short_gaps(frame([70, np.nan, np.nan, np.nan, 75]))
    assert out.loc[1, "heart_rate"] == 70 and out.loc[2, "heart_rate"] == 70
    assert np.isnan(out.loc[3, "heart_rate"])  # third missing reading: limit of 2


def test_stuck_sensor_is_detected():
    out = P.drop_stuck_sensor(frame([70, 71, 72, 80, 80, 80, 80, 80, 80, 80]))
    assert out["heart_rate"].isna().sum() >= 1 and out.loc[0, "heart_rate"] == 70


def test_changing_values_are_not_called_stuck():
    out = P.drop_stuck_sensor(frame([70, 71, 72, 73, 72, 71, 70, 71]))
    assert out["heart_rate"].isna().sum() == 0


def test_features_never_mix_patients():
    df = pd.concat([frame([60, 60, 60], "A"), frame([100, 100, 100], "B")])
    df["risk_group"], df["has_diabetes"] = "Low", False
    out = P.add_features(P.prepare(df))
    assert out[out.patient_id == "A"]["hr_mean5"].max() == 60


def test_raw_data_is_not_overwritten():
    raw = frame([70, 250, 72])
    P.range_check(raw)
    assert raw.loc[1, "heart_rate"] == 250


def test_data_health_counts_problems():
    df = frame([70, 250, 72])
    df.loc[2, "reading_id"] = df.loc[0, "reading_id"]
    h = P.data_health(df)
    assert h["duplicate_ids"] == 1 and h["out_of_range_values"] == 1
