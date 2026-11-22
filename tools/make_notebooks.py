"""Writes notebooks/*.ipynb from the cell lists below.  python tools/make_notebooks.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_n = 0


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(True)}


def write(name, cells):
    for i, c in enumerate(cells):
        c["id"] = f"cell{i:02d}"
    nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}}
    (ROOT / "notebooks" / name).write_text(json.dumps(nb, indent=1), encoding="utf-8")


SETUP = code('''
# SETUP: make the project's own code importable, whatever folder VS Code started in.
import sys, pathlib
ROOT = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "src").exists())
sys.path.insert(0, str(ROOT))
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
pd.set_option("display.width", 140); pd.set_option("display.max_columns", 30)
print("Project root:", ROOT)
''')

# ------------------------------------------------------------ notebook 1
nb1 = [
    md('''
# 01 · First model (R3, Output 4)
**Skills:** Week 1 train/test, Week 2 classification and overfitting, Week 4 data health, Week 5 pipelines and leakage.

**Run all cells (Run All in VS Code).** The CHECK lines print PASS or TODO.
The grey boxes marked **YOUR TURN** are for *your* words: they are the thinking the marks are for.
'''),
    SETUP,
    md('## 1 · The model in one line\n**YOUR TURN:** write it: *what it decides, from what, the main measure and the target.*\n\n> _e.g. "Classify each reading as Normal / Warning / Critical from the vitals and 5-minute trends; main measure: recall for Critical on unseen patients; target ≥ 0.90."_'),
    md('## 2 · Load the data and check its health (Week 5)'),
    code('''
from src import config, pipeline as P
raw = pd.read_csv(config.DATA_PATH)
print(raw.shape)
raw.head()
'''),
    code('''
health = P.data_health(raw)
for k, v in health.items():
    print(f"{k:22s} {v}")
print()
print("Share of each true label:")
print((raw["true_label"].value_counts(normalize=True) * 100).round(1).astype(str) + " %")
'''),
    code('''
# CHECK: is Critical rare? (If so, accuracy will mislead us.)
share = (raw["true_label"] == "Critical").mean()
print("PASS: Critical is rare, so accuracy alone will mislead." if share < 0.10 else "TODO: Critical is not rare in your data")
'''),
    md('**YOUR TURN:** what in the health report would worry you, and how will the pipeline deal with it?'),
    md('## 3 · Clean and build features (the same functions the API uses)'),
    code('''
df = P.clean_and_featurise(raw)
print("impossible values blanked:", int(df["n_glitches"].sum()), "| stuck-sensor values blanked:", int(df["n_stuck"].sum()))
print("rows still missing a heart rate after cleaning:", int(df["heart_rate"].isna().sum()))
df[["patient_id", "timestamp", "heart_rate", "hr_mean5", "hr_change5", "spo2", "true_label"]].head(8)
'''),
    md('## 4 · Keep back patients the model has never seen'),
    code('''
from src import model as M
from src.pipeline import FEATURES
train, test = M.split_by_patient(df)
overlap = set(train.patient_id) & set(test.patient_id)
print(len(train.patient_id.unique()), "training patients,", len(test.patient_id.unique()), "test patients")
print("PASS: no patient is in both sets" if not overlap else "FIX: patients appear in both sets")
X_tr, y_tr, X_te, y_te = train[FEATURES], train["true_label"], test[FEATURES], test["true_label"]
'''),
    md('## 5 · Baseline, then two real models'),
    code('''
models = {"baseline (always Normal)": M.make_baseline(),
          "logistic regression": M.make_logreg(),
          "random forest": M.make_forest()}
results = {}
for name, m in models.items():
    m.fit(X_tr, y_tr)
    results[name] = M.evaluate(m, X_te, y_te)
table = pd.DataFrame({n: {"accuracy": r["accuracy"], "macro F1": r["macro_f1"],
                          "precision Critical": r["precision"]["Critical"],
                          "recall Critical": r["recall"]["Critical"], "F1 Critical": r["f1"]["Critical"]}
                      for n, r in results.items()}).T.round(3)
table
'''),
    code('''
base = results["baseline (always Normal)"]
print(f"The baseline is right {base['accuracy']:.0%} of the time but finds {base['recall_critical']:.0%} of Critical readings.")
'''),
    md('**YOUR TURN:** why is accuracy the wrong main measure here? Which model do you choose, and why (cite the numbers)?'),
    md('## 6 · Confusion matrices (Output 4)'),
    code('''
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
for ax, (name, r) in zip(axes, results.items()):
    cm = np.array(r["confusion_matrix"])
    ax.imshow(cm, cmap="Blues"); ax.set_title(name, fontsize=10)
    ax.set_xticks(range(3), config.LABELS); ax.set_yticks(range(3), config.LABELS)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
plt.tight_layout(); plt.show()
'''),
    md('## 7 · Is a perfect score a warning? Row split vs patient split (Week 5)'),
    code('''
r_train, r_test = M.split_random_rows(df)
leaky = M.make_forest().fit(r_train[FEATURES], r_train["true_label"])
leaky_acc = M.evaluate(leaky, r_test[FEATURES], r_test["true_label"])["accuracy"]
print(f"forest, random-row split : accuracy {leaky_acc:.3f}   <- the model has already met these patients")
print(f"forest, patient split    : accuracy {results['random forest']['accuracy']:.3f}   <- honest")
'''),
    md('## 8 · What did the forest rely on?'),
    code('''
forest = models["random forest"]
imp = pd.Series(forest.named_steps["model"].feature_importances_, index=FEATURES).sort_values(ascending=False)
imp.head(8).round(3)
'''),
    md('''
**YOUR TURN (limitation):** the labels were made by a points rule on the same vitals the model sees. What does that mean for how impressive these numbers are? (See `docs/assumptions.md`.)
'''),
    md('## 9 · Target check'),
    code('''
target = 0.90
r = results["random forest"]["recall_critical"]
print(f"recall for Critical = {r:.3f} (target {target})")
print("PASS: target met on unseen patients" if r >= target else "TODO: below target - what could you try? (more data, features, a Critical threshold)")
'''),
    md('Save the chosen model for the API with `python -m src.train` (it also writes `docs/results/model_comparison.md`).'),
]
write("01_first_model.ipynb", nb1)

# ------------------------------------------------------------ notebook 2
nb2 = [
    md('''
# 02 · Data, problems and the pipeline (R1, R2, R9)
**Skills:** Week 4 data sourcing, missing values, outliers, edge vs cloud; Week 5 pipelines and honest charts.
'''),
    SETUP,
    md('## 1 · Who are the patients? (R1: Low / Medium / High risk)'),
    code('''
import json
from src import config
patients = pd.DataFrame(json.loads(config.PATIENTS_PATH.read_text()))
print(patients["risk_group"].value_counts().to_string())
patients[["patient_id", "age", "conditions", "risk_group", "clinician_id"]].head(8)
'''),
    md('## 2 · A messy hour from the simulator (R2, R9)'),
    code('''
from simulator.generator import simulate
events, observed = simulate(patients.to_dict("records"), minutes=60, seed=11, faults=True)
faults = pd.Series([e["fault"] or "clean" for e in events]).value_counts()
print(len(events), "messages arrive for", len(observed), "readings measured")
faults
'''),
    md('**YOUR TURN:** which of these problems can the *edge* fix cheaply, and which need the *cloud*? (Week 4: four constraints, four questions.)'),
    md('## 3 · Each cleaning step, one at a time'),
    code('''
from src import pipeline as P
obs = pd.DataFrame(observed)
step0 = P.prepare(obs)
step1 = P.range_check(step0)
step2 = P.drop_stuck_sensor(step1)
step3 = P.fill_short_gaps(step2)
summary = pd.DataFrame({
    "after step": ["raw", "range check", "stuck sensor", "short-gap fill"],
    "missing heart rates": [int(s["heart_rate"].isna().sum()) for s in (step0, step1, step2, step3)],
    "missing SpO2": [int(s["spo2"].isna().sum()) for s in (step0, step1, step2, step3)],
})
summary
'''),
    code('''
# One patient, raw vs cleaned heart rate (honest chart: units labelled, fixed sensible range)
bad = obs[obs["fault"] == "glitch"]["patient_id"]
pid = bad.iloc[0] if len(bad) else obs["patient_id"].iloc[0]
a = step0[step0.patient_id == pid]; b = step3[step3.patient_id == pid]
fig, ax = plt.subplots(figsize=(9, 3))
ax.plot(a["timestamp"], a["heart_rate"], color="#bbbbbb", label="raw (as sent)")
ax.plot(b["timestamp"], b["heart_rate"], color="#1f4e79", label="cleaned")
ax.set_ylabel("Heart rate (bpm)"); ax.set_xlabel("Time (simulated clock)"); ax.legend(frameon=False)
ax.set_title(f"Patient {pid}: raw vs cleaned"); plt.tight_layout(); plt.show()
'''),
    md('## 4 · The label rule (what Normal / Warning / Critical mean here)'),
    code('''
from src import rules
examples = [
    {"heart_rate": 72, "spo2": 98, "systolic": 120, "temperature": 36.8},
    {"heart_rate": 72, "spo2": 90, "systolic": 120, "temperature": 36.8},
    {"heart_rate": 135, "spo2": 88, "systolic": 92, "temperature": 39.4},
]
pd.DataFrame([{**e, "points": rules.score(e), "label": rules.label(e)} for e in examples])
'''),
    md('**YOUR TURN:** how does this differ from NEWS2 (Royal College of Physicians, 2017)? Read it, cite it, and list the differences.'),
    md('## 5 · Edge: a tiny early-warning rule that works offline'),
    code('''
from simulator import edge
print(edge.early_warning({"spo2": 85, "heart_rate": 160}))
clean, blanked = edge.range_check({"heart_rate": 250, "spo2": 97})
print(clean, "blanked:", blanked)
'''),
]
write("02_data_and_pipeline.ipynb", nb2)

# ------------------------------------------------------------ notebook 3
nb3 = [
    md('''
# 03 · Fault test and API timing (R9, R11, Week 8 Milestone 1 C and D)
Plays the same messy hour through the API **with and without the edge range check**, then times the two
ways of serving the model (Week 8 designs C and D). Everything runs in this notebook: no Docker needed.
'''),
    SETUP,
    code('''
import json, time
from simulator.generator import simulate
from simulator import edge
from tests.helpers import make_client, post
from src import config

register = json.loads(config.PATIENTS_PATH.read_text())
events, observed = simulate(register, minutes=45, seed=11, faults=True)
truth = {o["reading_id"]: o["true_label"] for o in observed}
print(len(events), "messages")
'''),
    md('## Edge ON vs edge OFF'),
    code('''
def play(use_edge):
    client, rows = make_client(register), []
    for ev in events:
        reading = edge.range_check(ev["reading"])[0] if use_edge else ev["reading"]
        r = post(client, reading)
        rows.append({"fault": ev["fault"] or "clean", "code": r.status_code,
                     "outcome": r.get_json().get("outcome"), "alert": bool(r.get_json().get("alert"))})
    return pd.DataFrame(rows)

with_edge, without_edge = play(True), play(False)
pd.DataFrame({"edge ON": with_edge.groupby(["code", "outcome"]).size(),
              "edge OFF": without_edge.groupby(["code", "outcome"]).size()}).fillna(0).astype(int)
'''),
    md('''
**Milestone 1 C, what did validation throw away?** With the edge OFF, every glitched reading is refused with a 422, so its *good* vitals are lost too.
With the edge ON, only the impossible value is blanked and the rest of the reading is kept.
'''),
    code('''
g_off = without_edge[without_edge.fault == "glitch"]
g_on = with_edge[with_edge.fault == "glitch"]
print(f"glitched readings: {len(g_off)}")
print(f"  edge OFF: {int((g_off.code == 422).sum())} refused (whole reading lost)")
print(f"  edge ON : {int((g_on.code == 201).sum())} stored with the bad value blanked")
'''),
    md('**YOUR TURN:** which is better for the patient, and what is the cost of doing the check at the edge? (Week 4 trade-offs; R9.)'),
    md('## Design C vs D: load the model once, or on every request (Week 8)'),
    code('''
import joblib
from app.classify import classify
from src import model as M
from tests.helpers import normal_reading

patient = {"patient_id": "P001", "risk_group": "Medium", "has_diabetes": 1}
reading = normal_reading()
model = M.load_model()

def time_it(fn, n=40):
    out = []
    for _ in range(n):
        t = time.perf_counter(); fn(); out.append((time.perf_counter() - t) * 1000)
    return np.percentile(out, [50, 95]).round(1)

c_times = time_it(lambda: classify(model, patient, [], reading))
d_times = time_it(lambda: classify(joblib.load(config.MODEL_PATH), patient, [], reading))
pd.DataFrame({"p50 (ms)": [c_times[0], d_times[0]], "p95 (ms)": [c_times[1], d_times[1]]},
             index=["C: model loaded once", "D: model loaded every request"])
'''),
    md('**YOUR TURN:** write ADR 3 using these numbers (your times will differ: say what machine you used).'),
]
write("03_fault_test_and_timing.ipynb", nb3)
print("notebooks written")
