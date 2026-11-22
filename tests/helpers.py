"""Shared test helpers. Tests use a temporary database and a small model trained on the fly,
so they never touch your real data/ or models/ folders."""
import json
import tempfile
from pathlib import Path

import pandas as pd

from app.main import create_app
from simulator.generator import make_patients, simulate
from src import config, model as M
from src.pipeline import FEATURES, clean_and_featurise

PASSWORD = "test-password"
DEVICE_KEY = "test-device-key"
_MODEL = None


def small_model():
    """The saved model if there is one (what the API really serves); otherwise train a small one."""
    global _MODEL
    if _MODEL is None and config.MODEL_PATH.exists():
        _MODEL = M.load_model()
    if _MODEL is None:
        patients = make_patients(30, seed=99, prefix="X")
        _, observed = simulate(patients, minutes=180, seed=3, faults=True)
        df = clean_and_featurise(pd.DataFrame(observed))
        _MODEL = M.make_forest().fit(df[FEATURES], df["true_label"])
    return _MODEL


def make_client(register=None):
    """A Flask test client on a fresh temporary database."""
    tmp = Path(tempfile.mkdtemp())
    register = register or json.loads(config.PATIENTS_PATH.read_text())
    (tmp / "patients.json").write_text(json.dumps(register))
    app = create_app({"DB_PATH": str(tmp / "t.db"), "PATIENTS_PATH": str(tmp / "patients.json"),
                      "MODEL": small_model(), "DEVICE_KEY": DEVICE_KEY, "SECRET_KEY": "test-secret",
                      "DEMO_PASSWORD": PASSWORD})
    return app.test_client()


def post(client, reading, key=DEVICE_KEY):
    return client.post("/readings", json=reading, headers={"X-Device-Key": key})


def token(client, clinician_id="C01", password=PASSWORD):
    r = client.post("/login", json={"clinician_id": clinician_id, "password": password})
    return r.get_json().get("token")


def auth(client, clinician_id="C01"):
    return {"Authorization": f"Bearer {token(client, clinician_id)}"}


def normal_reading(patient_id="P001", minute=0, **overrides):
    """A healthy reading. (P001 has diabetes in the demo register, so it includes glucose.)"""
    base = {"reading_id": f"{patient_id}-{minute:04d}", "patient_id": patient_id,
            "timestamp": f"2026-01-01T08:{minute % 60:02d}:00" if minute < 60 else f"2026-01-01T{8 + minute // 60:02d}:{minute % 60:02d}:00",
            "heart_rate": 70, "spo2": 97.5, "systolic": 120, "diastolic": 76, "temperature": 36.7,
            "glucose": 120}
    return base | overrides


def critical_reading(patient_id="P001", minute=0, **overrides):
    return normal_reading(patient_id, minute, heart_rate=135, spo2=88.0, systolic=92,
                          diastolic=60, temperature=39.4, glucose=300) | overrides
