"""T14 · Drift monitoring (extra feature): the dashboard notices when live readings stop
looking like the training data, and stays quiet when they do not."""
import numpy as np
import pandas as pd

from src import config, drift
from tests.helpers import auth, make_client, normal_reading, post

RNG = np.random.default_rng(0)


def _frame(hr_mean: float, n: int = 3000) -> pd.DataFrame:
    return pd.DataFrame({"heart_rate": RNG.normal(hr_mean, 8, n), "spo2": RNG.normal(97, 1, n),
                         "systolic": RNG.normal(120, 10, n), "diastolic": RNG.normal(78, 6, n),
                         "temperature": RNG.normal(36.7, 0.2, n).round(1), "glucose": np.nan})


def test_same_distribution_is_stable():
    ref = drift.build_reference(_frame(72))
    report = drift.drift_report(ref, _frame(72, 1000).to_dict("records"))
    assert all(r["verdict"] == "stable" for r in report.values()), report


def test_shifted_heart_rate_is_flagged_and_only_it():
    ref = drift.build_reference(_frame(72))
    report = drift.drift_report(ref, _frame(95, 1000).to_dict("records"))  # every pulse ~23 bpm higher
    assert report["heart_rate"]["verdict"] == "shift" and report["heart_rate"]["psi"] > drift.SHIFT
    assert report["spo2"]["verdict"] == "stable"


def test_too_few_live_values_are_not_judged():
    ref = drift.build_reference(_frame(72))
    report = drift.drift_report(ref, _frame(150, 20).to_dict("records"))
    assert report["heart_rate"]["psi"] is None and report["heart_rate"]["verdict"] == "not enough data"


def test_a_vital_nobody_has_is_left_out_not_crashed():
    assert "glucose" not in drift.build_reference(_frame(72))  # all NaN: nothing to compare against


def test_psi_is_zero_for_identical_shares_and_grows_with_difference():
    assert drift.psi([0.5, 0.5], [0.5, 0.5]) == 0
    assert drift.psi([0.5, 0.5], [0.6, 0.4]) < drift.psi([0.5, 0.5], [0.9, 0.1])


def test_saved_reference_matches_the_vitals_the_model_uses():
    ref = drift.load_reference()
    assert ref, "run python -m src.train to write models/drift_reference.json"
    assert set(ref) <= set(config.VITALS) and {"heart_rate", "spo2", "systolic"} <= set(ref)


def test_model_health_endpoint_needs_login_and_reports_drift():
    c = make_client()
    assert c.get("/model/health").status_code == 401
    post(c, normal_reading(minute=1))
    body = c.get("/model/health", headers=auth(c)).get_json()
    assert body["name"] and set(body["drift"]) <= set(config.VITALS)
    assert body["drift_verdict"] == "not enough data"  # one reading is far too few to judge
