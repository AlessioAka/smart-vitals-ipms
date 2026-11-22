"""Models, honest evaluation and saving (Weeks 1, 2, 5; R3, Output 4).

Three models are compared:
  baseline  - always the most common label (the thing to beat),
  logreg    - logistic regression (Week 2; simple, explainable),
  forest    - random forest (non-parametric; handles thresholds and interactions).

Every model is a scikit-learn Pipeline: the imputer (fills gaps from missing
readings, R9) and scaler are fitted on the TRAINING rows only, so nothing leaks
from the test set (Week 5).
"""
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src import config
from src.pipeline import FEATURES


def split_by_patient(df: pd.DataFrame, test_size: float = 0.25):
    """Keep back whole PATIENTS the model has never seen (not random rows)."""
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=config.RANDOM_STATE)
    train_idx, test_idx = next(splitter.split(df, groups=df["patient_id"]))
    return df.iloc[train_idx], df.iloc[test_idx]


def split_random_rows(df: pd.DataFrame, test_size: float = 0.25):
    """The WRONG way (rows of the same patient land in both sets). Used only to show the leak."""
    test = df.sample(frac=test_size, random_state=config.RANDOM_STATE)
    return df.drop(test.index), test


def make_baseline():
    return Pipeline([("model", DummyClassifier(strategy="most_frequent"))])


def make_logreg():
    return Pipeline([
        ("fill", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def make_forest():
    return Pipeline([
        ("fill", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(
            n_estimators=200, min_samples_leaf=3, class_weight="balanced_subsample",
            random_state=config.RANDOM_STATE, n_jobs=-1)),
    ])


def evaluate(model, X: pd.DataFrame, y: pd.Series) -> dict:
    """Accuracy, per-class precision / recall / F1, and the confusion matrix (Output 4)."""
    pred = model.predict(X)
    labels = config.LABELS
    p, r, f, support = precision_recall_fscore_support(y, pred, labels=labels, zero_division=0)
    cm = confusion_matrix(y, pred, labels=labels)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "precision": dict(zip(labels, p.round(3).tolist())),
        "recall": dict(zip(labels, r.round(3).tolist())),
        "f1": dict(zip(labels, f.round(3).tolist())),
        "macro_f1": float(np.mean(f)),
        "recall_critical": float(r[labels.index("Critical")]),
        "confusion_matrix": cm.tolist(),
        "support": dict(zip(labels, support.tolist())),
    }


def save_model(model, name: str, metrics: dict, path=config.MODEL_PATH) -> None:
    """Save the model plus a small meta file saying what it is and how well it did."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    meta = {
        "name": name,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": FEATURES,
        "labels": config.LABELS,
        "test_metrics": metrics,
    }
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))


def load_model(path=config.MODEL_PATH):
    """Load a saved model. A forest trained with n_jobs=-1 is told to use 1 thread for serving:
    starting threads for ONE row costs more than the prediction itself."""
    model = joblib.load(path)
    for step in model.named_steps.values():
        if hasattr(step, "n_jobs"):
            step.n_jobs = 1
    return model


def predict_status(model, features: pd.DataFrame) -> str:
    """One row of features in, one label out."""
    return str(model.predict(features[FEATURES])[0])
