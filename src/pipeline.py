"""The data pipeline (Weeks 4 and 5): small functions chained with .pipe().

    Ingest -> Validate -> Clean -> Correct -> Features -> Output

The SAME functions run when training the model and when the API classifies a
live reading, so the model never meets data prepared differently from its
training data (no "train/serve skew").

Every function takes a DataFrame and returns a NEW DataFrame. The raw data is
never overwritten (Week 5 "common mistakes").
"""
import numpy as np
import pandas as pd

from src import config

RISK_CODE = {"Low": 0, "Medium": 1, "High": 2}

FEATURES = [
    "heart_rate", "spo2", "systolic", "diastolic", "temperature", "glucose",
    "hr_mean5", "spo2_mean5", "sys_mean5", "temp_mean5",
    "hr_change5", "spo2_change5",
    "risk_code", "is_diabetic",
]


# ------------------------------------------------------------------ ingest
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Make the columns the right type and put each patient's readings in time order."""
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    for v in config.VITALS:
        if v not in out.columns:
            out[v] = np.nan
        out[v] = pd.to_numeric(out[v], errors="coerce")
    return out.sort_values(["patient_id", "timestamp"]).reset_index(drop=True)


# ---------------------------------------------------------------- validate
def range_check(df: pd.DataFrame) -> pd.DataFrame:
    """Impossible values become missing (NaN). Counted in `n_glitches`."""
    out = df.copy()
    out["n_glitches"] = 0
    for v, (low, high) in config.RANGES.items():
        # e.g. a heart rate of 250 or an SpO2 of 0: physically impossible, so a sensor glitch.
        # It becomes "missing" (NaN) rather than being deleted, so the rest of the reading is kept.
        bad = out[v].notna() & ((out[v] < low) | (out[v] > high))
        out["n_glitches"] += bad.astype(int)
        out[v] = out[v].mask(bad)
    return out


# ------------------------------------------------------------------- clean
def drop_stuck_sensor(df: pd.DataFrame) -> pd.DataFrame:
    """A vital whose rolling std is 0 over STUCK_WINDOW readings is stuck: set to NaN."""
    out = df.copy()
    out["n_stuck"] = 0
    for v in config.STUCK_COLUMNS:
        # Real bodies wobble: six identical heart rates in a row means the sensor has frozen.
        # groupby("patient_id") makes sure one patient's readings never mix with another's.
        std = out.groupby("patient_id")[v].transform(
            lambda s: s.rolling(config.STUCK_WINDOW, min_periods=config.STUCK_WINDOW).std()
        )
        stuck = std == 0
        out["n_stuck"] += stuck.astype(int)
        out[v] = out[v].mask(stuck)
    return out


def fill_short_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill gaps of at most FILL_LIMIT readings. Longer gaps stay missing."""
    out = df.copy()
    for v in config.VITALS:
        # Carry the last good value forward for at most 2 minutes. A longer gap stays missing:
        # inventing values for a long dropout would hide a real problem (R9).
        out[v] = out.groupby("patient_id")[v].ffill(limit=config.FILL_LIMIT)
    return out


# ---------------------------------------------------------------- features
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling means and changes per patient (trends, not just readings).

    Needs the columns `risk_group` and `has_diabetes` (from the patient register).
    """
    out = df.copy()
    w = config.ROLL_WINDOW
    g = out.groupby("patient_id")
    for name, col in [("hr_mean5", "heart_rate"), ("spo2_mean5", "spo2"),
                      ("sys_mean5", "systolic"), ("temp_mean5", "temperature")]:
        out[name] = g[col].transform(lambda s: s.rolling(w, min_periods=1).mean())
    # "Trends, not just readings": how much heart rate / SpO2 moved over the last 5 minutes.
    # A slow climb is an early sign of deterioration that a single reading cannot show.
    out["hr_change5"] = g["heart_rate"].transform(lambda s: s - s.shift(w - 1))
    out["spo2_change5"] = g["spo2"].transform(lambda s: s - s.shift(w - 1))
    out["risk_code"] = out["risk_group"].map(RISK_CODE)
    out["is_diabetic"] = out["has_diabetes"].astype(int)
    return out


# ------------------------------------------------------------------ chain
def clean_and_featurise(df: pd.DataFrame) -> pd.DataFrame:
    """The whole chain, readable top to bottom (Week 5: .pipe())."""
    return (
        df.pipe(prepare)
        .pipe(range_check)
        .pipe(drop_stuck_sensor)
        .pipe(fill_short_gaps)
        .pipe(add_features)
    )


def attach_register(df: pd.DataFrame, patients: list) -> pd.DataFrame:
    """Add risk_group and has_diabetes from the patient register."""
    reg = pd.DataFrame(patients)[["patient_id", "risk_group", "has_diabetes"]]
    return df.drop(columns=[c for c in ("risk_group", "has_diabetes") if c in df.columns]).merge(
        reg, on="patient_id", how="left"
    )


# ------------------------------------------------------------ data health
def data_health(df: pd.DataFrame) -> dict:
    """Week 5 data-health report: what is wrong with the raw data, in numbers."""
    n = len(df)
    vitals = [v for v in config.VITALS if v != "glucose"]
    missing = {v: round(float(df[v].isna().mean()) * 100, 2) for v in vitals}
    out_of_range = 0
    for v, (lo, hi) in config.RANGES.items():
        col = pd.to_numeric(df[v], errors="coerce")
        out_of_range += int(((col < lo) | (col > hi)).sum())
    return {
        "rows": n,
        "patients": int(df["patient_id"].nunique()),
        "duplicate_ids": int(df["reading_id"].duplicated().sum()),
        "missing_pct": missing,
        "out_of_range_values": out_of_range,
    }
