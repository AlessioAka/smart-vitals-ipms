"""R3 and Output 4: the saved model on patients it has never seen."""
from src import config, model as M
from src.pipeline import FEATURES
from src.train import load_training_frame

TARGET = 0.85  # a floor for the test; your design-plan target (e.g. 0.90) is reported in results


_FRAME = None


def _split():
    """Cleaning 27,000 readings takes a while, so do it once for all the tests in this file."""
    global _FRAME
    if _FRAME is None:
        _FRAME = load_training_frame()
    return M.split_by_patient(_FRAME)


def test_split_keeps_patients_apart():
    train, test = _split()
    assert not set(train.patient_id) & set(test.patient_id)


def test_saved_model_finds_critical_readings_in_unseen_patients():
    _, test = _split()
    m = M.load_model()
    r = M.evaluate(m, test[FEATURES], test["true_label"])
    assert r["recall_critical"] >= TARGET, r["recall"]


def test_model_beats_always_normal_baseline_on_critical():
    train, test = _split()
    base = M.make_baseline().fit(train[FEATURES], train["true_label"])
    b = M.evaluate(base, test[FEATURES], test["true_label"])
    m = M.evaluate(M.load_model(), test[FEATURES], test["true_label"])
    assert b["recall_critical"] == 0.0 and m["recall_critical"] > b["recall_critical"]
    assert b["accuracy"] > 0.85  # accuracy alone would have called the baseline "good"


def test_evaluation_reports_all_the_required_metrics():
    _, test = _split()
    r = M.evaluate(M.load_model(), test[FEATURES], test["true_label"])
    assert {"accuracy", "precision", "recall", "f1", "confusion_matrix"} <= set(r)
    assert len(r["confusion_matrix"]) == 3


def test_model_meta_file_exists_next_to_the_model():
    assert config.MODEL_PATH.with_suffix(".json").exists()
