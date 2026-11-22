# Data card

**Source:** 100% simulated by `simulator/generator.py`. No real patient data, from anyone, at any stage (R7).

| File | What | Made by |
|---|---|---|
| `data/patients.json` | 20 invented patients: ID, age, conditions, risk group, assigned clinician (C01–C04) | `python -m simulator.make_dataset` |
| `data/simulated_readings.csv` | TRAINING data: 80 other invented patients (IDs `T001`…), 360 readings each (1 per minute) | same command |

**Columns (CSV):** reading_id, patient_id, timestamp, heart_rate, spo2, systolic, diastolic, temperature,
glucose (diabetes only), minute, fault, true_label, risk_group, has_diabetes.

**How readings are made:** baseline per patient (shifted by hypertension, arrhythmia, age) + slow random wobble
+ occasional deterioration episodes (infection-like, low oxygen, hypertensive, high/low glucose).
Episode frequency depends on the risk group.

**How labels are made:** `src/rules.py` scores each *true* (pre-fault) reading with points, in the spirit of
NEWS2 (Royal College of Physicians, 2017): 6+ points = Critical; 3–5 points or any single vital worth 3 =
Warning; otherwise Normal. Diastolic and glucose bands are my own additions.

**Problems created on purpose (R9):** sensor dropouts, single missing vitals, impossible values (glitches),
stuck sensors, readings delivered 20–45 minutes late, and resent copies. The `fault` column records which.

**Known limits (say these in your report):**
- Labels come from a rule, so a model largely re-learns the rule.
- Simulated patients are simpler than real ones: no medication, sleep, exercise or sensor drift.
- Class balance (rare Critical) is a design choice, not a clinical statistic.
- Not for any clinical use.
