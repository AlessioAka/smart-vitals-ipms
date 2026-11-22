"""Drift monitoring (extra feature from the module guide's list of ideas).

The model was trained on one set of readings. If the readings arriving now start to
look different (a new sensor brand, a different patient group, a broken firmware
update), the model's accuracy can quietly drop. Drift monitoring notices that
BEFORE anyone sees a wrong alert.

How: the Population Stability Index (PSI), a standard way of comparing two
distributions of the same variable.

  1. At training time, cut each vital's training values into 10 bins with an equal
     share of readings in each (deciles), and save the bin edges and shares.
  2. Live, put the newest stored readings into the SAME bins and compare shares:

        PSI = sum over bins of (live% - train%) * ln(live% / train%)

  Rule of thumb used in industry: below 0.10 stable, 0.10 to 0.25 worth watching,
  above 0.25 a real shift (investigate, maybe retrain).

Only aggregate numbers leave this module (one PSI per vital); no patient's data is shown.
"""
import json
import math

import numpy as np
import pandas as pd

from src import config

N_BINS = 10
MIN_LIVE_VALUES = 200      # fewer live values than this: too few to judge
WATCH, SHIFT = 0.10, 0.25  # PSI thresholds (see the module docstring)
EPS = 1e-4                 # stops log(0) when a bin is empty


def build_reference(df: pd.DataFrame) -> dict:
    """Bin edges and shares per vital, from TRAINING readings (impossible values already removed)."""
    ref = {}
    for v in config.VITALS:
        values = pd.to_numeric(df[v], errors="coerce").dropna().to_numpy()
        if len(values) < MIN_LIVE_VALUES:
            continue  # e.g. no glucose at all: nothing to compare against
        # Inner edges at the 10 %, 20 %, ... 90 % points. np.unique removes repeated edges
        # (temperature has few distinct values at 0.1 °C resolution).
        edges = np.unique(np.quantile(values, np.linspace(0, 1, N_BINS + 1)[1:-1]))
        ref[v] = {"edges": edges.round(3).tolist(), "shares": _shares(values, edges).tolist(),
                  "n": int(len(values))}
    return ref


def _shares(values: np.ndarray, edges) -> np.ndarray:
    """Share of values in each bin. Bins are (-inf, e1], (e1, e2], ..., (e_last, +inf)."""
    counts = np.bincount(np.searchsorted(edges, values, side="left"), minlength=len(edges) + 1)
    return counts / max(len(values), 1)


def psi(reference_shares, live_shares) -> float:
    """Population Stability Index between two lists of bin shares."""
    total = 0.0
    for e, a in zip(reference_shares, live_shares):
        e, a = max(e, EPS), max(a, EPS)
        total += (a - e) * math.log(a / e)
    return total


def verdict(value) -> str:
    if value is None:
        return "not enough data"
    if value >= SHIFT:
        return "shift"
    if value >= WATCH:
        return "watch"
    return "stable"


def drift_report(reference: dict, live_rows: list) -> dict:
    """PSI per vital for the live readings (a list of dicts with the vital columns)."""
    out = {}
    for v, ref in reference.items():
        values = np.array([r[v] for r in live_rows if r.get(v) is not None], dtype=float)
        if len(values) < MIN_LIVE_VALUES:
            out[v] = {"psi": None, "verdict": verdict(None), "n": int(len(values))}
            continue
        value = psi(ref["shares"], _shares(values, np.array(ref["edges"])))
        out[v] = {"psi": round(value, 3), "verdict": verdict(value), "n": int(len(values))}
    return out


def save_reference(reference: dict, path=config.DRIFT_REFERENCE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reference, indent=1), encoding="utf-8")


def load_reference(path=config.DRIFT_REFERENCE_PATH) -> dict:
    """The saved reference, or {} if training has not written one yet (the dashboard then says so)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
