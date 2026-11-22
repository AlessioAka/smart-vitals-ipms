"""Classify one incoming reading using the patient's recent history (R3, R9).

The reading is appended to the patient's last few stored readings, and the SAME
pipeline used for training cleans it and builds the trend features. That is how
a single missing vital, a frozen sensor or a short gap are handled the same way
in training and in live use.
"""
import math

import pandas as pd

from src import config, model as M, pipeline


def classify(model, patient, history_rows: list, reading: dict):
    """Return (status, cleaned_vitals) for the new reading."""
    # 1. The patient's recent stored readings (oldest first) + the new one at the end.
    rows = [{**h, "timestamp": h["ts"]} for h in history_rows]
    rows.append({v: reading.get(v) for v in config.VITALS}
                | {"reading_id": reading["reading_id"], "patient_id": reading["patient_id"],
                   "timestamp": reading["timestamp"]})
    df = pd.DataFrame(rows)
    df["risk_group"] = patient["risk_group"]
    df["has_diabetes"] = bool(patient["has_diabetes"])
    # 2. Exactly the same cleaning + features as in training (no train/serve skew).
    feats = pipeline.clean_and_featurise(df)
    # 3. Only the NEW reading's row is classified; the history just feeds its trend features.
    last = feats[feats["reading_id"] == reading["reading_id"]].iloc[[-1]]
    status = M.predict_status(model, last)
    vitals = {v: _tidy(v, float(last[v].iloc[0])) for v in config.VITALS}
    return status, vitals


def _tidy(vital: str, value: float):
    """Whole numbers for pulse, pressure and glucose; one decimal for SpO2 and temperature."""
    if math.isnan(value):
        return None
    return int(round(value)) if vital in ("heart_rate", "systolic", "diastolic", "glucose") else round(value, 1)
